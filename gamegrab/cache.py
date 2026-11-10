"""Cache in .gamegrab-cache/: Listen (JSON/Text) 24 h, Dateien dauerhaft.

Damit lädt ein zweiter Lauf nichts neu, und ein abgebrochener Lauf setzt dort fort,
wo er aufgehört hat (bereits geladene Dateien liegen im Cache).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional, Tuple

LISTEN_TTL = 24 * 3600


def _schluessel(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Cache:
    def __init__(self, ordner: os.PathLike | str = ".gamegrab-cache") -> None:
        self.ordner = Path(ordner)

    # -- Listen -------------------------------------------------------------
    def _listenpfad(self, key: str) -> Path:
        return self.ordner / "listen" / (_schluessel(key) + ".json")

    def lies_liste(self, key: str, ttl: float = LISTEN_TTL) -> Optional[Any]:
        p = self._listenpfad(key)
        if not p.is_file():
            return None
        try:
            eintrag = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            return None
        if time.time() - eintrag.get("zeit", 0) > ttl:
            return None
        return eintrag.get("daten")

    def schreibe_liste(self, key: str, daten: Any) -> None:
        p = self._listenpfad(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"zeit": time.time(), "key": key, "daten": daten}, ensure_ascii=False), "utf-8")
        tmp.replace(p)

    # -- Dateien ------------------------------------------------------------
    def _dateipfad(self, key: str) -> Path:
        h = _schluessel(key)
        return self.ordner / "dateien" / h[:2] / h

    def lies_datei(self, key: str) -> Optional[Tuple[bytes, str]]:
        p = self._dateipfad(key)
        meta = p.with_suffix(".meta")
        if not (p.is_file() and meta.is_file()):
            return None
        try:
            endung = json.loads(meta.read_text("utf-8"))["endung"]
            return p.read_bytes(), endung
        except (OSError, ValueError, KeyError):
            return None

    def schreibe_datei(self, key: str, inhalt: bytes, endung: str) -> None:
        p = self._dateipfad(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(inhalt)
        tmp.replace(p)
        p.with_suffix(".meta").write_text(json.dumps({"key": key, "endung": endung}), "utf-8")
