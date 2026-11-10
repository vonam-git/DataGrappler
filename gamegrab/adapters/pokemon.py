"""Pokémon über PokéAPI (https://pokeapi.co/api/v2), ohne Schlüssel.

Bilder: Sprites (Standard) bzw. Official Artwork (--bild featured); Schreie als OGG (cries.latest,
aus dem Repository PokeAPI/cries). Namen auf Deutsch aus pokemon-species.names.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional
from urllib.parse import urljoin

from .base import Adapter
from ..netz import GamegrabFehler

API = "https://pokeapi.co/api/v2/"
MAX_POKEDEX = 1025  # ohne Sonderformen (IDs ab 10001)


def _id(url: Optional[str]) -> Optional[int]:
    m = re.search(r"/(\d+)/?$", url or "")
    return int(m.group(1)) if m else None


def _name(eintraege, sprache: str, standard: str = "") -> str:
    for e in eintraege or []:
        if (e.get("language") or {}).get("name") == sprache:
            return e.get("name") or standard
    return standard


class Pokemon(Adapter):
    name = "pokemon"
    titel = "Pokémon"
    alter = "3–7"
    beschreibung = "Pokémon, Arten, Typen, Fähigkeiten, Attacken, Entwicklungen; Sprites, Artworks, Schreie (OGG). --typ fire,water filtert nach Typ"
    kategorien = {}  # --typ filtert hier nach Pokémon-Typ, z.B. --typ fire,water
    entitaeten = {
        "pokemon": ["id", "name", "name_en", "art", "generation", "typen", "faehigkeiten", "attacken",
                    "groesse_dm", "gewicht_hg", "basis_erfahrung", "datei", "artwork", "schrei"],
        "arten": ["id", "name", "name_en", "generation", "entwickelt_aus", "entwicklung_level", "legendaer",
                  "mystisch", "baby"],
        "typen": ["id", "name", "name_en", "doppelter_schaden_an", "halber_schaden_an", "kein_schaden_an"],
    }
    erlaubte_hosts = ("pokeapi.co", "raw.githubusercontent.com")
    quelle = "PokéAPI: https://pokeapi.co (Daten), https://github.com/PokeAPI/sprites und /cries (Bilder, Schreie)"
    lizenz = ("PokéAPI: freie Nutzung mit Fair-Use-Regeln (https://pokeapi.co/docs/v2#fairuse), Cache Pflicht.\n"
              "Pokémon und alle Namen, Bilder und Töne: © Nintendo, Creatures Inc., GAME FREAK inc., "
              "The Pokémon Company.")
    disclaimer = "Pokémon © Nintendo/Creatures Inc./GAME FREAK inc. Dies ist ein nicht offizielles Schulprojekt."
    anzahl_hinweis = "Anzahl Pokémon, Standard 20 (in Pokédex-Reihenfolge)"
    loesung_schema = {
        "generation": {"spalten": ["id", "name"], "pk": ["id"]},
        "art": {"spalten": ["id", "name", "name_en", "generation_id", "legendaer", "mystisch", "baby"], "pk": ["id"],
                "fk": {"generation_id": "generation.id"}},
        "pokemon": {"spalten": ["id", "name", "art_id", "groesse_dm", "gewicht_hg", "basis_erfahrung", "datei",
                                "artwork", "schrei"], "pk": ["id"], "fk": {"art_id": "art.id"}},
        "typ": {"spalten": ["id", "name", "name_en"], "pk": ["id"]},
        "faehigkeit": {"spalten": ["id", "name"], "pk": ["id"]},
        "attacke": {"spalten": ["id", "name"], "pk": ["id"]},
        "pokemon_typ": {"spalten": ["pokemon_id", "typ_id", "slot"], "pk": ["pokemon_id", "slot"],
                        "fk": {"pokemon_id": "pokemon.id", "typ_id": "typ.id"}},
        "pokemon_faehigkeit": {"spalten": ["pokemon_id", "faehigkeit_id", "versteckt"],
                               "pk": ["pokemon_id", "faehigkeit_id"],
                               "fk": {"pokemon_id": "pokemon.id", "faehigkeit_id": "faehigkeit.id"}},
        "pokemon_attacke": {"spalten": ["pokemon_id", "attacke_id", "lernart", "level"],
                            "pk": ["pokemon_id", "attacke_id", "lernart"],
                            "fk": {"pokemon_id": "pokemon.id", "attacke_id": "attacke.id"}},
        "entwicklung": {"spalten": ["von_art_id", "zu_art_id", "ausloeser", "min_level"],
                        "pk": ["von_art_id", "zu_art_id"], "fk": {"von_art_id": "art.id", "zu_art_id": "art.id"}},
        "typ_effektivitaet": {"spalten": ["angreifer_typ_id", "verteidiger_typ_id", "faktor"],
                              "pk": ["angreifer_typ_id", "verteidiger_typ_id"],
                              "fk": {"angreifer_typ_id": "typ.id", "verteidiger_typ_id": "typ.id"}},
    }

    def hole(self, opt, http, namen):
        anzahl = opt.anzahl or 20
        abs_url = lambda u: urljoin(API, u) if u else u  # noqa: E731

        # Typen (für Effektivität und optional als Filter --typ fire,water)
        typliste = http.get_json(urljoin(API, "type"), params={"limit": 50})
        typen: Dict[int, dict] = {}
        for t in typliste.get("results") or []:
            tid = _id(t.get("url"))
            if tid and tid <= 18:
                typen[tid] = http.get_json(abs_url(t["url"]))
        typ_nach_name = {t["name"]: tid for tid, t in typen.items()}

        if opt.typ:
            unbekannt = [t for t in opt.typ if t not in typ_nach_name]
            if unbekannt:
                raise GamegrabFehler("unbekannte Pokémon-Typen: " + ", ".join(unbekannt))
            kandidaten = sorted({_id(p["pokemon"]["url"]) for t in opt.typ for p in typen[typ_nach_name[t]].get("pokemon", [])
                                 if (_id(p["pokemon"]["url"]) or 99999) <= MAX_POKEDEX})
            urls = [urljoin(API, f"pokemon/{i}/") for i in kandidaten]
        else:
            limit = MAX_POKEDEX if opt.suche else anzahl
            liste = http.get_json(urljoin(API, "pokemon"), params={"limit": limit, "offset": 0})
            urls = [abs_url(r["url"]) for r in liste.get("results") or []
                    if not opt.suche or opt.suche.lower() in r.get("name", "")]
        urls = urls[:anzahl]

        zeilen, arten, ketten = [], {}, {}
        self._rel = {"pokemon_typ": [], "pokemon_faehigkeit": [], "pokemon_attacke": [], "entwicklung": []}
        self._faehigkeiten, self._attacken, self._generationen = {}, {}, {}
        for url in urls:
            p = http.get_json(url)
            s = http.get_json(abs_url(p["species"]["url"]))
            name_de = _name(s.get("names"), opt.sprache, p["name"])
            gen_id = _id((s.get("generation") or {}).get("url"))
            self._generationen[gen_id] = (s.get("generation") or {}).get("name")
            vorstufe = s.get("evolves_from_species")
            arten[s["id"]] = {"id": s["id"], "name": name_de, "name_en": _name(s.get("names"), "en", s["name"]),
                              "generation": (s.get("generation") or {}).get("name"), "generation_id": gen_id,
                              "entwickelt_aus": vorstufe["name"] if vorstufe else "", "entwicklung_level": "",
                              "legendaer": s.get("is_legendary"), "mystisch": s.get("is_mythical"),
                              "baby": s.get("is_baby")}
            kette = (s.get("evolution_chain") or {}).get("url")
            if kette:
                ketten[abs_url(kette)] = True
            stamm = f"{p['id']:04d}_{name_de}"
            sprites = p.get("sprites") or {}
            datei = artwork = schrei = ""
            if sprites.get("front_default"):
                datei = self.datei(namen, "sprites", stamm, "png", sprites["front_default"])
            art_url = (((sprites.get("other") or {}).get("official-artwork")) or {}).get("front_default")
            if opt.bild == "featured" and art_url:
                artwork = self.datei(namen, "artworks", stamm, "png", art_url)
            cry = (p.get("cries") or {}).get("latest")
            if cry:
                schrei = self.datei(namen, "schreie", stamm, "ogg", cry)

            for t in p.get("types") or []:
                self._rel["pokemon_typ"].append({"pokemon_id": p["id"], "typ_id": _id(t["type"]["url"]),
                                                 "slot": t.get("slot")})
            for a in p.get("abilities") or []:
                aid = _id(a["ability"]["url"])
                self._faehigkeiten[aid] = a["ability"]["name"]
                self._rel["pokemon_faehigkeit"].append({"pokemon_id": p["id"], "faehigkeit_id": aid,
                                                        "versteckt": a.get("is_hidden")})
            level_attacken = []
            for mv in p.get("moves") or []:
                details = mv.get("version_group_details") or []
                if not details:
                    continue
                neueste = max(_id(d["version_group"]["url"]) or 0 for d in details)
                mid = _id(mv["move"]["url"])
                self._attacken[mid] = mv["move"]["name"]
                gesehen = set()
                for d in details:
                    if (_id(d["version_group"]["url"]) or 0) != neueste:
                        continue
                    art = d["move_learn_method"]["name"]
                    if art in gesehen:
                        continue
                    gesehen.add(art)
                    self._rel["pokemon_attacke"].append({"pokemon_id": p["id"], "attacke_id": mid, "lernart": art,
                                                         "level": d.get("level_learned_at")})
                    if art == "level-up":
                        level_attacken.append((d.get("level_learned_at") or 0, mv["move"]["name"]))
            level_attacken.sort()
            zeilen.append({
                "id": p["id"], "name": name_de, "name_en": p["name"], "art": s["name"],
                "art_id": s["id"], "generation": (s.get("generation") or {}).get("name"),
                "typen": [t["type"]["name"] for t in sorted(p.get("types") or [], key=lambda t: t.get("slot", 0))],
                "faehigkeiten": [a["ability"]["name"] + (" (versteckt)" if a.get("is_hidden") else "")
                                 for a in p.get("abilities") or []],
                "attacken": [f"{n} ({lv})" for lv, n in level_attacken],
                "groesse_dm": p.get("height"), "gewicht_hg": p.get("weight"),
                "basis_erfahrung": p.get("base_experience"), "datei": datei, "artwork": artwork, "schrei": schrei})

        # Entwicklungen (rekursiv: Art -> Art)
        def gehe(knoten):
            von = _id(knoten["species"]["url"])
            for weiter in knoten.get("evolves_to") or []:
                zu = _id(weiter["species"]["url"])
                d = (weiter.get("evolution_details") or [{}])[0]
                self._rel["entwicklung"].append({"von_art_id": von, "zu_art_id": zu,
                                                 "ausloeser": (d.get("trigger") or {}).get("name"),
                                                 "min_level": d.get("min_level")})
                gehe(weiter)
        for url in ketten:
            gehe(http.get_json(url)["chain"])
        for e in self._rel["entwicklung"]:
            if e["zu_art_id"] in arten and e["min_level"]:
                arten[e["zu_art_id"]]["entwicklung_level"] = e["min_level"]

        typ_zeilen = []
        self._effekt = []
        for tid, t in sorted(typen.items()):
            rel = t.get("damage_relations") or {}
            typ_zeilen.append({"id": tid, "name": _name(t.get("names"), opt.sprache, t["name"]), "name_en": t["name"],
                               "doppelter_schaden_an": [x["name"] for x in rel.get("double_damage_to", [])],
                               "halber_schaden_an": [x["name"] for x in rel.get("half_damage_to", [])],
                               "kein_schaden_an": [x["name"] for x in rel.get("no_damage_to", [])]})
            for feld, faktor in (("double_damage_to", 2), ("half_damage_to", 0.5), ("no_damage_to", 0)):
                for x in rel.get(feld, []):
                    self._effekt.append({"angreifer_typ_id": tid, "verteidiger_typ_id": _id(x["url"]), "faktor": faktor})
        self._typ_ids = set(typen)
        return {"pokemon": zeilen, "arten": list(arten.values()), "typen": typ_zeilen}

    def loesung(self, daten, opt):
        arten = {a["id"] for a in daten["arten"]}
        pids = {p["id"] for p in daten["pokemon"]}
        tids = self._typ_ids
        return {
            "generation": [{"id": g, "name": n} for g, n in sorted(self._generationen.items()) if g],
            "art": daten["arten"],
            "pokemon": [dict(p) for p in daten["pokemon"]],
            "typ": daten["typen"],
            "faehigkeit": [{"id": i, "name": n} for i, n in sorted(self._faehigkeiten.items())],
            "attacke": [{"id": i, "name": n} for i, n in sorted(self._attacken.items())],
            "pokemon_typ": [r for r in self._rel["pokemon_typ"] if r["typ_id"] in tids and r["pokemon_id"] in pids],
            "pokemon_faehigkeit": self._rel["pokemon_faehigkeit"],
            "pokemon_attacke": self._rel["pokemon_attacke"],
            "entwicklung": [e for e in self._rel["entwicklung"] if e["von_art_id"] in arten and e["zu_art_id"] in arten],
            "typ_effektivitaet": [e for e in self._effekt if e["verteidiger_typ_id"] in tids],
        }
