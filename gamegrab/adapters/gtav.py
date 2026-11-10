"""GTA V – nur Fahrzeuge, aus der FiveM-Dokumentation «Vehicle models» (docs.fivem.net).

Es gibt keine offene API: Die Seite wird langsam gelesen (höchstens 1 Anfrage pro Sekunde).
Keine Waffen, Figuren oder Story. Militärfahrzeuge (mit Waffen) werden ausgelassen.
GTA V ist ab 18 (PEGI 18): Einsatz vorher mit der Schulleitung klären.
Preis und Hersteller ergänzen die Lernenden selbst.
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import urljoin

from .base import Adapter
from ..namen import endung_aus_url
from ..netz import GamegrabFehler

SEITE = "https://docs.fivem.net/docs/game-references/vehicle-references/vehicle-models/"
AUSGELASSEN = {"military"}


class _FahrzeugParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fahrzeuge: List[dict] = []
        self.klassen: dict = {}
        self._klasse: Optional[str] = None
        self._ueberschrift: Optional[str] = None
        self._h2 = False
        self._aktuell: Optional[dict] = None
        self._span: Optional[List[str]] = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        klassen = (a.get("class") or "").split()
        if tag == "h2":
            self._h2 = True
            self._ueberschrift = ""
        elif tag == "div" and "category" in klassen:
            self._klasse = a.get("id") or (self._ueberschrift or "").lower()
            self.klassen[self._klasse] = (self._ueberschrift or self._klasse).strip()
        elif tag == "div" and "vehicle" in klassen:
            self._aktuell = {"klasse": self._klasse}
            self.fahrzeuge.append(self._aktuell)
        elif tag == "img" and self._aktuell is not None and "src" not in self._aktuell:
            self._aktuell["src"] = a.get("src")
            self._aktuell["alt"] = a.get("alt")
        elif tag == "span" and self._aktuell is not None:
            self._span = []

    def handle_endtag(self, tag):
        if tag == "h2":
            self._h2 = False
        elif tag == "span" and self._span is not None and self._aktuell is not None:
            text = "".join(self._span)
            schluessel, _, wert = text.partition(":")
            self._aktuell[schluessel.strip().lower()] = wert.strip()
            self._span = None

    def handle_data(self, data):
        if self._h2:
            self._ueberschrift = (self._ueberschrift or "") + data
        if self._span is not None:
            self._span.append(data)


def lies_fahrzeuge(html: str):
    p = _FahrzeugParser()
    p.feed(html)
    return p.fahrzeuge, p.klassen


class GtaV(Adapter):
    name = "gtav"
    titel = "GTA V (nur Fahrzeuge)"
    alter = "18"
    beschreibung = "Fahrzeugmodelle mit Klasse und Bild aus der FiveM-Doku; Preis/Hersteller ergänzen die Lernenden"
    kategorien = {k: f"fahrzeuge/{k}" for k in (
        "compacts sedans suvs coupes muscle sports-classics sports super motorcycles off-road industrial utility "
        "vans cycles boats helicopters planes service emergency commercial trains open-wheels").split()}
    entitaeten = {"fahrzeuge": ["id", "name", "klasse", "hash", "hersteller", "preis", "datei"],
                  "klassen": ["id", "name"]}
    erlaubte_hosts = ("docs.fivem.net",)
    rate = 1.0
    quelle = f"FiveM-Dokumentation, Vehicle models: {SEITE}"
    lizenz = ("Fahrzeugnamen und Bilder gehören Rockstar Games / Take-Two Interactive.\n"
              "Rockstar-Richtlinie zu urheberrechtlich geschütztem Material: "
              "https://support.rockstargames.com/articles/200153756/Policy-on-posting-copyrighted-Rockstar-Games-material\n"
              "Seite der FiveM-Doku (Cfx.re) wird höchstens 1x pro Sekunde abgefragt.")
    disclaimer = "Grand Theft Auto V © Rockstar Games. Nicht offiziell, nicht von Rockstar Games unterstützt."
    hinweise = ("ACHTUNG: GTA V ist ab 18 Jahren (PEGI 18). Einsatz im Unterricht vorher mit der Schulleitung klären. "
                "Es werden nur Fahrzeuge geladen – keine Waffen, Figuren oder Story.",)
    anzahl_hinweis = "total (mit --typ: pro Klasse)"
    loesung_schema = {
        "klasse": {"spalten": ["id", "name"], "pk": ["id"]},
        "hersteller": {"spalten": ["id", "name"], "pk": ["id"]},
        "fahrzeug": {"spalten": ["id", "name", "klasse_id", "hersteller_id", "hash", "preis", "datei"], "pk": ["id"],
                     "fk": {"klasse_id": "klasse.id", "hersteller_id": "hersteller.id"}},
    }

    def hole(self, opt, http, namen):
        html = http.get_text(SEITE)
        fahrzeuge, klassen = lies_fahrzeuge(html)
        if not fahrzeuge:
            raise GamegrabFehler("Auf der FiveM-Seite wurden keine Fahrzeuge gefunden (Aufbau geändert?)")
        gewaehlt = [t.lower() for t in opt.typ]
        verboten = [t for t in gewaehlt if t in AUSGELASSEN]
        if verboten:
            raise GamegrabFehler("Militärfahrzeuge werden bewusst nicht geladen (Waffen).")
        unbekannt = [t for t in gewaehlt if t not in klassen]
        if unbekannt:
            raise GamegrabFehler("unbekannte Klassen: " + ", ".join(unbekannt) + " – erlaubt: " +
                                 ", ".join(k for k in klassen if k not in AUSGELASSEN))
        auswahl, pro_klasse = [], {}
        for f in fahrzeuge:
            k = f.get("klasse")
            if k in AUSGELASSEN or (gewaehlt and k not in gewaehlt):
                continue
            name = f.get("display name") or f.get("alt") or f.get("model name")
            if opt.suche and opt.suche.lower() not in (name or "").lower() and opt.suche.lower() not in (f.get("model name") or ""):
                continue
            if opt.anzahl:
                if gewaehlt:
                    if pro_klasse.get(k, 0) >= opt.anzahl:
                        continue
                    pro_klasse[k] = pro_klasse.get(k, 0) + 1
                elif len(auswahl) >= opt.anzahl:
                    break
            auswahl.append(f)
        zeilen = []
        for f in auswahl:
            modell = f.get("model name") or f.get("alt")
            datei = ""
            if f.get("src"):
                url = urljoin(SEITE, f["src"])
                datei = self.datei(namen, f"fahrzeuge/{f['klasse']}", modell, endung_aus_url(url, "webp"), url)
            zeilen.append({"id": modell, "name": f.get("display name") or f.get("alt"), "klasse": f["klasse"],
                           "hash": f.get("hash"), "hersteller": "", "preis": "", "datei": datei})
        benutzt = []
        for z in zeilen:
            if z["klasse"] not in benutzt:
                benutzt.append(z["klasse"])
        return {"fahrzeuge": zeilen, "klassen": [{"id": k, "name": klassen.get(k, k)} for k in benutzt]}

    def loesung(self, daten, opt):
        return {
            "klasse": daten["klassen"],
            "hersteller": [],
            "fahrzeug": [{"id": f["id"], "name": f["name"], "klasse_id": f["klasse"], "hersteller_id": "",
                          "hash": f["hash"], "preis": "", "datei": f["datei"]} for f in daten["fahrzeuge"]],
        }
