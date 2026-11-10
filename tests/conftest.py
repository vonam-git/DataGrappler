"""Gemeinsame Hilfen: aufgezeichnete Beispielantworten statt echter Netzaufrufe."""
from __future__ import annotations

import io
import json
import struct
import zlib
from pathlib import Path
from typing import Callable, Dict, Union

import pytest

from gamegrab.adapters import hole_adapter
from gamegrab.adapters.base import Optionen
from gamegrab.kern import ausfuehren

DATEN = Path(__file__).parent / "daten"


def png(breite: int = 4, hoehe: int = 4) -> bytes:
    roh = b"".join(b"\x00" + b"\xff\x00\x00\xff" * breite for _ in range(hoehe))

    def block(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + block(b"IHDR", struct.pack(">IIBBBBB", breite, hoehe, 8, 6, 0, 0, 0))
            + block(b"IDAT", zlib.compress(roh)) + block(b"IEND", b""))


OGG = b"OggS\x00\x02" + b"\x00" * 40
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 30
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 40


class FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b"", headers: Dict[str, str] = None) -> None:
        self.status_code = status
        self._body = body
        self.headers = headers or {}

    def iter_content(self, groesse: int):
        stream = io.BytesIO(self._body)
        while True:
            stueck = stream.read(groesse)
            if not stueck:
                break
            yield stueck


Antwort = Union[FakeResponse, Callable[[], FakeResponse]]


class FakeSession:
    """Ersetzt requests.Session. Jede URL muss vorher eingetragen sein – sonst 404."""

    def __init__(self) -> None:
        self.routen: Dict[str, Antwort] = {}
        self.aufrufe = []

    def json(self, url: str, daten) -> None:
        self.routen[url] = FakeResponse(200, json.dumps(daten).encode(), {"Content-Type": "application/json"})

    def json_datei(self, url: str, name: str) -> None:
        self.json(url, json.loads((DATEN / name).read_text("utf-8")))

    def datei(self, url: str, inhalt: bytes, typ: str = "image/png") -> None:
        self.routen[url] = FakeResponse(200, inhalt, {"Content-Type": typ, "Content-Length": str(len(inhalt))})

    def text(self, url: str, text: str) -> None:
        self.routen[url] = FakeResponse(200, text.encode(), {"Content-Type": "text/html; charset=utf-8"})

    def get(self, url, headers=None, timeout=None, stream=False, allow_redirects=True):
        self.aufrufe.append((url, dict(headers or {})))
        r = self.routen.get(url)
        if r is None:
            return FakeResponse(404, b"nicht gefunden")
        return r() if callable(r) else r


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    """Führt gamegrab mit einer FakeSession aus. Gibt (ergebnis, meldungen) zurück."""
    monkeypatch.chdir(tmp_path)

    def _lauf(spiel: str, session: FakeSession, **opt):
        meldungen = []
        opt.setdefault("ziel", str(tmp_path / "aus" / spiel))
        erg = ausfuehren(hole_adapter(spiel), Optionen(**opt), cache_ordner=str(tmp_path / "cache"),
                         session=session, melde=meldungen.append, schlafen=lambda s: None)
        return erg, meldungen

    return _lauf


# --- Routen pro Spiel ----------------------------------------------------------
def fortnite_session(sprache: str = "de") -> FakeSession:
    s = FakeSession()
    s.json_datei(f"https://fortnite-api.com/v2/cosmetics/br?language={sprache}", "fortnite_br.json")
    s.json_datei("https://fortnite-api.com/v2/cosmetics/tracks", "fortnite_tracks.json")
    daten = json.loads((DATEN / "fortnite_br.json").read_text("utf-8"))["data"]
    for c in daten:
        for url in (c["images"] or {}).values():
            if url and url.startswith("https://fortnite-api.com"):
                s.datei(url, png())
    s.datei("https://cdn2.unrealengine.com/neon-nights-512x512.jpg", JPG, "image/jpeg")
    return s


