"""Kern: Dateinamen, Pfad-Traversal, HTTP-Regeln, Cache, CSV-Rohform, Register."""
import csv
import io

import pytest

from gamegrab.adapters import alle_adapter
from gamegrab.adapters.base import Adapter
from gamegrab.cache import Cache
from gamegrab.namen import Dateinamen, bereinige, sicherer_relpfad
from gamegrab.netz import DateiAbgelehnt, GamegrabFehler, GesperrteUrl, HttpClient
from gamegrab.schreiber import FremdschluesselFehler, csv_text, pruefe_fremdschluessel
from gamegrab.wappen import wappen_png

from conftest import FakeResponse, FakeSession, png


# --- Dateinamen wie in Durchblick ---------------------------------------------
@pytest.mark.parametrize("roh, erwartet", [
    ("Kaktus Kalle (Gold)", "kaktus_kalle_gold"),
    ("Neon Ninja.PNG", "neon_ninja.png"),
    ("Über Ärger", "ueber_aerger"),
    ("Straße", "strasse"),
    ("Pokémon Café", "pokemon_cafe"),
    ("...versteckt", "versteckt"),
    ("???", "datei"),
    ("a  --  b", "a_--_b"),
])
def test_bereinige(roh, erwartet):
    assert bereinige(roh) == erwartet


def test_bereinigt_ist_stabil():
    # Durchblick bereinigt beim Einsortieren nochmals – unsere Namen dürfen sich dabei nicht ändern
    for roh in ["Kaktus Kalle (Gold)", "Peely Ärger!!", "../../böse Datei", "Ü-Bär_2"]:
        einmal = bereinige(roh)
        assert bereinige(einmal) == einmal


def test_kollision_bekommt_nummer():
    n = Dateinamen()
    assert n.vergib("skins", "Neon Ninja", "png") == "skins/neon_ninja.png"
    assert n.vergib("skins", "neon ninja", "png") == "skins/neon_ninja_2.png"
    assert n.vergib("skins", "NEON-NINJA", "png") == "skins/neon-ninja.png"
    assert n.vergib("skins", "Neon Ninja", "png") == "skins/neon_ninja_3.png"


@pytest.mark.parametrize("roh", ["../../etc/passwd", "/etc/passwd", "C:/Windows/x", "..\\..\\x", "a/./../b"])
def test_pfad_traversal(roh):
    p = sicherer_relpfad(roh)
    assert ".." not in p.split("/") and not p.startswith("/") and ":" not in p


def test_pfad_leer_ist_fehler():
    with pytest.raises(ValueError):
        sicherer_relpfad("../..")


# --- HTTP-Regeln ----------------------------------------------------------------
def client(session, **kw):
    import tempfile
    return HttpClient(["beispiel.ch"], cache=Cache(tempfile.mkdtemp()), session=session,
                      schlafen=lambda s: None, melde=lambda t: None, **kw)


def test_nur_https_und_erlaubte_hosts():
    c = client(FakeSession())
    with pytest.raises(GesperrteUrl):
        c.get_json("http://beispiel.ch/a.json")
    with pytest.raises(GesperrteUrl):
        c.get_json("https://boese.example.com/a.json")
    with pytest.raises(GesperrteUrl):
        c.lade_datei("https://beispiel.ch.boese.com/x.png")


def test_weiterleitung_auf_fremden_host_gesperrt():
    s = FakeSession()
    s.routen["https://beispiel.ch/x.png"] = FakeResponse(302, b"", {"Location": "https://boese.example.com/x.png"})
    with pytest.raises(GesperrteUrl):
        client(s).lade_datei("https://beispiel.ch/x.png")
    assert all("boese" not in u for u, _ in s.aufrufe)


def test_user_agent():
    s = FakeSession()
    s.json("https://beispiel.ch/a.json", {"ok": 1})
    client(s).get_json("https://beispiel.ch/a.json")
    assert s.aufrufe[0][1]["User-Agent"] == "gamegrab/1.0 (Schulprojekt)"


def test_groessenlimit_pro_datei():
    s = FakeSession()
    gross = png() + b"\x00" * (6 * 1024 * 1024)
    s.routen["https://beispiel.ch/gross.png"] = FakeResponse(200, gross, {"Content-Type": "image/png"})
    with pytest.raises(DateiAbgelehnt):
        client(s).lade_datei("https://beispiel.ch/gross.png")
    s.datei("https://beispiel.ch/gross2.png", gross)  # mit Content-Length
    with pytest.raises(DateiAbgelehnt):
        client(s).lade_datei("https://beispiel.ch/gross2.png")


def test_content_type_und_signatur_werden_geprueft():
    s = FakeSession()
    s.datei("https://beispiel.ch/seite.png", b"<html>hallo</html>", "text/html")
    s.datei("https://beispiel.ch/getarnt.png", b"<html>hallo</html>", "image/png")
    s.datei("https://beispiel.ch/ok.bin", png(), "application/octet-stream")
    c = client(s)
    with pytest.raises(DateiAbgelehnt):
        c.lade_datei("https://beispiel.ch/seite.png")
    with pytest.raises(DateiAbgelehnt):
        c.lade_datei("https://beispiel.ch/getarnt.png")
    assert c.lade_datei("https://beispiel.ch/ok.bin")[1] == "png"


