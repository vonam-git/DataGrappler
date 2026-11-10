"""Minecraft: Daten aus PrismarineJS/minecraft-data (MIT, JSON auf GitHub).

Texturen (PNG) und Geräusche (OGG) gehören Mojang. Sie werden NIE aus dem Internet geladen,
sondern nur mit --lokal aus der eigenen Installation gelesen:
  .minecraft/versions/<v>/<v>.jar            -> assets/minecraft/textures/item|block/<name>.png
  .minecraft/assets/indexes/<index>.json     -> objects/<hh>/<hash> (Töne)
Es werden nur die ausgewählten Dateien kopiert. Spieler-Skins/Benutzernamen werden nie abgefragt.
"""
from __future__ import annotations

import json
import os
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from .base import Adapter, LokaleDatei, ZipEintrag
from ..netz import GamegrabFehler

ROH = "https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master/data"
DATEIEN = ["items", "blocks", "entities", "biomes", "recipes", "enchantments", "entityLoot"]
KATEGORIEN = {"items": "items", "bloecke": "bloecke", "kreaturen": "kreaturen", "biome": "biome",
              "rezepte": "rezepte", "verzauberungen": "verzauberungen"}
KEINE_KREATUR = {"other", "projectile", "player"}


def _version_key(v: str):
    return [int(x) for x in v.split(".")]


def neueste_version(pfade: Dict[str, dict]) -> str:
    vs = [k for k in pfade if re.fullmatch(r"\d+\.\d+(\.\d+)?", k) and "items" in pfade[k]]
    if not vs:
        raise GamegrabFehler("keine Minecraft-Version in dataPaths.json gefunden")
    return max(vs, key=_version_key)


def standard_minecraft_ordner() -> Path:
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / ".minecraft"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "minecraft"
    return Path.home() / ".minecraft"


class LokaleInstallation:
    """Liest nur aus der eigenen Installation; kopiert wird später nur, was ausgewählt ist."""

    def __init__(self, ordner: Path, version: str, melde) -> None:
        self.ordner = ordner
        versionen = ordner / "versions"
        jar = versionen / version / f"{version}.jar"
        if not jar.is_file():
            installiert = [p.name for p in versionen.glob("*") if (p / f"{p.name}.jar").is_file()] if versionen.is_dir() else []
            nummern = [v for v in installiert if re.fullmatch(r"\d+\.\d+(\.\d+)?", v)]
            if not nummern:
                raise GamegrabFehler(f"keine Minecraft-Installation gefunden in {versionen} (Pfad mit --lokal PFAD angeben)")
            ersatz = max(nummern, key=_version_key)
            melde(f"Version {version} ist nicht installiert, nehme Texturen aus {ersatz}")
            version = ersatz
            jar = versionen / version / f"{version}.jar"
        self.jar = jar
        with zipfile.ZipFile(jar) as z:
            self.eintraege = set(z.namelist())
        self.objekte: Dict[str, str] = {}
        meta = versionen / version / f"{version}.json"
        try:
            index_id = json.loads(meta.read_text("utf-8"))["assetIndex"]["id"]
            index = json.loads((ordner / "assets" / "indexes" / f"{index_id}.json").read_text("utf-8"))
            self.objekte = {k: v["hash"] for k, v in index.get("objects", {}).items()}
        except (OSError, ValueError, KeyError):
            melde("keine Ton-Liste (assets/indexes) gefunden – es werden nur Texturen gelesen")

    def textur(self, art: str, name: str) -> Optional[ZipEintrag]:
        for kandidat in (name, f"{name}_front", f"{name}_side", f"{name}_top", f"{name}_00"):
            e = f"assets/minecraft/textures/{art}/{kandidat}.png"
            if e in self.eintraege:
                return ZipEintrag(str(self.jar), e)
        return None

    def ton(self, kreatur: str) -> Optional[LokaleDatei]:
        praefix = f"minecraft/sounds/mob/{kreatur}/"
        kandidaten = sorted(k for k in self.objekte if k.startswith(praefix) and k.endswith(".ogg"))
        if not kandidaten:
            return None
        bevorzugt = [k for k in kandidaten if re.search(r"/(say|idle|ambient|living)\d*\.ogg$", k)]
        h = self.objekte[(bevorzugt or kandidaten)[0]]
        p = self.ordner / "assets" / "objects" / h[:2] / h
        return LokaleDatei(str(p)) if p.is_file() else None


