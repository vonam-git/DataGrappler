"""Basisklasse für Adapter. Ein Adapter weiss nur, wie «seine» Quelle aussieht.

Kern, Cache, Sicherheitsregeln und Ausgabeformat sind für alle Spiele gleich.
Ein neues Spiel = eine neue Datei in gamegrab/adapters/ mit einer Unterklasse von Adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from ..namen import Dateinamen
from ..netz import HttpClient


@dataclass
class Optionen:
    typ: List[str] = field(default_factory=list)
    anzahl: Optional[int] = None
    seltenheit: List[str] = field(default_factory=list)
    neu_seit: Optional[date] = None
    suche: Optional[str] = None
    bild: str = "small"
    sprache: str = "de"
    max_mb: float = 50.0
    lokal: Optional[str] = None
    quelle: Optional[str] = None
    wettbewerb: Optional[str] = None
    saison: Optional[str] = None
    spielversion: Optional[str] = None
    normalisiert: bool = False
    ziel: Optional[str] = None
    zip: bool = False


# --- Herkunft einer Datei ------------------------------------------------------
@dataclass(frozen=True)
class LokaleDatei:
    """Datei aus der eigenen Installation (z.B. Minecraft-Töne)."""
    pfad: str


@dataclass(frozen=True)
class ZipEintrag:
    """Eintrag in einem ZIP/JAR der eigenen Installation (z.B. Minecraft-Texturen)."""
    archiv: str
    eintrag: str


@dataclass(frozen=True)
class Erzeugt:
    """Vom Tool selbst erzeugte Datei (z.B. Fussball-Wappen)."""
    inhalt: bytes
    endung: str


Herkunft = Union[str, LokaleDatei, ZipEintrag, Erzeugt]
Daten = Dict[str, List[Dict[str, Any]]]
# Lösungsschema: tabelle -> {"spalten": [...], "pk": [...], "fk": {spalte: "tabelle.spalte"}}
Schema = Dict[str, Dict[str, Any]]


class Adapter:
    name: str = ""                       # CLI-Name, z.B. "fortnite"
    titel: str = ""                      # Anzeigename
    alter: str = ""                      # PEGI-Einstufung
    beschreibung: str = ""
    entitaeten: Dict[str, List[str]] = {}  # Rohform: Entität -> Spalten (CSV)
    kategorien: Dict[str, str] = {}      # Wert von --typ -> Ordnername
    erlaubte_hosts: Tuple[str, ...] = ()
    rate: float = 2.0                    # Anfragen pro Sekunde (höchstens 2)
    quelle: str = ""
    lizenz: str = ""
    disclaimer: str = ""
    hinweise: Tuple[str, ...] = ()       # bei jedem Lauf ausgeben
    anzahl_hinweis: str = "pro Typ"
    json_name: str = "daten.json"
    geruest: bool = False                # True = nur dokumentiertes Gerüst
    loesung_schema: Schema = {}

    def __init__(self) -> None:
        self._dateien: List[Tuple[str, Herkunft]] = []
        self.meldungen: List[str] = []

    # -- Hilfen für Unterklassen --
    def datei(self, namen: Dateinamen, ordner: str, name: str, endung: str, herkunft: Herkunft) -> str:
        rel = namen.vergib(ordner, name, endung)
        self._dateien.append((rel, herkunft))
        return rel

    def melde(self, text: str) -> None:
        self.meldungen.append(text)

    # -- Schnittstelle --
    def hole(self, opt: Optionen, http: HttpClient, namen: Dateinamen) -> Daten:
        """Liste laden, filtern, Zeilen pro Entität zurückgeben. Registriert Dateien mit self.datei()."""
        raise NotImplementedError

    def dateien(self, opt: Optionen) -> Iterable[Tuple[str, Herkunft]]:
        """(relativer_pfad, url_oder_lokale_herkunft) aller zu ladenden Dateien."""
        return list(self._dateien)

    def loesung(self, daten: Daten, opt: Optionen) -> Daten:
        """Normalisierte Tabellen (Lösung für die Lehrperson). Spalten gemäss loesung_schema."""
        return {}

    def quellen_text(self, opt: Optionen) -> str:
        """Zusatztext für QUELLEN.txt (z.B. je nach --quelle)."""
        return ""


# --- kleine Hilfen -------------------------------------------------------------
def kuerze(text: Any, laenge: int = 300) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= laenge else s[: laenge - 1].rstrip() + "…"


class IdVergabe:
    """Vergibt fortlaufende Ganzzahl-IDs für Werte (z.B. Seltenheit 'rare' -> 3)."""

    def __init__(self) -> None:
        self.ids: Dict[Any, int] = {}

    def __call__(self, wert: Any) -> Optional[int]:
        if wert in (None, ""):
            return None
        if wert not in self.ids:
            self.ids[wert] = len(self.ids) + 1
        return self.ids[wert]

    def zeilen(self, spalte: str = "name") -> List[Dict[str, Any]]:
        return [{"id": i, spalte: w} for w, i in self.ids.items()]
