"""Einfache Wappen als PNG (128x128) selbst erzeugen – statt echter, geschützter Vereinslogos.

Zwei Farbflächen in Schildform, Farben und Muster aus einem Hash des Namens, ohne Text.
Nur Standardbibliothek (zlib + struct)."""
from __future__ import annotations

import colorsys
import hashlib
import struct
import zlib
from typing import Tuple

GROESSE = 128


def farben(name: str) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], int]:
    h = hashlib.sha256(name.encode("utf-8")).digest()
    ton1 = h[0] / 255
    ton2 = (ton1 + 0.33 + (h[1] / 255) * 0.34) % 1.0
    hell2 = 0.25 if h[2] % 2 else 0.92
    c1 = colorsys.hsv_to_rgb(ton1, 0.55 + h[3] / 255 * 0.4, 0.55 + h[4] / 255 * 0.4)
    c2 = colorsys.hsv_to_rgb(ton2, 0.2 if hell2 > 0.9 else 0.6, hell2)
    return tuple(int(x * 255) for x in c1), tuple(int(x * 255) for x in c2), h[5] % 4


def hexfarbe(rgb: Tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _im_schild(x: float, y: float) -> bool:
    # x, y in 0..1; oben gerade, unten spitz zulaufend
    rand = 0.1
    if y < 0.06 or y > 0.96:
        return False
    if y < 0.6:
        return rand <= x <= 1 - rand
    t = (y - 0.6) / 0.36
    halb = (0.5 - rand) * (1 - t * t)
    return abs(x - 0.5) <= halb


def _flaeche(muster: int, x: float, y: float) -> int:
    if muster == 0:
        return 0 if x < 0.5 else 1            # gespalten
    if muster == 1:
        return 0 if y < 0.45 else 1           # geteilt
    if muster == 2:
        return 0 if x + y < 1.0 else 1        # schräg
    return 1 if abs(x - 0.5) < 0.12 else 0    # Pfahl (Mittelstreifen)


def wappen_png(name: str, groesse: int = GROESSE) -> bytes:
    c1, c2, muster = farben(name)
    rand = (40, 40, 40)
    zeilen = bytearray()
    for py in range(groesse):
        zeilen.append(0)  # Filter: keiner
        y = (py + 0.5) / groesse
        for px in range(groesse):
            x = (px + 0.5) / groesse
            if not _im_schild(x, y):
                zeilen += b"\x00\x00\x00\x00"
                continue
            d = 2.5 / groesse
            innen = all(_im_schild(x + dx, y + dy) for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d)))
            r, g, b = (c1, c2)[_flaeche(muster, x, y)] if innen else rand
            zeilen += bytes((r, g, b, 255))

    def block(typ: bytes, daten: bytes) -> bytes:
        return struct.pack(">I", len(daten)) + typ + daten + struct.pack(">I", zlib.crc32(typ + daten) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", groesse, groesse, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + block(b"IHDR", ihdr) + block(b"IDAT", zlib.compress(bytes(zeilen), 9)) + block(b"IEND", b"")
