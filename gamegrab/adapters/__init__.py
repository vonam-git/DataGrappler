"""Adapter-Register. Jede Datei in diesem Ordner (ausser base.py) wird automatisch geladen;
jede darin definierte Unterklasse von Adapter mit gesetztem `name` ist danach verfügbar."""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Dict

from .base import Adapter

_REIHENFOLGE = ["fortnite", "minecraft", "fussball", "pokemon", "gtav", "valorant", "mtg"]


def alle_adapter() -> Dict[str, Adapter]:
    gefunden: Dict[str, Adapter] = {}
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_") or info.name == "base":
            continue
        modul = importlib.import_module(f"{__name__}.{info.name}")
        for _, klasse in inspect.getmembers(modul, inspect.isclass):
            if issubclass(klasse, Adapter) and klasse is not Adapter and klasse.__module__ == modul.__name__ and klasse.name:
                gefunden[klasse.name] = klasse()
    rang = {n: i for i, n in enumerate(_REIHENFOLGE)}
    return dict(sorted(gefunden.items(), key=lambda kv: (rang.get(kv[0], 99), kv[0])))


def hole_adapter(name: str) -> Adapter:
    adapter = alle_adapter()
    if name not in adapter:
        raise KeyError(name)
    return adapter[name]