MC = "https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master/data"


def minecraft_session() -> FakeSession:
    s = FakeSession()
    s.json_datei(f"{MC}/dataPaths.json", "mc_dataPaths.json")
    for d in ["items", "blocks", "entities", "biomes", "recipes", "enchantments"]:
        s.json_datei(f"{MC}/pc/26.1/{d}.json", f"mc_{d}.json")
    s.json_datei(f"{MC}/pc/1.20/entityLoot.json", "mc_entityLoot.json")
    return s


OF = "https://raw.githubusercontent.com/openfootball"
SB = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
FD = "https://api.football-data.org/v4"


def fussball_session() -> FakeSession:
    s = FakeSession()
    s.json_datei(f"{OF}/worldcup.json/master/2022/worldcup.json", "wc2022.json")
    s.json_datei(f"{SB}/competitions.json", "sb_competitions.json")
    s.json_datei(f"{SB}/matches/43/106.json", "sb_matches.json")
    s.json_datei(f"{SB}/events/3857286.json", "sb_events.json")
    for art in ("teams", "matches", "scorers"):
        s.json_datei(f"{FD}/competitions/BL1/{art}?season=2024", f"fd_{art}.json")
    return s


PK = "https://pokeapi.co/api/v2/"


def _absolut(daten):
    """api-data hat relative URLs, die echte API absolute – hier wie die echte API."""
    text = json.dumps(daten).replace('"/api/v2/', '"https://pokeapi.co/api/v2/')
    return json.loads(text)


def pokemon_session() -> FakeSession:
    s = FakeSession()
    lade = lambda n: _absolut(json.loads((DATEN / n).read_text("utf-8")))  # noqa: E731
    s.json(f"{PK}type?limit=50", {"count": 3, "results": [
        {"name": "poison", "url": f"{PK}type/4/"}, {"name": "grass", "url": f"{PK}type/12/"},
        {"name": "stellar", "url": f"{PK}type/19/"}]})
    s.json(f"{PK}type/4/", lade("pk_type_4.json"))
    s.json(f"{PK}type/12/", lade("pk_type_12.json"))
    s.json(f"{PK}pokemon?limit=2&offset=0", {"count": 1350, "results": [
        {"name": "bulbasaur", "url": f"{PK}pokemon/1/"}, {"name": "ivysaur", "url": f"{PK}pokemon/2/"}]})
    for i in (1, 2):
        p = lade(f"pk_pokemon_{i}.json")
        s.json(f"{PK}pokemon/{i}/", p)
        s.json(f"{PK}pokemon-species/{i}/", lade(f"pk_species_{i}.json"))
        s.datei(p["sprites"]["front_default"], png())
        s.datei(p["sprites"]["other"]["official-artwork"]["front_default"], png(8, 8))
        s.datei(p["cries"]["latest"], OGG, "audio/ogg")
    s.json(f"{PK}evolution-chain/1/", lade("pk_chain_1.json"))
    return s


FIVEM = "https://docs.fivem.net/docs/game-references/vehicle-references/vehicle-models/"


def gtav_session() -> FakeSession:
    s = FakeSession()
    html = (DATEN / "fivem_vehicle_models.html").read_text("utf-8")
    s.text(FIVEM, html)
    import re
    for src in re.findall(r'src="([^"]+)"', html):
        s.datei("https://docs.fivem.net" + src, WEBP, "image/webp")
    return s


@pytest.fixture(autouse=True)
def kein_internet(monkeypatch):
    """Tests laufen ohne Internet: jeder echte Verbindungsversuch schlägt fehl."""
    import socket

    def gesperrt(*a, **k):
        raise RuntimeError("Netzaufruf im Test – bitte FakeSession verwenden")

    monkeypatch.setattr(socket.socket, "connect", gesperrt)
    monkeypatch.setattr(socket, "create_connection", gesperrt)