def test_429_respektiert_retry_after():
    s = FakeSession()
    antworten = [FakeResponse(429, b"", {"Retry-After": "7"}),
                 FakeResponse(200, b'{"ok": true}', {"Content-Type": "application/json"})]
    s.routen["https://beispiel.ch/a.json"] = lambda: antworten.pop(0)
    pausen = []
    c = HttpClient(["beispiel.ch"], rate=0, cache=Cache(__import__("tempfile").mkdtemp()), session=s,
                   schlafen=pausen.append, melde=lambda t: None)
    assert c.get_json("https://beispiel.ch/a.json") == {"ok": True}
    assert 7.0 in pausen


def test_serverfehler_mit_backoff_und_abbruch():
    s = FakeSession()
    s.routen["https://beispiel.ch/a.json"] = FakeResponse(503)
    with pytest.raises(GamegrabFehler):
        client(s).get_json("https://beispiel.ch/a.json")
    assert len(s.aufrufe) == 4


def test_rate_limit_wartet():
    s = FakeSession()
    s.json("https://beispiel.ch/a.json", 1)
    s.json("https://beispiel.ch/b.json", 2)
    pausen = []
    c = HttpClient(["beispiel.ch"], rate=2.0, cache=Cache(__import__("tempfile").mkdtemp()), session=s,
                   schlafen=pausen.append)
    c.get_json("https://beispiel.ch/a.json")
    c.get_json("https://beispiel.ch/b.json")
    assert pausen and 0.3 < pausen[-1] <= 0.5


def test_cache_laedt_nichts_neu(tmp_path):
    s = FakeSession()
    s.json("https://beispiel.ch/a.json", {"x": 1})
    s.datei("https://beispiel.ch/b.png", png())
    for _ in range(2):
        c = HttpClient(["beispiel.ch"], cache=Cache(tmp_path), session=s, schlafen=lambda x: None)
        c.get_json("https://beispiel.ch/a.json")
        c.lade_datei("https://beispiel.ch/b.png")
    assert len(s.aufrufe) == 2


def test_cache_listen_laufen_ab(tmp_path):
    cache = Cache(tmp_path)
    cache.schreibe_liste("k", [1])
    assert cache.lies_liste("k") == [1]
    assert cache.lies_liste("k", ttl=-1) is None


# --- CSV-Rohform -------------------------------------------------------------------
def test_csv_rohform_mehrwertig_und_anfuehrungszeichen():
    text = csv_text(["id", "name", "typen", "aktiv"], [
        {"id": 1, "name": 'Peely, "die Banane"', "typen": ["fire", "flying"], "aktiv": True}])
    zeilen = list(csv.reader(io.StringIO(text)))
    assert zeilen[0] == ["id", "name", "typen", "aktiv"]
    assert zeilen[1] == ["1", 'Peely, "die Banane"', "fire|flying", "1"]
    assert text.splitlines()[1].startswith('1,"Peely, ""die Banane"""')


def test_fremdschluessel_pruefung():
    schema = {"a": {"spalten": ["id"], "pk": ["id"]}, "b": {"spalten": ["id", "a_id"], "fk": {"a_id": "a.id"}}}
    pruefe_fremdschluessel(schema, {"a": [{"id": 1}], "b": [{"id": 1, "a_id": 1}, {"id": 2, "a_id": None}]})
    with pytest.raises(FremdschluesselFehler):
        pruefe_fremdschluessel(schema, {"a": [{"id": 1}], "b": [{"id": 1, "a_id": 2}]})
    with pytest.raises(FremdschluesselFehler):
        pruefe_fremdschluessel(schema, {"a": [{"id": 1}, {"id": 1}], "b": []})


def test_wappen_ist_png_128():
    daten = wappen_png("FC Beispiel")
    assert daten.startswith(b"\x89PNG") and daten[16:24] == (128).to_bytes(4, "big") * 2
    assert wappen_png("FC Beispiel") == daten and wappen_png("FC Anders") != daten


# --- Register: ein neuer Adapter = eine Datei ------------------------------------
def test_alle_adapter_erfuellen_vertrag():
    adapter = alle_adapter()
    assert list(adapter)[:5] == ["fortnite", "minecraft", "fussball", "pokemon", "gtav"]
    assert "zelda" not in adapter and "mtg" not in adapter
    for name, a in adapter.items():
        assert isinstance(a, Adapter) and a.name == name
        assert a.titel and a.alter and a.entitaeten and a.erlaubte_hosts and a.lizenz
        assert 0 < a.rate <= 2.0
        for spalten in a.entitaeten.values():
            assert spalten[:2] == ["id", "name"] or name == "fussball"
        for tabelle, info in a.loesung_schema.items():
            for spalte, ziel in info.get("fk", {}).items():
                assert spalte in info["spalten"]
                t, s = ziel.split(".")
                assert s in a.loesung_schema[t]["spalten"]


def test_geruest_meldet_sich(lauf):
    with pytest.raises(GamegrabFehler, match="Gerüst"):
        lauf("valorant", FakeSession())
