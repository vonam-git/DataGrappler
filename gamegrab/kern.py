"""Ablauf eines Laufs – für alle Spiele gleich:
Liste laden (Adapter) -> filtern (Adapter) -> Dateien einzeln laden (Kern) -> schreiben (Kern)."""
from __future__ import annotations

import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from .adapters.base import Adapter, Erzeugt, LokaleDatei, Optionen, ZipEintrag
from .cache import Cache
from .namen import Dateinamen, liegt_in, sicherer_relpfad
from .netz import MAX_DATEI, DateiAbgelehnt, GamegrabFehler, HttpClient, erkenne_art
from . import schreiber

URHEBERRECHT = ("Hinweis: Die Bilder und Töne gehören den Spielefirmen. Nur für den Unterricht verwenden, "
                "nicht veröffentlichen und nicht in ein öffentliches Repository hochladen.")
WERKSTATT_LIMIT = 200 * 1024  # Standard «Maximalgrösse übrige Dateien» in der Werkstatt


class Ergebnis:
    def __init__(self, ziel: Path) -> None:
        self.ziel = ziel
        self.dateien = 0
        self.bytes = 0
        self.fehlgeschlagen: List[str] = []
        self.zip: Optional[Path] = None
        self.anfragen = 0
        self.cache_treffer = 0


def _lies_lokal(herkunft, max_bytes: int) -> bytes:
    if isinstance(herkunft, LokaleDatei):
        p = Path(herkunft.pfad)
        if not p.is_file():
            raise DateiAbgelehnt(f"Datei fehlt: {p}")
        if p.stat().st_size > max_bytes:
            raise DateiAbgelehnt(f"zu gross: {p.name}")
        return p.read_bytes()
    if isinstance(herkunft, ZipEintrag):
        with zipfile.ZipFile(herkunft.archiv) as z:
            info = z.getinfo(herkunft.eintrag)
            if info.file_size > max_bytes:
                raise DateiAbgelehnt(f"zu gross: {herkunft.eintrag}")
            return z.read(info)
    raise TypeError(herkunft)


def standard_ziel(adapter: Adapter, heute: Optional[date] = None) -> Path:
    return Path("rohdaten") / f"{adapter.name}_{(heute or date.today()).isoformat()}"


