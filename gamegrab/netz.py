"""HTTP-Client mit den Sicherheits- und Fairnessregeln von gamegrab.

- nur HTTPS und nur Hosts aus der Liste des Adapters (auch bei Weiterleitungen)
- höchstens `rate` Anfragen pro Sekunde (Standard 2/s), eigener User-Agent
- Wiederholung mit Backoff, bei HTTP 429 wird Retry-After respektiert
- Grössenlimit pro Datei, Content-Type und Dateisignatur werden geprüft
- Cache: Listen 24 h, Dateien dauerhaft
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, Iterable, Optional, Tuple
from urllib.parse import urlencode, urljoin, urlsplit

import requests

from .cache import LISTEN_TTL, Cache

USER_AGENT = "gamegrab/1.0 (Schulprojekt)"
MAX_DATEI = 5 * 1024 * 1024
MAX_LISTE = 128 * 1024 * 1024  # die Fortnite-Gesamtliste ist mehrere MB gross
MAX_WEITERLEITUNGEN = 5
VERSUCHE = 4


class GamegrabFehler(Exception):
    """Fehler, die dem Benutzer verständlich gemeldet werden."""


class GesperrteUrl(GamegrabFehler):
    pass


class DateiAbgelehnt(GamegrabFehler):
    pass


def erkenne_art(daten: bytes) -> Optional[Tuple[str, str]]:
    """Dateisignatur prüfen. Gibt (art, endung) zurück, z.B. ('image', 'png')."""
    k = daten[:16]
    if k.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "png"
    if k.startswith(b"\xff\xd8\xff"):
        return "image", "jpg"
    if k.startswith(b"GIF87a") or k.startswith(b"GIF89a"):
        return "image", "gif"
    if k[:4] == b"RIFF" and k[8:12] == b"WEBP":
        return "image", "webp"
    if k[:4] == b"RIFF" and k[8:12] == b"WAVE":
        return "audio", "wav"
    if k.startswith(b"OggS"):
        return "audio", "ogg"
    if k.startswith(b"fLaC"):
        return "audio", "flac"
    if k.startswith(b"ID3") or k[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio", "mp3"
    return None


_NEUTRALE_TYPEN = ("", "application/octet-stream", "binary/octet-stream")


class HttpClient:
    def __init__(
        self,
        erlaubte_hosts: Iterable[str],
        rate: float = 2.0,
        cache: Optional[Cache] = None,
        session: Any = None,
        max_datei: int = MAX_DATEI,
        schlafen: Callable[[float], None] = time.sleep,
        melde: Callable[[str], None] = print,
    ) -> None:
        self.erlaubte_hosts = {h.lower() for h in erlaubte_hosts}
        self.intervall = 1.0 / rate if rate > 0 else 0.0
        self.cache = cache or Cache()
        self.session = session or requests.Session()
        self.max_datei = max_datei
        self._schlafen = schlafen
        self._melde = melde
        self._letzte = 0.0
        self.anfragen = 0
        self.cache_treffer = 0

    # -- Regeln ---------------------------------------------------------------
    def pruefe_url(self, url: str) -> None:
        teile = urlsplit(url)
        if teile.scheme != "https":
            raise GesperrteUrl(f"nur HTTPS erlaubt: {url}")
        host = (teile.hostname or "").lower()
        if host not in self.erlaubte_hosts:
            raise GesperrteUrl(f"Host nicht erlaubt: {host or url}")

    def _drosseln(self) -> None:
        jetzt = time.monotonic()
        warte = self._letzte + self.intervall - jetzt
        if warte > 0:
            self._schlafen(warte)
        self._letzte = time.monotonic()

    @staticmethod
    def _retry_after(wert: Optional[str]) -> float:
        try:
            return min(max(float(wert), 1.0), 120.0)
        except (TypeError, ValueError):
            return 10.0

    def _anfrage(self, url: str, headers: Optional[Dict[str, str]] = None, stream: bool = False):
        kopf = {"User-Agent": USER_AGENT}
        kopf.update(headers or {})
        weiterleitungen = 0
        versuch = 0
        while True:
            self.pruefe_url(url)
            self._drosseln()
            self.anfragen += 1
            try:
                r = self.session.get(url, headers=kopf, timeout=30, stream=stream, allow_redirects=False)
            except requests.RequestException as e:
                versuch += 1
                if versuch >= VERSUCHE:
                    raise GamegrabFehler(f"Netzwerkfehler bei {url}: {e}") from e
                self._schlafen(2 ** versuch)
                continue
            code = r.status_code
            if code in (301, 302, 303, 307, 308):
                weiterleitungen += 1
                if weiterleitungen > MAX_WEITERLEITUNGEN:
                    raise GamegrabFehler(f"zu viele Weiterleitungen: {url}")
                url = urljoin(url, r.headers.get("Location", ""))
                continue
            if code == 429:
                versuch += 1
                if versuch >= VERSUCHE:
                    raise GamegrabFehler(f"Server meldet zu viele Anfragen (429): {url}")
                warte = self._retry_after(r.headers.get("Retry-After"))
                self._melde(f"  Server bittet um Pause (429), warte {warte:.0f} s …")
                self._schlafen(warte)
                continue
            if code >= 500:
                versuch += 1
                if versuch >= VERSUCHE:
                    raise GamegrabFehler(f"Serverfehler {code}: {url}")
                self._schlafen(2 ** versuch)
                continue
            if code != 200:
                raise GamegrabFehler(f"HTTP {code} bei {url}")
            return r

    @staticmethod
    def _mit_parametern(url: str, params: Optional[Dict[str, Any]]) -> str:
        if not params:
            return url
        sep = "&" if "?" in url else "?"
        return url + sep + urlencode(sorted((k, v) for k, v in params.items() if v is not None))

    def _inhalt(self, r, grenze: int, url: str) -> bytes:
        laenge = r.headers.get("Content-Length")
        if laenge and laenge.isdigit() and int(laenge) > grenze:
            raise DateiAbgelehnt(f"zu gross ({int(laenge) // 1024} KB > {grenze // 1024} KB): {url}")
        teile, summe = [], 0
        for stueck in r.iter_content(64 * 1024):
            summe += len(stueck)
            if summe > grenze:
                raise DateiAbgelehnt(f"zu gross (> {grenze // 1024} KB): {url}")
            teile.append(stueck)
        return b"".join(teile)

    # -- öffentliche Methoden --------------------------------------------------
    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None, ttl: float = LISTEN_TTL) -> Any:
        voll = self._mit_parametern(url, params)
        self.pruefe_url(voll)
        treffer = self.cache.lies_liste("json:" + voll, ttl)
        if treffer is not None:
            self.cache_treffer += 1
            return treffer
        r = self._anfrage(voll, headers, stream=True)
        roh = self._inhalt(r, MAX_LISTE, voll)
        try:
            daten = json.loads(roh.decode("utf-8"))
        except ValueError as e:
            raise GamegrabFehler(f"keine gültige JSON-Antwort: {voll}") from e
        self.cache.schreibe_liste("json:" + voll, daten)
        return daten

    def get_text(self, url: str, ttl: float = LISTEN_TTL) -> str:
        self.pruefe_url(url)
        treffer = self.cache.lies_liste("text:" + url, ttl)
        if treffer is not None:
            self.cache_treffer += 1
            return treffer
        r = self._anfrage(url, stream=True)
        text = self._inhalt(r, MAX_LISTE, url).decode("utf-8", errors="replace")
        self.cache.schreibe_liste("text:" + url, text)
        return text

    def lade_datei(self, url: str, erlaubt: Tuple[str, ...] = ("image", "audio")) -> Tuple[bytes, str]:
        """Bild oder Audio laden. Gibt (inhalt, endung) zurück. Dauerhaft im Cache."""
        self.pruefe_url(url)
        treffer = self.cache.lies_datei(url)
        if treffer is not None:
            self.cache_treffer += 1
            return treffer
        r = self._anfrage(url, stream=True)
        typ = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if not (typ.split("/")[0] in erlaubt or typ in _NEUTRALE_TYPEN):
            raise DateiAbgelehnt(f"unerwarteter Dateityp {typ!r}: {url}")
        inhalt = self._inhalt(r, self.max_datei, url)
        art = erkenne_art(inhalt)
        if art is None or art[0] not in erlaubt:
            raise DateiAbgelehnt(f"Inhalt ist kein Bild/Audio: {url}")
        self.cache.schreibe_datei(url, inhalt, art[1])
        return inhalt, art[1]
