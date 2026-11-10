"""Adapter mit aufgezeichneten Antworten – ohne Internet."""
import csv
import json
import zipfile
from datetime import date

import pytest

from gamegrab.netz import GamegrabFehler

from conftest import (OGG, fortnite_session, fussball_session, gtav_session, minecraft_session, png,
                      pokemon_session)


def lies_csv(pfad):
    with open(pfad, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def dateien(ordner):
    return sorted(str(p.relative_to(ordner)) for p in ordner.rglob("*") if p.is_file())


# --- Fortnite ---------------------------------------------------------------------
def test_fortnite_grundlauf(lauf, tmp_path):
    s = fortnite_session()
    erg, meldungen = lauf("fortnite", s, typ=["outfit", "backpack", "emote"], anzahl=20)
    ziel = erg.ziel
    zeilen = lies_csv(ziel / "items.csv")
    assert list(zeilen[0]) == ["id", "name", "typ", "kategorie", "seltenheit", "set", "saison", "hinzugefuegt",
                               "beschreibung", "datei", "video_link", "shop_daten"]
    assert {z["kategorie"] for z in zeilen} == {"skins", "rucksaecke", "taenze"}
    assert len(zeilen) == 6
    raider = next(z for z in zeilen if z["id"] == "CID_028_Athena_Commando_F")
    assert raider["datei"] == "skins/renegade_raider.png" and (ziel / raider["datei"]).is_file()
    assert raider["set"] == "Raider" and raider["saison"] == "Chapter 1, Season 1"
    assert raider["hinzugefuegt"] == "2017-10-26" and raider["shop_daten"] == "2017-10-26|2017-11-02"
    peely = next(z for z in zeilen if z["name"] == "Peely Ärger")
    assert peely["datei"] == "skins/peely_aerger.png" and peely["set"] == ""
    neon = next(z for z in zeilen if z["name"] == "Neon Ninja")
    assert len(neon["beschreibung"]) <= 300
    # Videos nur als Link, nie heruntergeladen
    tanz = next(z for z in zeilen if z["typ"] == "emote")
    assert tanz["video_link"] == "https://youtu.be/dQw4w9WgXcQ"
    assert not any("youtu" in u for u, _ in s.aufrufe)
    # neueste zuerst
    assert [z["name"] for z in zeilen if z["typ"] == "outfit"] == ["Peely Ärger", "Neon Ninja", "Renegade Raider"]
    # Begleitdateien
    assert (ziel / ".gitignore").read_text().strip().endswith("*")
    quellen = (ziel / "QUELLEN.txt").read_text("utf-8")
    assert "Fan Content Policy" in quellen and "This material is not official" in quellen
    assert "Nur für den Unterricht, nicht veröffentlichen" in quellen
    js = json.loads((ziel / "items.json").read_text("utf-8"))
    assert js["disclaimer"].startswith("Portions of the materials") and js["abgerufen_am"]
    assert any("Spielefirmen" in m for m in meldungen)


def test_fortnite_filter(lauf):
    erg, _ = lauf("fortnite", fortnite_session(), typ=["outfit", "backpack"], seltenheit=["legendary"])
    assert [z["name"] for z in lies_csv(erg.ziel / "items.csv")] == ["Neon Ninja", "Neon Rucksack"]
    erg, _ = lauf("fortnite", fortnite_session(), neu_seit=date(2026, 9, 1), ziel=str(erg.ziel) + "_b")
    assert {z["name"] for z in lies_csv(erg.ziel / "items.csv")} == {
        "Neon Ninja", "Peely Ärger", "Neon Rucksack", "../../böse Datei"}
    erg, _ = lauf("fortnite", fortnite_session(), suche="peely", ziel=str(erg.ziel) + "_c")
    assert [z["name"] for z in lies_csv(erg.ziel / "items.csv")] == ["Peely Ärger"]
    erg, _ = lauf("fortnite", fortnite_session(), typ=["outfit"], anzahl=1, ziel=str(erg.ziel) + "_d")
    assert len(lies_csv(erg.ziel / "items.csv")) == 1


def test_fortnite_pfad_traversal_und_fremder_host(lauf, tmp_path):
    erg, meldungen = lauf("fortnite", fortnite_session(), typ=["pickaxe"], bild="icon")
    zeilen = {z["name"]: z for z in lies_csv(erg.ziel / "items.csv")}
    boese = zeilen["../../böse Datei"]["datei"]
    assert boese == "spitzhacken/boese_datei.png" and (erg.ziel / boese).is_file()
    assert zeilen["Fremdbild"]["datei"] == ""          # Host nicht erlaubt -> übersprungen
    assert any("Host nicht erlaubt" in m for m in meldungen)
    alle = [p.resolve() for p in tmp_path.rglob("*.png")]
    assert all(str(p).startswith(str(erg.ziel.resolve())) or "cache" in str(p) for p in alle)


def test_fortnite_songs(lauf):
    erg, _ = lauf("fortnite", fortnite_session(), typ=["track"])
    songs = lies_csv(erg.ziel / "songs.csv")
    assert songs[0]["name"] == "Neon Nights" and songs[0]["genres"] == "Pop|Dance"
    assert songs[0]["datei"] == "songs/neon_nights.jpg"


def test_zweiter_lauf_laedt_nichts_neu(lauf):
    s = fortnite_session()
    erg1, _ = lauf("fortnite", s, typ=["outfit", "backpack", "emote"])
    vorher = len(s.aufrufe)
    erg2, _ = lauf("fortnite", s, typ=["outfit", "backpack", "emote"])
    assert vorher > 0 and len(s.aufrufe) == vorher
    assert erg2.anfragen == 0 and erg2.dateien == erg1.dateien


def test_max_mb_bricht_ab(lauf):
    erg, meldungen = lauf("fortnite", fortnite_session(), typ=["outfit"], max_mb=0.0002)
    assert any("--max-mb" in m for m in meldungen)
    assert 0 < erg.bytes <= 0.0002 * 1024 * 1024
    dateien = [z["datei"] for z in lies_csv(erg.ziel / "items.csv")]
    assert "" in dateien and all((erg.ziel / d).is_file() for d in dateien if d)


def test_zip(lauf):
    erg, _ = lauf("fortnite", fortnite_session(), typ=["outfit"], zip=True)
    with zipfile.ZipFile(erg.zip) as z:
        namen = z.namelist()
    assert f"{erg.ziel.name}/items.csv" in namen and f"{erg.ziel.name}/skins/renegade_raider.png" in namen


def test_endung_wird_an_inhalt_angepasst(lauf):
    s = fortnite_session()
    s.datei("https://fortnite-api.com/images/cosmetics/br/cid_028_athena_commando_f/smallicon.png", b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 20)
    erg, _ = lauf("fortnite", s, typ=["outfit"])
    raider = next(z for z in lies_csv(erg.ziel / "items.csv") if z["name"] == "Renegade Raider")
    assert raider["datei"] == "skins/renegade_raider.webp" and (erg.ziel / raider["datei"]).is_file()


# --- Minecraft ----------------------------------------------------------------------
def test_minecraft_ohne_lokal_nur_csv(lauf):
    erg, meldungen = lauf("minecraft", minecraft_session())
    for n in ("items", "bloecke", "kreaturen", "rezepte", "biome", "verzauberungen"):
        assert (erg.ziel / f"{n}.csv").is_file()
    assert erg.dateien == 0
    assert not [p for p in erg.ziel.rglob("*") if p.suffix in (".png", ".ogg")]
    rezepte = {r["ergebnis"]: r for r in lies_csv(erg.ziel / "rezepte.csv")}
    import re
    assert re.fullmatch(r"3x [a-z_]+_planks\|2x stick", rezepte["wooden_pickaxe"]["zutaten"])
    assert rezepte["stick"]["menge"] == "4"
    stein = next(b for b in lies_csv(erg.ziel / "bloecke.csv") if b["name"] == "stone")
    assert "wooden_pickaxe" in stein["werkzeuge"].split("|") and stein["drops"] == "cobblestone"
    kreaturen = {k["name"]: k for k in lies_csv(erg.ziel / "kreaturen.csv")}
    assert "arrow" not in kreaturen and "rotten_flesh" in kreaturen["zombie"]["drops"]
    assert any("ohne --lokal" in m for m in meldungen)


def _mini_installation(wurzel):
    v = wurzel / "versions" / "26.1"
    v.mkdir(parents=True)
    with zipfile.ZipFile(v / "26.1.jar", "w") as z:
        z.writestr("assets/minecraft/textures/item/stick.png", png())
        z.writestr("assets/minecraft/textures/block/stone.png", png())
        z.writestr("assets/minecraft/textures/block/oak_log_top.png", png())
        z.writestr("assets/minecraft/textures/item/zombie_spawn_egg.png", png())
        z.writestr("net/minecraft/Main.class", b"\xca\xfe\xba\xbe")
    (v / "26.1.json").write_text(json.dumps({"assetIndex": {"id": "29"}}))
    h = "ab" + "c" * 38
    idx = wurzel / "assets" / "indexes"
    idx.mkdir(parents=True)
    idx.joinpath("29.json").write_text(json.dumps({"objects": {
        "minecraft/sounds/mob/zombie/hurt1.ogg": {"hash": "ff" + "0" * 38, "size": 10},
        "minecraft/sounds/mob/zombie/say1.ogg": {"hash": h, "size": 10}}}))
    obj = wurzel / "assets" / "objects" / "ab"
    obj.mkdir(parents=True)
    (obj / h).write_bytes(OGG)


def test_minecraft_lokal_liest_eigene_installation(lauf, tmp_path):
    inst = tmp_path / "dot_minecraft"
    _mini_installation(inst)
    s = minecraft_session()
    erg, _ = lauf("minecraft", s, lokal=str(inst))
    items = {i["name"]: i for i in lies_csv(erg.ziel / "items.csv")}
    assert items["stick"]["datei"] == "items/stick.png" and (erg.ziel / "items/stick.png").is_file()
    bloecke = {b["name"]: b for b in lies_csv(erg.ziel / "bloecke.csv")}
    assert bloecke["stone"]["datei"] == "bloecke/stone.png" and bloecke["oak_log"]["datei"] == "bloecke/oak_log.png"
    zombie = next(k for k in lies_csv(erg.ziel / "kreaturen.csv") if k["name"] == "zombie")
    assert zombie["ton"] == "kreaturen/zombie.ogg" and (erg.ziel / zombie["ton"]).read_bytes() == OGG
    assert zombie["datei"] == "kreaturen/zombie.png"
    # nie Mojang-Assets aus dem Internet
    assert all("raw.githubusercontent.com/PrismarineJS" in u for u, _ in s.aufrufe)
    # nur Ausgewähltes kopiert (keine .class-Dateien)
    assert not list(erg.ziel.rglob("*.class"))


def test_minecraft_lokal_ohne_installation(lauf, tmp_path):
    with pytest.raises(GamegrabFehler, match="keine Minecraft-Installation"):
        lauf("minecraft", minecraft_session(), lokal=str(tmp_path / "gibtsnicht"))


def test_minecraft_typ_und_anzahl(lauf):
    erg, _ = lauf("minecraft", minecraft_session(), typ=["items", "rezepte"], anzahl=2)
    assert sorted(p.name for p in erg.ziel.glob("*.csv")) == ["items.csv", "rezepte.csv"]
    assert len(lies_csv(erg.ziel / "items.csv")) == 2


# --- Fussball --------------------------------------------------------------------------
def test_fussball_wm_2022(lauf):
    erg, _ = lauf("fussball", fussball_session(), wettbewerb="wm", saison="2022")
    z = erg.ziel
    nationen = lies_csv(z / "nationen.csv")
    assert {"Qatar", "Ecuador", "Argentina", "France"} <= {n["name"] for n in nationen}
    for n in nationen:
        inhalt = (z / n["datei"]).read_bytes()
        assert n["datei"].startswith("wappen/") and inhalt[:4] == b"\x89PNG"
    spiele = lies_csv(z / "spiele.csv")
    finale = next(s for s in spiele if s["runde"] == "Final")
    assert (finale["heim"], finale["tore_heim"], finale["tore_gast"], finale["penaltyschiessen"]) == ("Argentina", "3", "3", "4:2")
    assert any(s["tore_heim"] == "0" and s["halbzeit"] == "" for s in spiele)  # Kurzform score [0, 0]
    tore = lies_csv(z / "tore.csv")
    messi = [t for t in tore if t["spieler"] == "Lionel Messi"]
    assert len(messi) == 2 and messi[0]["penalty"] == "1"
    assert any(t["eigentor"] == "1" for t in tore)
    spieler = lies_csv(z / "spieler.csv")
    assert list(spieler[0]) == ["id", "name", "position", "nation", "verein"]
    text = "".join(p.read_text("utf-8") for p in z.glob("*.csv")) + (z / "daten.json").read_text("utf-8")
    assert "geburt" not in text.lower() and "dateOfBirth" not in text and "crest" not in text


def test_fussball_eigentor_zaehlt_fuer_gegner(lauf):
    erg, _ = lauf("fussball", fussball_session())
    tore = lies_csv(erg.ziel / "tore.csv")
    spieler = {s["name"]: s for s in lies_csv(erg.ziel / "spieler.csv")}
    et = next(t for t in tore if t["eigentor"] == "1")
    assert spieler[et["spieler"]]["nation"] != et["team"]


def test_fussball_football_data_ohne_geburtsdaten(lauf, monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_TOKEN", "geheim")
    s = fussball_session()
    erg, _ = lauf("fussball", s, quelle="football-data", wettbewerb="BL1", saison="2024")
    assert all(h.get("X-Auth-Token") == "geheim" for u, h in s.aufrufe)
    spieler = lies_csv(erg.ziel / "spieler.csv")
    assert {"Manuel Neuer", "Harry Kane", "Gregor Kobel"} == {p["name"] for p in spieler}
    kobel = next(p for p in spieler if p["name"] == "Gregor Kobel")
    assert (kobel["position"], kobel["nation"], kobel["verein"]) == ("Goalkeeper", "Switzerland", "Borussia Dortmund")
    alles = "".join(p.read_text("utf-8") for p in erg.ziel.rglob("*.csv")) + (erg.ziel / "daten.json").read_text("utf-8")
    assert "1986" not in alles and "crests" not in alles
    assert lies_csv(erg.ziel / "torschuetzen.csv")[0]["tore"] == "26"


def test_fussball_football_data_braucht_token(lauf, monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_TOKEN", raising=False)
    with pytest.raises(GamegrabFehler, match="FOOTBALL_DATA_TOKEN"):
        lauf("fussball", fussball_session(), quelle="football-data")


def test_fussball_statsbomb(lauf):
    erg, _ = lauf("fussball", fussball_session(), quelle="statsbomb", wettbewerb="wm", saison="2022", anzahl=1)
    assert "Data provided by StatsBomb" in (erg.ziel / "QUELLEN.txt").read_text("utf-8")
    ereignisse = lies_csv(erg.ziel / "ereignisse.csv")
    assert ereignisse and "Pass" not in {e["typ"] for e in ereignisse}
    tore = lies_csv(erg.ziel / "tore.csv")
    assert tore and all(t["team"] == "Ecuador" for t in tore)


# --- Pokémon ------------------------------------------------------------------------------
def test_pokemon(lauf):
    erg, _ = lauf("pokemon", pokemon_session(), anzahl=2)
    z = erg.ziel
    pk = {p["name_en"]: p for p in lies_csv(z / "pokemon.csv")}
    bisasam = pk["bulbasaur"]
    assert bisasam["name"] == "Bisasam" and bisasam["typen"] == "grass|poison"
    assert bisasam["faehigkeiten"] == "overgrow|chlorophyll (versteckt)"
    assert bisasam["datei"] == "sprites/0001_bisasam.png" and (z / bisasam["datei"]).is_file()
    assert bisasam["schrei"] == "schreie/0001_bisasam.ogg" and (z / bisasam["schrei"]).read_bytes()[:4] == b"OggS"
    assert bisasam["artwork"] == ""
    arten = {a["name_en"]: a for a in lies_csv(z / "arten.csv")}
    assert arten["Ivysaur"]["entwickelt_aus"] == "bulbasaur" and arten["Ivysaur"]["entwicklung_level"] == "16"
    typen = {t["name_en"]: t for t in lies_csv(z / "typen.csv")}
    assert typen["grass"]["name"] == "Pflanze" and "water" in typen["grass"]["doppelter_schaden_an"].split("|")
    assert "stellar" not in typen


def test_pokemon_artwork_und_typfilter(lauf):
    erg, _ = lauf("pokemon", pokemon_session(), anzahl=5, bild="featured", typ=["grass"])
    pk = lies_csv(erg.ziel / "pokemon.csv")
    assert [p["id"] for p in pk] == ["1", "2"]          # Sonderform 10033 ausgelassen
    assert pk[0]["artwork"] == "artworks/0001_bisasam.png"


# --- GTA V --------------------------------------------------------------------------------
def test_gtav_nur_fahrzeuge_mit_pegi_hinweis(lauf):
    s = gtav_session()
    erg, meldungen = lauf("gtav", s, anzahl=20)
    assert any("PEGI 18" in m for m in meldungen)
    f = lies_csv(erg.ziel / "fahrzeuge.csv")
    assert len(f) == 6 and {x["klasse"] for x in f} == {"compacts", "super"}   # military ausgelassen
    asbo = f[0]
    assert (asbo["id"], asbo["name"], asbo["hash"]) == ("asbo", "Asbo", "1118611807")
    assert asbo["datei"] == "fahrzeuge/compacts/asbo.webp" and (erg.ziel / asbo["datei"]).is_file()
    assert asbo["preis"] == "" and asbo["hersteller"] == ""
    assert {u.split("/")[2] for u, _ in s.aufrufe} == {"docs.fivem.net"}


def test_gtav_rate_1_pro_sekunde():
    from gamegrab.adapters import hole_adapter
    assert hole_adapter("gtav").rate == 1.0


def test_gtav_militaer_gesperrt(lauf):
    with pytest.raises(GamegrabFehler, match="Militär"):
        lauf("gtav", gtav_session(), typ=["military"])


def test_gtav_anzahl_pro_klasse(lauf):
    erg, _ = lauf("gtav", gtav_session(), typ=["compacts", "super"], anzahl=1)
    assert [x["id"] for x in lies_csv(erg.ziel / "fahrzeuge.csv")] == ["asbo", "adder"]
