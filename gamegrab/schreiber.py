"""Ausgabe schreiben: CSV pro Entität (Rohform), JSON, QUELLEN.txt, .gitignore,
optional _loesung/ mit Beziehungstabellen und ERD (Mermaid)."""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .adapters.base import Adapter, Daten, Optionen, Schema

HINWEIS = "Nur für den Unterricht, nicht veröffentlichen."


def zellwert(wert: Any) -> str:
    """Mehrwertige Felder bewusst in EINER Zelle, mit «|» getrennt."""
    if wert is None:
        return ""
    if isinstance(wert, bool):
        return "1" if wert else "0"
    if isinstance(wert, (list, tuple)):
        return "|".join(zellwert(w) for w in wert if w not in (None, ""))
    if isinstance(wert, float) and wert.is_integer():
        return str(int(wert))
    return str(wert)


def csv_text(spalten: List[str], zeilen: Iterable[Dict[str, Any]]) -> str:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w.writerow(spalten)
    for z in zeilen:
        w.writerow([zellwert(z.get(s)) for s in spalten])
    return puffer.getvalue()


def schreibe_csv(pfad: Path, spalten: List[str], zeilen: Iterable[Dict[str, Any]]) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(csv_text(spalten, zeilen).encode("utf-8"))  # \n, auch unter Windows


def schreibe_rohform(ziel: Path, adapter: Adapter, daten: Daten) -> List[Path]:
    geschrieben = []
    for entitaet, zeilen in daten.items():
        spalten = adapter.entitaeten.get(entitaet)
        if spalten is None:
            spalten = list(zeilen[0].keys()) if zeilen else ["id", "name"]
        p = ziel / f"{entitaet}.csv"
        schreibe_csv(p, spalten, zeilen)
        geschrieben.append(p)
    return geschrieben


