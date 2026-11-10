"""Fortnite über Fortnite-API.com (Community-API, nicht von Epic). Cosmetics ohne API-Schlüssel.

Endpunkte: /v2/cosmetics/br (alle BR-Cosmetics), /v2/cosmetics/tracks (Songs, nur Metadaten + Cover).
showcaseVideo ist eine YouTube-ID: gamegrab speichert NUR den Link und lädt nie Videos herunter.
Spielerstatistiken (brauchen einen Schlüssel) ruft das Tool nie ab.
"""
from __future__ import annotations

from .base import Adapter, IdVergabe, kuerze
from ..namen import endung_aus_url

API = "https://fortnite-api.com"

KATEGORIEN = {
    "outfit": "skins",
    "backpack": "rucksaecke",
    "emote": "taenze",
    "pickaxe": "spitzhacken",
    "glider": "gleiter",
    "track": "songs",
}
STANDARD = ["outfit", "backpack", "emote", "pickaxe"]
BILD_FELD = {"small": "smallIcon", "icon": "icon", "featured": "featured"}

EPIC_DISCLAIMER = ("Portions of the materials used are trademarks and/or copyrighted works of Epic Games, Inc. "
                   "All rights reserved by Epic. This material is not official and is not endorsed by Epic.")


class Fortnite(Adapter):
    name = "fortnite"
    titel = "Fortnite"
    alter = "12"
    beschreibung = "Cosmetics (Skins, Rucksäcke, Tänze, Spitzhacken, Gleiter) und Songs von Fortnite-API.com"
    kategorien = KATEGORIEN
    entitaeten = {
        "items": ["id", "name", "typ", "kategorie", "seltenheit", "set", "saison", "hinzugefuegt",
                  "beschreibung", "datei", "video_link", "shop_daten"],
        "songs": ["id", "name", "interpret", "album", "jahr", "bpm", "dauer_s", "genres", "hinzugefuegt", "datei"],
    }
    erlaubte_hosts = ("fortnite-api.com", "cdn2.unrealengine.com", "cdn1.epicgames.com")
    json_name = "items.json"
    quelle = ("Fortnite-API.com (Community-API, nicht von Epic Games): https://fortnite-api.com/v2/cosmetics/br "
              "und /v2/cosmetics/tracks")
    lizenz = ("Epic Games Fan Content Policy: https://legal.epicgames.com/epicgames/fan-art-policy\n"
              "Erlaubt nicht-kommerzielle Fan-Inhalte und verlangt den untenstehenden Disclaimer.\n"
              "Videos: nur YouTube-Links (showcaseVideo), kein Download (YouTube-Nutzungsbedingungen).")
    disclaimer = EPIC_DISCLAIMER
    anzahl_hinweis = "pro Typ (z.B. --typ outfit,backpack --anzahl 20 = 40 Items)"
    loesung_schema = {
        "typ": {"spalten": ["id", "name", "kategorie"], "pk": ["id"]},
        "seltenheit": {"spalten": ["id", "name"], "pk": ["id"]},
        "cosmetic_set": {"spalten": ["id", "name"], "pk": ["id"]},
        "saison": {"spalten": ["id", "name"], "pk": ["id"]},
        "cosmetic": {"spalten": ["id", "name", "typ_id", "seltenheit_id", "set_id", "saison_id", "hinzugefuegt",
                                 "beschreibung", "datei", "video_link"], "pk": ["id"],
                     "fk": {"typ_id": "typ.id", "seltenheit_id": "seltenheit.id", "set_id": "cosmetic_set.id",
                            "saison_id": "saison.id"}},
        "shop_auftritt": {"spalten": ["cosmetic_id", "datum"], "pk": ["cosmetic_id", "datum"],
                          "fk": {"cosmetic_id": "cosmetic.id"}},
        "song": {"spalten": ["id", "name", "interpret", "album", "jahr", "bpm", "dauer_s", "datei"], "pk": ["id"]},
    }

    @staticmethod
    def _passt(c, opt) -> bool:
        if opt.seltenheit and ((c.get("rarity") or {}).get("value") or "").lower() not in {s.lower() for s in opt.seltenheit}:
            return False
        if opt.neu_seit and (c.get("added") or "")[:10] < opt.neu_seit.isoformat():
            return False
        if opt.suche:
            name = c.get("name") or c.get("title") or ""
            if opt.suche.lower() not in name.lower():
                return False
        return True

    def hole(self, opt, http, namen):
        typen = [t.lower() for t in (opt.typ or STANDARD)]
        unbekannt = [t for t in typen if t not in KATEGORIEN]
        if unbekannt:
            self.melde("unbekannte Typen werden in eigene Ordner gelegt: " + ", ".join(unbekannt))
        daten = {}
        br_typen = [t for t in typen if t != "track"]
        if br_typen:
            antwort = http.get_json(f"{API}/v2/cosmetics/br", params={"language": opt.sprache})
            alle = antwort.get("data") or []
            pro_typ = {t: [] for t in br_typen}
            for c in alle:
                t = ((c.get("type") or {}).get("value") or "").lower()
                if t in pro_typ and self._passt(c, opt):
                    pro_typ[t].append(c)
            zeilen = []
            for t in br_typen:
                auswahl = sorted(pro_typ[t], key=lambda c: c.get("added") or "", reverse=True)
                if opt.anzahl:
                    auswahl = auswahl[: opt.anzahl]
                for c in auswahl:
                    zeilen.append(self._zeile(c, t, opt, namen))
            daten["items"] = zeilen
        if "track" in typen:
            antwort = http.get_json(f"{API}/v2/cosmetics/tracks")
            songs = [s for s in (antwort.get("data") or []) if self._passt(s, opt)]
            songs.sort(key=lambda s: s.get("added") or "", reverse=True)
            if opt.anzahl:
                songs = songs[: opt.anzahl]
            daten["songs"] = [self._song(s, namen) for s in songs]
        return daten

    def _zeile(self, c, typ, opt, namen):
        ordner = KATEGORIEN.get(typ, typ)
        bilder = c.get("images") or {}
        url = bilder.get(BILD_FELD[opt.bild]) or bilder.get("smallIcon") or bilder.get("icon")
        datei = ""
        if url:
            datei = self.datei(namen, ordner, c.get("name") or c.get("id"), endung_aus_url(url, "png"), url)
        einf = c.get("introduction") or {}
        video = c.get("showcaseVideo")
        historie = c.get("shopHistory") or []
        return {
            "id": c.get("id"),
            "name": c.get("name"),
            "typ": typ,
            "kategorie": ordner,
            "seltenheit": (c.get("rarity") or {}).get("value"),
            "set": (c.get("set") or {}).get("value"),
            "saison": einf.get("text"),
            "hinzugefuegt": (c.get("added") or "")[:10],
            "beschreibung": kuerze(c.get("description")),
            "datei": datei,
            "video_link": f"https://youtu.be/{video}" if video else "",
            "shop_daten": [d[:10] for d in historie[-10:]],
        }

    def _song(self, s, namen):
        url = s.get("albumArt")
        datei = ""
        if url:
            datei = self.datei(namen, "songs", s.get("title") or s.get("id"), endung_aus_url(url, "jpg"), url)
        return {
            "id": s.get("id"),
            "name": s.get("title"),
            "interpret": s.get("artist"),
            "album": s.get("album"),
            "jahr": s.get("releaseYear"),
            "bpm": s.get("bpm"),
            "dauer_s": s.get("duration"),
            "genres": s.get("genres") or [],
            "hinzugefuegt": (s.get("added") or "")[:10],
            "datei": datei,
        }

    def loesung(self, daten, opt):
        typ, selt, sets, saison = IdVergabe(), IdVergabe(), IdVergabe(), IdVergabe()
        cosmetics, shop = [], []
        typ_ordner = {}
        for z in daten.get("items", []):
            typ_ordner[z["typ"]] = z["kategorie"]
            cosmetics.append({
                "id": z["id"], "name": z["name"], "typ_id": typ(z["typ"]), "seltenheit_id": selt(z["seltenheit"]),
                "set_id": sets(z["set"]), "saison_id": saison(z["saison"]), "hinzugefuegt": z["hinzugefuegt"],
                "beschreibung": z["beschreibung"], "datei": z["datei"], "video_link": z["video_link"]})
            for d in sorted(set(z["shop_daten"])):
                shop.append({"cosmetic_id": z["id"], "datum": d})
        typen = [{"id": i, "name": w, "kategorie": typ_ordner[w]} for w, i in typ.ids.items()]
        return {"typ": typen, "seltenheit": selt.zeilen(), "cosmetic_set": sets.zeilen(), "saison": saison.zeilen(),
                "cosmetic": cosmetics, "shop_auftritt": shop, "song": daten.get("songs", [])}