def ausfuehren(
    adapter: Adapter,
    opt: Optionen,
    cache_ordner: str = ".gamegrab-cache",
    session=None,
    melde: Callable[[str], None] = print,
    schlafen=None,
    heute: Optional[date] = None,
) -> Ergebnis:
    melde(f"gamegrab · {adapter.titel} (PEGI {adapter.alter})")
    melde(URHEBERRECHT)
    for h in adapter.hinweise:
        melde(h)
    if adapter.geruest:
        raise GamegrabFehler(f"Der Adapter «{adapter.name}» ist erst ein dokumentiertes Gerüst und lädt noch nichts. "
                             f"Siehe gamegrab/adapters/{adapter.name}.py.")

    ziel = Path(opt.ziel) if opt.ziel else standard_ziel(adapter, heute)
    ziel.mkdir(parents=True, exist_ok=True)
    erg = Ergebnis(ziel)

    kwargs = {"schlafen": schlafen} if schlafen else {}
    http = HttpClient(adapter.erlaubte_hosts, adapter.rate, Cache(cache_ordner), session=session, melde=melde, **kwargs)
    namen = Dateinamen()
    adapter._dateien = []
    adapter.meldungen = []

    melde("1/3 Liste laden und filtern …")
    daten = adapter.hole(opt, http, namen)
    for m in adapter.meldungen:
        melde("  " + m)
    for ent, zeilen in daten.items():
        melde(f"  {ent}: {len(zeilen)} Zeilen")

    # -- Dateien einzeln laden ------------------------------------------------
    jobs = list(adapter.dateien(opt))
    melde(f"2/3 Dateien laden ({len(jobs)}) …")
    max_gesamt = int(opt.max_mb * 1024 * 1024) if opt.max_mb else 0
    umbenannt: Dict[str, str] = {}
    fehlend: Set[str] = set()
    abgebrochen = False
    for i, (rel, herkunft) in enumerate(jobs, 1):
        try:
            sicher = sicherer_relpfad(rel)
        except ValueError:
            fehlend.add(rel)
            continue
        if sicher != rel:
            umbenannt[rel] = sicher
        if abgebrochen:
            fehlend.add(rel)
            continue
        try:
            if isinstance(herkunft, str):
                inhalt, endung = http.lade_datei(herkunft)
            elif isinstance(herkunft, Erzeugt):
                inhalt, endung = herkunft.inhalt, herkunft.endung
            else:
                inhalt = _lies_lokal(herkunft, MAX_DATEI)
                art = erkenne_art(inhalt)
                if art is None:
                    raise DateiAbgelehnt(f"kein Bild/Audio: {sicher}")
                endung = art[1]
        except (DateiAbgelehnt, GamegrabFehler, KeyError, OSError, zipfile.BadZipFile) as e:
            melde(f"  übersprungen: {sicher} ({e})")
            erg.fehlgeschlagen.append(sicher)
            fehlend.add(rel)
            continue
        if max_gesamt and erg.bytes + len(inhalt) > max_gesamt:
            melde(f"  Grenze --max-mb {opt.max_mb:g} erreicht – weitere Dateien werden nicht geladen.")
            abgebrochen = True
            fehlend.add(rel)
            continue
        # Endung an den tatsächlichen Inhalt anpassen
        stamm, _, alte = sicher.rpartition(".")
        if endung and alte != endung:
            neu = f"{stamm}.{endung}"
            umbenannt[rel] = neu
            sicher = neu
        pfad = ziel / sicher
        if not liegt_in(ziel, pfad):
            fehlend.add(rel)
            continue
        pfad.parent.mkdir(parents=True, exist_ok=True)
        if not (pfad.is_file() and pfad.stat().st_size == len(inhalt)):
            pfad.write_bytes(inhalt)
        erg.dateien += 1
        erg.bytes += len(inhalt)
        if i % 25 == 0:
            melde(f"  {i}/{len(jobs)} …")

    _pfade_anpassen(daten, umbenannt, fehlend)

    # -- Schreiben -------------------------------------------------------------
    melde("3/3 CSV, JSON und QUELLEN.txt schreiben …")
    jetzt = datetime.now()
    geschrieben = schreiber.schreibe_rohform(ziel, adapter, daten)
    geschrieben.append(schreiber.schreibe_json(ziel, adapter, daten, jetzt, opt))
    schreiber.schreibe_quellen(ziel, adapter, jetzt, opt)
    schreiber.schreibe_gitignore(ziel)
    if opt.normalisiert:
        tabellen = adapter.loesung(daten, opt)
        schreiber.schreibe_loesung(ziel, adapter, tabellen)
        melde("  _loesung/ mit Beziehungstabellen und erd.md erzeugt "
              "(Lösung für die Lehrperson – vor dem Weitergeben an Lernende entfernen).")
    for p in geschrieben:
        if p.stat().st_size > WERKSTATT_LIMIT:
            melde(f"  Hinweis: {p.name} ist {p.stat().st_size // 1024} KB gross. Die Werkstatt überspringt "
                  f"Textdateien über 200 KB, ausser du erhöhst «Maximalgrösse übrige Dateien» (oder nutzt --anzahl).")
    if opt.zip:
        erg.zip = schreiber.schreibe_zip(ziel)
    erg.anfragen = http.anfragen
    erg.cache_treffer = http.cache_treffer
    melde(f"Fertig: {ziel}  ({erg.dateien} Dateien, {erg.bytes / 1024 / 1024:.1f} MB, "
          f"{http.anfragen} Anfragen, {http.cache_treffer} aus dem Cache)")
    if erg.zip:
        melde(f"ZIP: {erg.zip}")
    melde("Weiter in Durchblick: Ordner in Werkstatt Schritt 1 ziehen, «In Benutzerordner einsortieren», Benutzer gamer.")
    return erg


def _pfade_anpassen(daten, umbenannt: Dict[str, str], fehlend: Set[str]) -> None:
    if not umbenannt and not fehlend:
        return
    for zeilen in daten.values():
        for z in zeilen:
            for k, v in z.items():
                if isinstance(v, str) and v:
                    if v in fehlend:
                        z[k] = ""
                    elif v in umbenannt:
                        z[k] = umbenannt[v]