def schreibe_json(ziel: Path, adapter: Adapter, daten: Daten, abgerufen: datetime, opt: Optionen) -> Path:
    inhalt = {
        "spiel": adapter.titel,
        "quelle": adapter.quelle,
        "abgerufen_am": abgerufen.isoformat(timespec="seconds"),
        "disclaimer": adapter.disclaimer,
        "lizenz": adapter.lizenz,
        "hinweis": HINWEIS,
        "optionen": _optionen_text(opt),
        "entitaeten": daten,
    }
    p = ziel / adapter.json_name
    p.write_text(json.dumps(inhalt, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")
    return p


def _optionen_text(opt: Optionen) -> Dict[str, Any]:
    d = {}
    for k, v in vars(opt).items():
        if v in (None, [], False, ""):
            continue
        d[k] = v.isoformat() if hasattr(v, "isoformat") else v
    return d


def schreibe_quellen(ziel: Path, adapter: Adapter, abgerufen: datetime, opt: Optionen) -> Path:
    zeilen = [
        f"QUELLEN – {adapter.titel}",
        "=" * 60,
        "",
        f"Erzeugt mit: gamegrab (Rohdaten-Sammler für Durchblick, Modul 141)",
        f"Abgerufen am: {abgerufen.strftime('%Y-%m-%d %H:%M')}",
        f"Altersfreigabe: {adapter.alter}",
        f"Aufruf: gamegrab {adapter.name} " + " ".join(f"--{k.replace('_', '-')} {v}" for k, v in _optionen_text(opt).items()),
        "",
        "Quelle",
        "------",
        adapter.quelle,
        "",
        "Lizenz / Richtlinie des Herstellers",
        "-----------------------------------",
        adapter.lizenz,
    ]
    extra = adapter.quellen_text(opt)
    if extra:
        zeilen += ["", extra]
    if adapter.disclaimer:
        zeilen += ["", "Disclaimer", "----------", adapter.disclaimer]
    zeilen += [
        "",
        "Wichtig",
        "-------",
        f"{HINWEIS}",
        "Die Bilder und Töne gehören den jeweiligen Firmen. Sie wurden nur für den",
        "Unterricht heruntergeladen. Rohdaten und daraus erzeugte CSV-Dateien gehören",
        "nicht in ein öffentliches Repository. Dies ist keine Rechtsberatung.",
        "",
    ]
    p = ziel / "QUELLEN.txt"
    p.write_text("\n".join(zeilen), encoding="utf-8")
    return p


def schreibe_gitignore(ziel: Path) -> None:
    (ziel / ".gitignore").write_text(
        "# Rohdaten nie committen (Urheberrecht). Erzeugt von gamegrab.\n*\n", encoding="utf-8")


# --- Lösung -----------------------------------------------------------------
class FremdschluesselFehler(Exception):
    pass


def pruefe_fremdschluessel(schema: Schema, tabellen: Daten) -> None:
    """Jeder Fremdschlüssel muss auf eine existierende ID verweisen (leer = NULL ist erlaubt)."""
    vorhanden: Dict[str, set] = {}
    for name, zeilen in tabellen.items():
        for spalte in schema.get(name, {}).get("spalten", []):
            vorhanden.setdefault(f"{name}.{spalte}", {zellwert(z.get(spalte)) for z in zeilen})
    fehler = []
    for name, info in schema.items():
        for spalte, ziel in info.get("fk", {}).items():
            erlaubt = vorhanden.get(ziel, set())
            for z in tabellen.get(name, []):
                w = zellwert(z.get(spalte))
                if w and w not in erlaubt:
                    fehler.append(f"{name}.{spalte}={w} -> {ziel} fehlt")
        pk = info.get("pk")
        if pk:
            gesehen = set()
            for z in tabellen.get(name, []):
                schluessel = tuple(zellwert(z.get(s)) for s in pk)
                if schluessel in gesehen:
                    fehler.append(f"{name}: Primärschlüssel {schluessel} doppelt")
                gesehen.add(schluessel)
    if fehler:
        raise FremdschluesselFehler("; ".join(fehler[:10]) + (" …" if len(fehler) > 10 else ""))


def _typ(werte: List[str]) -> str:
    werte = [w for w in werte if w != ""]
    if not werte:
        return "string"
    try:
        for w in werte:
            int(w)
        return "int"
    except ValueError:
        pass
    try:
        for w in werte:
            float(w)
        return "float"
    except ValueError:
        return "string"


def erd_mermaid(schema: Schema, tabellen: Daten, titel: str) -> str:
    z = [f"# ERD – {titel} (Lösung)", "",
         "Automatisch aus den Tabellen in `_loesung/` erzeugt. Darstellbar z.B. auf GitHub oder mermaid.live.", "",
         "```mermaid", "erDiagram"]
    for name, info in schema.items():
        zeilen = tabellen.get(name, [])
        z.append(f"    {name.upper()} {{")
        fks = info.get("fk", {})
        pk = info.get("pk", [])
        for s in info["spalten"]:
            marken = []
            if s in pk:
                marken.append("PK")
            if s in fks:
                marken.append("FK")
            typ = _typ([zellwert(r.get(s)) for r in zeilen[:200]])
            z.append(f"        {typ} {s}{(' ' + ','.join(marken)) if marken else ''}")
        z.append("    }")
    for name, info in schema.items():
        for spalte, ziel in info.get("fk", {}).items():
            eltern = ziel.split(".")[0]
            z.append(f'    {eltern.upper()} ||--o{{ {name.upper()} : "{spalte}"')
    z += ["```", ""]
    return "\n".join(z)


def schreibe_loesung(ziel: Path, adapter: Adapter, tabellen: Daten) -> Path:
    ordner = ziel / "_loesung"
    schema = adapter.loesung_schema
    pruefe_fremdschluessel(schema, tabellen)
    for name, info in schema.items():
        schreibe_csv(ordner / f"{name}.csv", info["spalten"], tabellen.get(name, []))
    (ordner / "erd.md").write_text(erd_mermaid(schema, tabellen, adapter.titel), encoding="utf-8")
    return ordner


def schreibe_zip(ziel: Path) -> Path:
    zpfad = ziel.with_suffix(".zip") if ziel.suffix == "" else ziel.parent / (ziel.name + ".zip")
    with zipfile.ZipFile(zpfad, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ziel.rglob("*")):
            if p.is_file():
                z.write(p, Path(ziel.name) / p.relative_to(ziel))
    return zpfad
