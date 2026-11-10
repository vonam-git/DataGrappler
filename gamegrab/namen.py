"""Dateinamen und Pfade bereinigen - gleiche Regeln wie Durchblick (compressor.js, cleanSegment).

«Kaktus Kalle (Gold).PNG» -> «kaktus_kalle_gold.png»
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path, PurePosixPath

_ERSATZ = {
    "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss",
    "é": "e", "è": "e", "ê": "e", "à": "a", "ç": "c",
}


def bereinige(teil: str) -> str:
    """Einen Pfadteil für Datenbank und Linux tauglich machen."""
    s = unicodedata.normalize("NFC", str(teil))
    s = "".join(_ERSATZ.get(c, c) for c in s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9._-]+", "_", s)
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"^[_.-]+|[_-]+$", "", s)
    return s or "datei"


def sicherer_relpfad(pfad: str) -> str:
    """Relativen Pfad aus API-Daten entschärfen: kein '..', kein absoluter Pfad,
    keine Laufwerksbuchstaben, jeder Teil bereinigt."""
    teile = []
    for teil in str(pfad).replace("\\", "/").split("/"):
        if teil in ("", ".", ".."):
            continue
        if re.fullmatch(r"[A-Za-z]:", teil):
            continue
        teile.append(bereinige(teil))
    if not teile:
        raise ValueError(f"ungültiger Pfad: {pfad!r}")
    return "/".join(teile)


def liegt_in(basis: Path, ziel: Path) -> bool:
    """True, wenn ziel innerhalb von basis liegt (nach Auflösen von Links)."""
    basis = basis.resolve()
    try:
        ziel.resolve().relative_to(basis)
        return True
    except ValueError:
        return False


def endung_aus_url(url: str, standard: str = "") -> str:
    name = PurePosixPath(url.split("?", 1)[0]).name
    if "." in name:
        e = name.rsplit(".", 1)[1].lower()
        if re.fullmatch(r"[a-z0-9]{2,5}", e):
            return e
    return standard


class Dateinamen:
    """Vergibt eindeutige relative Dateipfade: kategorie/name.endung, bei Kollision _2, _3 …"""

    def __init__(self) -> None:
        self._vergeben: set[str] = set()

    def vergib(self, ordner: str, name: str, endung: str) -> str:
        ordner = sicherer_relpfad(ordner)
        basis = bereinige(name)
        endung = bereinige(endung or "bin")
        kandidat = f"{ordner}/{basis}.{endung}"
        n = 2
        while kandidat in self._vergeben:
            kandidat = f"{ordner}/{basis}_{n}.{endung}"
            n += 1
        self._vergeben.add(kandidat)
        return kandidat

    def freigeben(self, rel: str) -> None:
        self._vergeben.discard(rel)
