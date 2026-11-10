"""Fussball mit echten Daten (EA Sports FC hat keine offene API).

Quellen:
- openfootball (Standard, CC0, ohne Schlüssel): Weltmeisterschaften (openfootball/worldcup.json)
  und Ligen (openfootball/football.json)
- football-data (optional): Schlüssel in FOOTBALL_DATA_TOKEN, Header X-Auth-Token, max. 10 Anfragen/Minute
- statsbomb (optional): StatsBomb Open Data auf GitHub, Ereignisse pro Spiel, Quellenangabe Pflicht

Datenschutz (nDSG): Spieler nur mit Name, Position, Nation, Verein. KEIN Geburtsdatum, keine Grösse,
kein Gewicht, keine Fotos. Keine echten Logos: Wappen werden selbst erzeugt (gamegrab.wappen).
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

from .base import Adapter, Erzeugt
from ..namen import bereinige
from ..netz import GamegrabFehler
from ..wappen import farben, hexfarbe, wappen_png

OPENFOOTBALL = "https://raw.githubusercontent.com/openfootball"
FOOTBALL_DATA = "https://api.football-data.org/v4"
STATSBOMB = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
STATSBOMB_TYPEN = {"Shot", "Substitution", "Foul Committed", "Bad Behaviour", "Own Goal Against", "Goal Keeper"}


def _minute(text) -> tuple:
    m = re.match(r"\s*(\d+)(?:\s*\+\s*(\d+))?", str(text or ""))
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2)) if m.group(2) else None


def _ergebnis(paar) -> tuple:
    if isinstance(paar, (list, tuple)) and len(paar) == 2:
        return paar[0], paar[1]
    return None, None


def _saison_liga(s: Optional[str]) -> str:
    if not s:
        return "2024-25"
    if re.fullmatch(r"\d{4}", s):
        return f"{s}-{(int(s) + 1) % 100:02d}"
    return s


class Modell:
    """Internes Modell, aus dem Rohform und Lösung entstehen."""

    def __init__(self, wettbewerb: str, saison: str) -> None:
        self.wettbewerb = {"id": 1, "name": wettbewerb, "saison": saison}
        self.teams: Dict[str, dict] = {}
        self.stadien: Dict[str, dict] = {}
        self.spieler: Dict[str, dict] = {}
        self.spiele: List[dict] = []
        self.tore: List[dict] = []
        self.ereignisse: List[dict] = []
        self.torschuetzen: List[dict] = []
        self.ist_wm = False

    def team(self, name: str) -> str:
        tid = bereinige(name)
        if tid not in self.teams:
            c1, c2, _ = farben(name)
            self.teams[tid] = {"id": tid, "name": name, "farbe1": hexfarbe(c1), "farbe2": hexfarbe(c2), "datei": ""}
        return tid

    def stadion(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        sid = bereinige(text)
        if sid not in self.stadien:
            name, _, stadt = text.partition(",")
            self.stadien[sid] = {"id": sid, "name": name.strip(), "stadt": stadt.strip()}
        return sid

    def person(self, name: str, team_id: Optional[str], position: str = "", nation: str = "",
               pid: Optional[str] = None) -> str:
        pid = pid or bereinige(name)
        if pid not in self.spieler:
            # bewusst nur Name, Position, Nation, Verein
            self.spieler[pid] = {"id": pid, "name": name, "position": position or "", "nation": nation or "",
                                 "verein_id": team_id or "", "verein": self.teams.get(team_id or "", {}).get("name", "")}
        return pid


class Fussball(Adapter):
    name = "fussball"
    titel = "Fussball (echte Daten)"
    alter = "– (echte Daten)"
    beschreibung = "Wettbewerbe, Vereine/Nationen, Spiele, Tore (openfootball, CC0); optional football-data, StatsBomb"
    kategorien = {}
    entitaeten = {
        "wettbewerb": ["id", "name", "saison"],
        "nationen": ["id", "name", "farbe1", "farbe2", "datei"],
        "vereine": ["id", "name", "farbe1", "farbe2", "datei"],
        "stadien": ["id", "name", "stadt"],
        "spiele": ["id", "datum", "zeit", "runde", "gruppe", "heim", "gast", "tore_heim", "tore_gast",
                   "halbzeit", "verlaengerung", "penaltyschiessen", "stadion"],
        "tore": ["spiel_id", "nr", "spieler", "team", "minute", "nachspielzeit", "penalty", "eigentor"],
        "spieler": ["id", "name", "position", "nation", "verein"],
        "torschuetzen": ["spieler", "verein", "tore", "vorlagen", "penaltys"],
        "ereignisse": ["spiel_id", "nr", "minute", "sekunde", "typ", "team", "spieler", "ergebnis"],
    }
    erlaubte_hosts = ("raw.githubusercontent.com", "api.football-data.org")
    anzahl_hinweis = "Anzahl Spiele (StatsBomb: Standard 3, wegen grosser Ereignisdateien)"
    loesung_schema = {
        "wettbewerb": {"spalten": ["id", "name", "saison"], "pk": ["id"]},
        "verein": {"spalten": ["id", "name", "wettbewerb_id", "farbe1", "farbe2", "datei"], "pk": ["id"],
                   "fk": {"wettbewerb_id": "wettbewerb.id"}},
        "stadion": {"spalten": ["id", "name", "stadt"], "pk": ["id"]},
        "spieler": {"spalten": ["id", "name", "position", "nation"], "pk": ["id"]},
        "vertrag": {"spalten": ["spieler_id", "verein_id", "saison"], "pk": ["spieler_id", "verein_id", "saison"],
                    "fk": {"spieler_id": "spieler.id", "verein_id": "verein.id"}},
        "spiel": {"spalten": ["id", "wettbewerb_id", "datum", "runde", "heim_verein_id", "gast_verein_id",
                              "stadion_id", "tore_heim", "tore_gast"], "pk": ["id"],
                  "fk": {"wettbewerb_id": "wettbewerb.id", "heim_verein_id": "verein.id",
                         "gast_verein_id": "verein.id", "stadion_id": "stadion.id"}},
        "tor": {"spalten": ["spiel_id", "nr", "spieler_id", "verein_id", "minute", "nachspielzeit", "penalty",
                            "eigentor"], "pk": ["spiel_id", "nr"],
                "fk": {"spiel_id": "spiel.id", "spieler_id": "spieler.id", "verein_id": "verein.id"}},
        "ereignis": {"spalten": ["spiel_id", "nr", "minute", "sekunde", "typ", "verein_id", "spieler_id", "ergebnis"],
                     "pk": ["spiel_id", "nr"],
                     "fk": {"spiel_id": "spiel.id", "verein_id": "verein.id", "spieler_id": "spieler.id"}},
    }

    quelle = "openfootball (CC0): https://github.com/openfootball"
    lizenz = "openfootball: CC0 1.0 (gemeinfrei)."
    disclaimer = ""

    def hole(self, opt, http, namen):
        q = (opt.quelle or "openfootball").lower()
        if q == "football-data":
            http.intervall = 6.0  # höchstens 10 Anfragen pro Minute
        if q == "openfootball":
            m = self._openfootball(opt, http)
            self.quelle = "openfootball (CC0): https://github.com/openfootball/worldcup.json bzw. /football.json"
            self.lizenz = "openfootball: CC0 1.0 Universal (gemeinfrei), ohne Schlüssel."
        elif q == "football-data":
            m = self._football_data(opt, http)
            self.quelle = "football-data.org API v4: https://www.football-data.org"
            self.lizenz = ("football-data.org: kostenloser Zugang (Free Tier) gemäss Nutzungsbedingungen "
                           "https://www.football-data.org/terms. Personendaten reduziert (nDSG).")
        elif q == "statsbomb":
            m = self._statsbomb(opt, http)
            self.quelle = "StatsBomb Open Data: https://github.com/statsbomb/open-data"
            self.lizenz = ("StatsBomb Open Data – Nutzung gemäss StatsBomb Public Data User Agreement "
                           "(https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf). "
                           "Quellenangabe Pflicht: «Data provided by StatsBomb».")
            self.disclaimer = "Data provided by StatsBomb."
        else:
            raise GamegrabFehler("unbekannte --quelle (openfootball, football-data, statsbomb)")
        self.melde(f"Quelle {q}: {m.wettbewerb['name']} (Saison {m.wettbewerb['saison']})")
        self.melde("Keine echten Logos: Wappen werden selbst erzeugt. Spieler nur mit Name/Position/Nation/Verein.")
        for t in m.teams.values():
            t["datei"] = self.datei(namen, "wappen", t["name"], "png", Erzeugt(wappen_png(t["name"]), "png"))
        self._modell = m
        daten = {
            "wettbewerb": [m.wettbewerb],
            ("nationen" if m.ist_wm else "vereine"): list(m.teams.values()),
            "stadien": list(m.stadien.values()),
            "spiele": m.spiele,
        }
        if m.tore:
            daten["tore"] = m.tore
        if m.spieler:
            daten["spieler"] = list(m.spieler.values())
        if m.torschuetzen:
            daten["torschuetzen"] = m.torschuetzen
        if m.ereignisse:
            daten["ereignisse"] = m.ereignisse
        return daten

    # -- openfootball ---------------------------------------------------------
    def _openfootball(self, opt, http) -> Modell:
        wb = (opt.wettbewerb or "wm").lower()
        if wb in ("wm", "worldcup", "wc"):
            saison = opt.saison or "2022"
            url = f"{OPENFOOTBALL}/worldcup.json/master/{saison}/worldcup.json"
        else:
            saison = _saison_liga(opt.saison)
            url = f"{OPENFOOTBALL}/football.json/master/{saison}/{wb}.json"
        try:
            roh = http.get_json(url)
        except GamegrabFehler as e:
            raise GamegrabFehler(f"openfootball hat keine Daten für {wb} {saison} ({e})") from e
        m = Modell(roh.get("name") or wb, saison)
        m.ist_wm = wb in ("wm", "worldcup", "wc")
        spiele = roh.get("matches") or []
        if not spiele and roh.get("rounds"):  # älteres Format
            spiele = [dict(s, round=r.get("name")) for r in roh["rounds"] for s in r.get("matches", [])]
        if opt.anzahl:
            spiele = spiele[: opt.anzahl]
        for nr, s in enumerate(spiele, 1):
            sid = f"s{nr}"
            heim = s.get("team1") if isinstance(s.get("team1"), str) else (s.get("team1") or {}).get("name")
            gast = s.get("team2") if isinstance(s.get("team2"), str) else (s.get("team2") or {}).get("name")
            if not heim or not gast:
                continue
            h, g = m.team(heim), m.team(gast)
            score = s.get("score") or {}
            if isinstance(score, list):  # Kurzform [heim, gast]
                score = {"ft": score}
            ft = _ergebnis(score.get("ft"))
            if ft == (None, None) and "score1" in s:
                ft = (s.get("score1"), s.get("score2"))
            ht = _ergebnis(score.get("ht"))
            et = _ergebnis(score.get("et"))
            p = _ergebnis(score.get("p"))
            m.spiele.append({
                "id": sid, "datum": s.get("date"), "zeit": s.get("time"), "runde": s.get("round"),
                "gruppe": s.get("group"), "heim": heim, "gast": gast, "heim_id": h, "gast_id": g,
                "tore_heim": et[0] if et[0] is not None else ft[0],
                "tore_gast": et[1] if et[1] is not None else ft[1],
                "halbzeit": f"{ht[0]}:{ht[1]}" if ht[0] is not None else "",
                "verlaengerung": et[0] is not None, "penaltyschiessen": f"{p[0]}:{p[1]}" if p[0] is not None else "",
                "stadion": (s.get("ground") or ""), "stadion_id": m.stadion(s.get("ground"))})
            tor_nr = 0
            for seite, team_id, gegner_id in (("goals1", h, g), ("goals2", g, h)):
                for t in s.get(seite) or []:
                    tor_nr += 1
                    eigentor = bool(t.get("owngoal"))
                    schuetze_team = gegner_id if eigentor else team_id
                    pid = m.person(t.get("name") or "unbekannt", schuetze_team,
                                   nation=m.teams[schuetze_team]["name"] if wb in ("wm", "worldcup", "wc") else "")
                    minute, nachspiel = _minute(t.get("minute"))
                    m.tore.append({"spiel_id": sid, "nr": tor_nr, "spieler": t.get("name"), "spieler_id": pid,
                                   "team": m.teams[team_id]["name"], "team_id": team_id, "minute": minute,
                                   "nachspielzeit": nachspiel or t.get("offset"), "penalty": bool(t.get("penalty")),
                                   "eigentor": eigentor})
        m.tore.sort(key=lambda t: (int(t["spiel_id"][1:]), t["minute"] or 0, t["nachspielzeit"] or 0))
        zaehler: Dict[str, int] = {}
        for t in m.tore:
            zaehler[t["spiel_id"]] = zaehler.get(t["spiel_id"], 0) + 1
            t["nr"] = zaehler[t["spiel_id"]]
        return m

    # -- football-data ---------------------------------------------------------
    def _football_data(self, opt, http) -> Modell:
        token = os.environ.get("FOOTBALL_DATA_TOKEN")
        if not token:
            raise GamegrabFehler("Für --quelle football-data die Umgebungsvariable FOOTBALL_DATA_TOKEN setzen "
                                 "(kostenloser Schlüssel auf football-data.org).")
        kopf = {"X-Auth-Token": token}
        code = (opt.wettbewerb or "PL").upper()
        if code == "WM":
            code = "WC"
        params = {"season": opt.saison[:4]} if opt.saison else None
        teams = http.get_json(f"{FOOTBALL_DATA}/competitions/{code}/teams", params=params, headers=kopf)
        spiele = http.get_json(f"{FOOTBALL_DATA}/competitions/{code}/matches", params=params, headers=kopf)
        schuetzen = http.get_json(f"{FOOTBALL_DATA}/competitions/{code}/scorers", params=params, headers=kopf)
        saison = str((teams.get("season") or {}).get("startDate", opt.saison or ""))[:4]
        m = Modell((teams.get("competition") or {}).get("name") or code, saison)
        m.ist_wm = code == "WC"
        ids: Dict[int, str] = {}
        for t in teams.get("teams") or []:
            tid = m.team(t.get("name") or str(t.get("id")))
            ids[t.get("id")] = tid
            m.stadion(t.get("venue"))
            for p in t.get("squad") or []:  # dateOfBirth u.a. werden bewusst verworfen
                m.person(p.get("name") or "unbekannt", tid, p.get("position") or "", p.get("nationality") or "",
                         pid=f"p{p.get('id')}")
        liste = spiele.get("matches") or []
        if opt.anzahl:
            liste = liste[: opt.anzahl]
        for s in liste:
            h = ids.get((s.get("homeTeam") or {}).get("id")) or m.team((s.get("homeTeam") or {}).get("name") or "?")
            g = ids.get((s.get("awayTeam") or {}).get("id")) or m.team((s.get("awayTeam") or {}).get("name") or "?")
            ft = (s.get("score") or {}).get("fullTime") or {}
            ht = (s.get("score") or {}).get("halfTime") or {}
            m.spiele.append({
                "id": f"m{s.get('id')}", "datum": (s.get("utcDate") or "")[:10], "zeit": (s.get("utcDate") or "")[11:16],
                "runde": s.get("matchday") or s.get("stage"), "gruppe": s.get("group"),
                "heim": m.teams[h]["name"], "gast": m.teams[g]["name"], "heim_id": h, "gast_id": g,
                "tore_heim": ft.get("home"), "tore_gast": ft.get("away"),
                "halbzeit": f"{ht.get('home')}:{ht.get('away')}" if ht.get("home") is not None else "",
                "verlaengerung": (s.get("score") or {}).get("duration") == "EXTRA_TIME", "penaltyschiessen": "",
                "stadion": "", "stadion_id": None})
        for e in schuetzen.get("scorers") or []:
            p, t = e.get("player") or {}, e.get("team") or {}
            tid = ids.get(t.get("id")) or m.team(t.get("name") or "?")
            m.person(p.get("name") or "unbekannt", tid, p.get("position") or p.get("section") or "",
                     p.get("nationality") or "", pid=f"p{p.get('id')}")
            m.torschuetzen.append({"spieler": p.get("name"), "spieler_id": f"p{p.get('id')}",
                                   "verein": m.teams[tid]["name"], "tore": e.get("goals"),
                                   "vorlagen": e.get("assists"), "penaltys": e.get("penalties")})
        return m

    # -- StatsBomb ---------------------------------------------------------------
    def _statsbomb(self, opt, http) -> Modell:
        comps = http.get_json(f"{STATSBOMB}/competitions.json")
        wb = (opt.wettbewerb or "wm").lower()
        name = "FIFA World Cup" if wb in ("wm", "worldcup", "wc") else opt.wettbewerb
        saison = opt.saison or "2022"
        treffer = [c for c in comps if (c.get("competition_name") or "").lower() == (name or "").lower()
                   or str(c.get("competition_id")) == wb]
        treffer = [c for c in treffer if str(c.get("season_name")) == saison] or []
        if not treffer:
            raise GamegrabFehler(f"StatsBomb hat keine offenen Daten für {name} {saison}")
        c = treffer[0]
        spiele = http.get_json(f"{STATSBOMB}/matches/{c['competition_id']}/{c['season_id']}.json")
        spiele.sort(key=lambda s: (s.get("match_date") or "", s.get("kick_off") or ""))
        spiele = spiele[: opt.anzahl or 3]
        m = Modell(c.get("competition_name"), str(c.get("season_name")))
        m.ist_wm = "world cup" in (c.get("competition_name") or "").lower()
        for s in spiele:
            h = m.team((s.get("home_team") or {}).get("home_team_name") or "?")
            g = m.team((s.get("away_team") or {}).get("away_team_name") or "?")
            st = s.get("stadium") or {}
            sid = f"m{s['match_id']}"
            m.spiele.append({
                "id": sid, "datum": s.get("match_date"), "zeit": (s.get("kick_off") or "")[:5],
                "runde": (s.get("competition_stage") or {}).get("name"), "gruppe": "",
                "heim": m.teams[h]["name"], "gast": m.teams[g]["name"], "heim_id": h, "gast_id": g,
                "tore_heim": s.get("home_score"), "tore_gast": s.get("away_score"), "halbzeit": "",
                "verlaengerung": False, "penaltyschiessen": "", "stadion": st.get("name") or "",
                "stadion_id": m.stadion(st.get("name"))})
            ereignisse = http.get_json(f"{STATSBOMB}/events/{s['match_id']}.json")
            nr = tor_nr = 0
            for e in ereignisse:
                typ = (e.get("type") or {}).get("name")
                if typ not in STATSBOMB_TYPEN:
                    continue
                team = m.team((e.get("team") or {}).get("name") or "?")
                spieler = e.get("player") or {}
                pid = m.person(spieler["name"], team, (e.get("position") or {}).get("name") or "",
                               m.teams[team]["name"] if m.ist_wm else "",
                               pid=f"p{spieler['id']}") if spieler.get("name") else None
                ergebnis = ((e.get("shot") or {}).get("outcome") or {}).get("name") or \
                           ((e.get("foul_committed") or {}).get("card") or {}).get("name") or ""
                nr += 1
                m.ereignisse.append({"spiel_id": sid, "nr": nr, "minute": e.get("minute"), "sekunde": e.get("second"),
                                     "typ": typ, "team": m.teams[team]["name"], "team_id": team,
                                     "spieler": spieler.get("name") or "", "spieler_id": pid, "ergebnis": ergebnis})
                if typ == "Shot" and ergebnis == "Goal" and e.get("period", 1) <= 4:
                    tor_nr += 1
                    m.tore.append({"spiel_id": sid, "nr": tor_nr, "spieler": spieler.get("name"), "spieler_id": pid,
                                   "team": m.teams[team]["name"], "team_id": team, "minute": e.get("minute"),
                                   "nachspielzeit": None,
                                   "penalty": ((e.get("shot") or {}).get("type") or {}).get("name") == "Penalty",
                                   "eigentor": False})
        return m

    def quellen_text(self, opt):
        return ("Datenschutz: Spielerdaten sind Personendaten (nDSG). Gespeichert werden nur Name, Position, "
                "Nation und Verein – keine Geburtsdaten, Grössen, Gewichte oder Fotos.\n"
                "Wappen: selbst erzeugt (zwei Farbflächen aus einem Hash des Namens), keine echten Logos.")

    def loesung(self, daten, opt):
        m = self._modell
        saison = m.wettbewerb["saison"]
        vereine = [{"id": t["id"], "name": t["name"], "wettbewerb_id": 1, "farbe1": t["farbe1"],
                    "farbe2": t["farbe2"], "datei": t["datei"]} for t in m.teams.values()]
        spieler = [{"id": p["id"], "name": p["name"], "position": p["position"], "nation": p["nation"]}
                   for p in m.spieler.values()]
        vertraege = sorted({(p["id"], p["verein_id"]) for p in m.spieler.values() if p["verein_id"]})
        return {
            "wettbewerb": [m.wettbewerb],
            "verein": vereine,
            "stadion": list(m.stadien.values()),
            "spieler": spieler,
            "vertrag": [{"spieler_id": s, "verein_id": v, "saison": saison} for s, v in vertraege],
            "spiel": [{"id": s["id"], "wettbewerb_id": 1, "datum": s["datum"], "runde": s["runde"],
                       "heim_verein_id": s["heim_id"], "gast_verein_id": s["gast_id"], "stadion_id": s["stadion_id"],
                       "tore_heim": s["tore_heim"], "tore_gast": s["tore_gast"]} for s in m.spiele],
            "tor": [{"spiel_id": t["spiel_id"], "nr": t["nr"], "spieler_id": t["spieler_id"], "verein_id": t["team_id"],
                     "minute": t["minute"], "nachspielzeit": t["nachspielzeit"], "penalty": t["penalty"],
                     "eigentor": t["eigentor"]} for t in m.tore],
            "ereignis": [{"spiel_id": e["spiel_id"], "nr": e["nr"], "minute": e["minute"], "sekunde": e["sekunde"],
                          "typ": e["typ"], "verein_id": e["team_id"], "spieler_id": e["spieler_id"],
                          "ergebnis": e["ergebnis"]} for e in m.ereignisse],
        }
