"""Kommandozeile: gamegrab liste | gamegrab <spiel> [optionen]"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import List, Optional

from . import __version__
from .adapters import alle_adapter
from .adapters.base import Optionen
from .kern import ausfuehren
from .netz import GamegrabFehler
from .schreiber import FremdschluesselFehler


def _liste(text: Optional[str]) -> List[str]:
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def _datum(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Datum im Format JJJJ-MM-TT erwartet, nicht {text!r}")


def _optionen_hinzufuegen(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("Auswahl")
    g.add_argument("--typ", help="Kategorien/Typen, mit Komma getrennt (siehe «gamegrab liste»)")
    g.add_argument("--anzahl", type=int, help="höchstens so viele Einträge (je nach Spiel pro Typ)")
    g.add_argument("--seltenheit", help="nur diese Seltenheit(en), z.B. legendary")
    g.add_argument("--neu-seit", type=_datum, metavar="DATUM", help="nur Einträge, die seit diesem Datum dazukamen")
    g.add_argument("--suche", metavar="TEXT", help="Namenssuche (Teil des Namens)")
    g.add_argument("--sprache", default="de", help="Sprache der Namen, Standard de")
    g.add_argument("--bild", choices=["small", "icon", "featured"], default="small",
                   help="Bildvariante, Standard small (spart Platz)")
    g.add_argument("--lokal", nargs="?", const="auto", metavar="PFAD",
                   help="Minecraft: Texturen/Töne aus der eigenen Installation lesen (Standardpfad, falls leer)")
    g.add_argument("--spielversion", metavar="V", help="Minecraft: Java-Version, Standard die neueste")
    g.add_argument("--quelle", help="Fussball: openfootball (Standard), football-data oder statsbomb")
    g.add_argument("--wettbewerb", help="Fussball: wm (Standard), en.1, de.1 … bzw. PL, BL1 … bei football-data")
    g.add_argument("--saison", help="Fussball: z.B. 2022 (WM) oder 2024-25 (Liga)")
    a = p.add_argument_group("Ausgabe")
    a.add_argument("--normalisiert", action="store_true",
                   help="zusätzlich _loesung/ mit Beziehungstabellen und ERD (für die Lehrperson)")
    a.add_argument("--ziel", metavar="ORDNER", help="Ausgabeordner, Standard ./rohdaten/<spiel>_<datum>/")
    a.add_argument("--zip", action="store_true", help="zusätzlich als ZIP ablegen")
    a.add_argument("--max-mb", type=float, default=50.0, help="Obergrenze für den Ordner in MB, Standard 50")
    a.add_argument("--cache", default=".gamegrab-cache", help="Cache-Ordner, Standard .gamegrab-cache")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gamegrab",
        description="Rohdaten-Sammler für die Durchblick-Werkstatt (Modul 141). Holt Spieldaten aus offenen Quellen.",
        epilog="Beispiel: gamegrab fortnite --typ outfit,backpack,emote --anzahl 20 --sprache de")
    p.add_argument("--version", action="version", version=f"gamegrab {__version__}")
    sub = p.add_subparsers(dest="befehl", metavar="BEFEHL")
    sub.add_parser("liste", help="verfügbare Spiele, Kategorien und Altersfreigaben anzeigen")
    for name, ad in alle_adapter().items():
        sp = sub.add_parser(name, help=f"{ad.titel} (PEGI {ad.alter})" + (" – Gerüst" if ad.geruest else ""),
                            description=ad.beschreibung)
        _optionen_hinzufuegen(sp)
    return p


def zeige_liste() -> None:
    for name, ad in alle_adapter().items():
        status = "  [Gerüst]" if ad.geruest else ""
        print(f"\n{name:<10} {ad.titel} · PEGI {ad.alter}{status}")
        print(f"           {ad.beschreibung}")
        if len(ad.kategorien) > 8:
            print("           --typ:      " + ", ".join(ad.kategorien))
        elif ad.kategorien:
            print("           --typ:      " + ", ".join(f"{k}->{v}/" for k, v in ad.kategorien.items()))
        print("           Entitäten:  " + ", ".join(ad.entitaeten))
        print(f"           --anzahl:   {ad.anzahl_hinweis}")
    print()


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    args = parser().parse_args(argv)
    if args.befehl in (None, "liste"):
        zeige_liste()
        return 0
    adapter = alle_adapter()[args.befehl]
    opt = Optionen(
        typ=_liste(args.typ), anzahl=args.anzahl, seltenheit=_liste(args.seltenheit), neu_seit=args.neu_seit,
        suche=args.suche, bild=args.bild, sprache=args.sprache, max_mb=args.max_mb, lokal=args.lokal,
        quelle=args.quelle, wettbewerb=args.wettbewerb, saison=args.saison, spielversion=args.spielversion,
        normalisiert=args.normalisiert, ziel=args.ziel, zip=args.zip)
    if opt.anzahl is not None and opt.anzahl < 1:
        print("Fehler: --anzahl muss mindestens 1 sein.", file=sys.stderr)
        return 2
    try:
        ausfuehren(adapter, opt, cache_ordner=args.cache)
    except (GamegrabFehler, FremdschluesselFehler) as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAbgebrochen. Ein neuer Lauf setzt dank Cache fort.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