def _zutat_id(z):
    if z is None:
        return None
    if isinstance(z, int):
        return z
    if isinstance(z, dict):
        return z.get("id")
    if isinstance(z, list) and z:
        return _zutat_id(z[0])
    return None


def _drop_id(d):
    if isinstance(d, int):
        return d
    if isinstance(d, dict):
        x = d.get("drop", d.get("id"))
        return x.get("id") if isinstance(x, dict) else x
    return None


class Minecraft(Adapter):
    name = "minecraft"
    titel = "Minecraft (Java Edition)"
    alter = "7"
    beschreibung = "Items, Blöcke, Kreaturen, Biome, Rezepte, Verzauberungen (PrismarineJS); Bilder/Töne nur mit --lokal"
    kategorien = KATEGORIEN
    entitaeten = {
        "items": ["id", "name", "anzeigename", "stapelgroesse", "datei"],
        "bloecke": ["id", "name", "anzeigename", "haerte", "widerstand", "abbaubar", "material", "werkzeuge",
                    "drops", "datei"],
        "kreaturen": ["id", "name", "anzeigename", "typ", "kategorie", "breite", "hoehe", "drops", "datei", "ton"],
        "biome": ["id", "name", "anzeigename", "kategorie", "temperatur", "dimension", "niederschlag"],
        "rezepte": ["id", "name", "ergebnis", "menge", "form", "zutaten"],
        "verzauberungen": ["id", "name", "anzeigename", "max_stufe", "kategorie", "schatz", "fluch", "schliesst_aus"],
    }
    erlaubte_hosts = ("raw.githubusercontent.com",)
    quelle = "PrismarineJS/minecraft-data (MIT): https://github.com/PrismarineJS/minecraft-data"
    lizenz = ("Daten: minecraft-data, MIT-Lizenz (PrismarineJS).\n"
              "Texturen und Geräusche: gehören Mojang/Microsoft, nur aus der eigenen Installation gelesen (--lokal).\n"
              "Minecraft Usage Guidelines: https://www.minecraft.net/en-us/usage-guidelines")
    disclaimer = "NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT."
    anzahl_hinweis = "pro Entität (ohne --anzahl: alle)"
    loesung_schema = {
        "item": {"spalten": ["id", "name", "anzeigename", "stapelgroesse", "datei"], "pk": ["id"]},
        "block": {"spalten": ["id", "name", "anzeigename", "haerte", "widerstand", "abbaubar", "material", "datei"],
                  "pk": ["id"]},
        "kreatur": {"spalten": ["id", "name", "anzeigename", "typ", "kategorie", "breite", "hoehe", "datei", "ton"],
                    "pk": ["id"]},
        "biom": {"spalten": ["id", "name", "anzeigename", "kategorie", "temperatur", "dimension"], "pk": ["id"]},
        "verzauberung": {"spalten": ["id", "name", "anzeigename", "max_stufe", "kategorie"], "pk": ["id"]},
        "rezept": {"spalten": ["id", "ergebnis_item_id", "menge", "form"], "pk": ["id"],
                   "fk": {"ergebnis_item_id": "item.id"}},
        "rezept_zutat": {"spalten": ["rezept_id", "item_id", "menge"], "pk": ["rezept_id", "item_id"],
                         "fk": {"rezept_id": "rezept.id", "item_id": "item.id"}},
        "block_werkzeug": {"spalten": ["block_id", "item_id"], "pk": ["block_id", "item_id"],
                           "fk": {"block_id": "block.id", "item_id": "item.id"}},
        "block_drop": {"spalten": ["block_id", "item_id"], "pk": ["block_id", "item_id"],
                       "fk": {"block_id": "block.id", "item_id": "item.id"}},
        "kreatur_drop": {"spalten": ["kreatur_id", "item_id", "chance"], "pk": ["kreatur_id", "item_id"],
                         "fk": {"kreatur_id": "kreatur.id", "item_id": "item.id"}},
    }

    def _passt(self, eintrag, opt) -> bool:
        if not opt.suche:
            return True
        s = opt.suche.lower()
        return s in (eintrag.get("name") or "").lower() or s in (eintrag.get("displayName") or "").lower()

    def hole(self, opt, http, namen):
        pfade = http.get_json(f"{ROH}/dataPaths.json")["pc"]
        version = opt.spielversion or neueste_version(pfade)
        if version not in pfade:
            raise GamegrabFehler(f"unbekannte Minecraft-Version {version}")
        self.version = version
        self.melde(f"Minecraft-Version {version}")
        vp = pfade[version]
        roh = {}
        for d in DATEIEN:
            roh[d] = http.get_json(f"{ROH}/{vp[d]}/{d}.json") if d in vp else ([] if d != "recipes" else {})

        gewaehlt = set(opt.typ) if opt.typ else set(KATEGORIEN)
        unbekannt = gewaehlt - set(KATEGORIEN)
        if unbekannt:
            raise GamegrabFehler("unbekannte Typen: " + ", ".join(sorted(unbekannt)) + " (erlaubt: " + ", ".join(KATEGORIEN) + ")")
        lokal = None
        if opt.lokal:
            ordner = standard_minecraft_ordner() if opt.lokal == "auto" else Path(opt.lokal).expanduser()
            lokal = LokaleInstallation(ordner, version, self.melde)
        else:
            self.melde("ohne --lokal: nur Daten (CSV), keine Texturen/Töne")

        items = {i["id"]: i for i in roh["items"]}
        item_name = {i["id"]: i["name"] for i in roh["items"]}
        item_nach_name = {i["name"]: i["id"] for i in roh["items"]}

        def begrenze(liste):
            liste = [e for e in liste if self._passt(e, opt)]
            return liste[: opt.anzahl] if opt.anzahl else liste

        daten = {}
        self._rel = {"rezept_zutat": [], "block_werkzeug": [], "block_drop": [], "kreatur_drop": [], "rezept": []}
        if "items" in gewaehlt:
            zeilen = []
            for i in begrenze([i for i in roh["items"] if i["name"] != "air"]):
                datei = ""
                if lokal:
                    t = lokal.textur("item", i["name"]) or lokal.textur("block", i["name"])
                    if t:
                        datei = self.datei(namen, "items", i["name"], "png", t)
                zeilen.append({"id": i["id"], "name": i["name"], "anzeigename": i.get("displayName"),
                               "stapelgroesse": i.get("stackSize"), "datei": datei})
            daten["items"] = zeilen
        if "bloecke" in gewaehlt:
            zeilen = []
            for b in begrenze([b for b in roh["blocks"] if b["name"] != "air"]):
                werkzeuge = [int(k) for k in (b.get("harvestTools") or {})]
                drops = [x for x in (_drop_id(d) for d in b.get("drops") or []) if x is not None]
                datei = ""
                if lokal:
                    t = lokal.textur("block", b["name"])
                    if t:
                        datei = self.datei(namen, "bloecke", b["name"], "png", t)
                zeilen.append({"id": b["id"], "name": b["name"], "anzeigename": b.get("displayName"),
                               "haerte": b.get("hardness"), "widerstand": b.get("resistance"),
                               "abbaubar": b.get("diggable"), "material": b.get("material"),
                               "werkzeuge": [item_name.get(w, str(w)) for w in werkzeuge],
                               "drops": [item_name.get(d, str(d)) for d in drops], "datei": datei})
                self._rel["block_werkzeug"] += [{"block_id": b["id"], "item_id": w} for w in sorted(set(werkzeuge))]
                self._rel["block_drop"] += [{"block_id": b["id"], "item_id": d} for d in sorted(set(drops))]
            daten["bloecke"] = zeilen
        if "kreaturen" in gewaehlt:
            loot = {e["entity"]: e.get("drops") or [] for e in roh["entityLoot"]}
            zeilen = []
            for e in begrenze([e for e in roh["entities"] if e.get("type") not in KEINE_KREATUR]):
                drops = loot.get(e["name"], [])
                datei = ton = ""
                if lokal:
                    t = lokal.ton(e["name"])
                    if t:
                        ton = self.datei(namen, "kreaturen", e["name"], "ogg", t)
                    sp = lokal.textur("item", f"{e['name']}_spawn_egg")
                    if sp:
                        datei = self.datei(namen, "kreaturen", e["name"], "png", sp)
                zeilen.append({"id": e["id"], "name": e["name"], "anzeigename": e.get("displayName"),
                               "typ": e.get("type"), "kategorie": e.get("category"), "breite": e.get("width"),
                               "hoehe": e.get("height"), "drops": [d["item"] for d in drops if d.get("item")],
                               "datei": datei, "ton": ton})
                gesehen = set()
                for d in drops:
                    iid = item_nach_name.get(d.get("item"))
                    if iid is not None and iid not in gesehen:
                        gesehen.add(iid)
                        self._rel["kreatur_drop"].append({"kreatur_id": e["id"], "item_id": iid,
                                                          "chance": d.get("dropChance")})
            daten["kreaturen"] = zeilen
        if "biome" in gewaehlt:
            daten["biome"] = [{"id": b["id"], "name": b["name"], "anzeigename": b.get("displayName"),
                               "kategorie": b.get("category"), "temperatur": b.get("temperature"),
                               "dimension": b.get("dimension"), "niederschlag": b.get("has_precipitation")}
                              for b in begrenze(roh["biomes"])]
        if "rezepte" in gewaehlt:
            zeilen = []
            nr = 0
            for ergebnis_id, varianten in roh["recipes"].items():
                for v in varianten:
                    erg = v.get("result") or {}
                    rid = _zutat_id(erg) if isinstance(erg, (dict, int)) else None
                    if rid is None:
                        rid = int(ergebnis_id)
                    menge = erg.get("count", 1) if isinstance(erg, dict) else 1
                    if "inShape" in v:
                        zutaten = Counter(_zutat_id(z) for reihe in v["inShape"] for z in reihe)
                        form = "geformt"
                    else:
                        zutaten = Counter(_zutat_id(z) for z in v.get("ingredients") or [])
                        form = "formlos"
                    zutaten.pop(None, None)
                    eintrag = items.get(rid, {"name": str(rid), "displayName": str(rid)})
                    if not self._passt(eintrag, opt):
                        continue
                    nr += 1
                    rez_id = f"r{nr}"
                    zeilen.append({"id": rez_id, "name": eintrag.get("displayName"), "ergebnis": eintrag.get("name"),
                                   "menge": menge, "form": form,
                                   "zutaten": [f"{n}x {item_name.get(z, z)}" for z, n in sorted(zutaten.items(), key=lambda kv: -kv[1])]})
                    self._rel["rezept"].append({"id": rez_id, "ergebnis_item_id": rid, "menge": menge, "form": form})
                    self._rel["rezept_zutat"] += [{"rezept_id": rez_id, "item_id": z, "menge": n} for z, n in zutaten.items()]
                    if opt.anzahl and nr >= opt.anzahl:
                        break
                if opt.anzahl and nr >= opt.anzahl:
                    break
            daten["rezepte"] = zeilen
        if "verzauberungen" in gewaehlt:
            daten["verzauberungen"] = [{"id": v["id"], "name": v["name"], "anzeigename": v.get("displayName"),
                                        "max_stufe": v.get("maxLevel"), "kategorie": v.get("category"),
                                        "schatz": v.get("treasureOnly"), "fluch": v.get("curse"),
                                        "schliesst_aus": v.get("exclude") or []}
                                       for v in begrenze(roh["enchantments"])]
        # vollständige Item-Liste für die Lösung (damit Fremdschlüssel aufgehen)
        self._alle_items = [{"id": i["id"], "name": i["name"], "anzeigename": i.get("displayName"),
                             "stapelgroesse": i.get("stackSize"), "datei": ""} for i in roh["items"]]
        return daten

    def quellen_text(self, opt):
        return f"Minecraft-Version der Daten: {getattr(self, 'version', '?')}"

    def loesung(self, daten, opt):
        items = {z["id"]: dict(z) for z in self._alle_items}
        for z in daten.get("items", []):
            items[z["id"]] = z
        bloecke = daten.get("bloecke", [])
        kreaturen = daten.get("kreaturen", [])
        bids = {b["id"] for b in bloecke}
        kids = {k["id"] for k in kreaturen}

        def gueltig(zeilen, **pruef):
            return [z for z in zeilen if all(z[k] in menge for k, menge in pruef.items())]

        rezepte = gueltig(self._rel["rezept"], ergebnis_item_id=items)
        rids = {r["id"] for r in rezepte}
        return {
            "item": list(items.values()),
            "block": bloecke,
            "kreatur": kreaturen,
            "biom": daten.get("biome", []),
            "verzauberung": daten.get("verzauberungen", []),
            "rezept": rezepte,
            "rezept_zutat": gueltig(self._rel["rezept_zutat"], rezept_id=rids, item_id=items),
            "block_werkzeug": gueltig(self._rel["block_werkzeug"], block_id=bids, item_id=items),
            "block_drop": gueltig(self._rel["block_drop"], block_id=bids, item_id=items),
            "kreatur_drop": gueltig(self._rel["kreatur_drop"], kreatur_id=kids, item_id=items),
        }
