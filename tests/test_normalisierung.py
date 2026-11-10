"""--normalisiert: Beziehungstabellen + ERD; jeder Fremdschlüssel verweist auf eine existierende ID."""
import csv

import pytest

from gamegrab.adapters import hole_adapter

from conftest import fortnite_session, fussball_session, gtav_session, minecraft_session, pokemon_session

FAELLE = [
    ("fortnite", fortnite_session, {"typ": ["outfit", "backpack", "emote", "track"]}),
    ("minecraft", minecraft_session, {}),
    ("fussball", fussball_session, {}),
    ("fussball", fussball_session, {"quelle": "statsbomb", "anzahl": 1}),
    ("pokemon", pokemon_session, {"anzahl": 2}),
    ("gtav", gtav_session, {}),
]


def lies(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("spiel, session, opt", FAELLE, ids=[f"{f[0]}-{i}" for i, f in enumerate(FAELLE)])
def test_fremdschluessel_gueltig(lauf, spiel, session, opt):
    erg, _ = lauf(spiel, session(), normalisiert=True, **opt)
    ordner = erg.ziel / "_loesung"
    schema = hole_adapter(spiel).loesung_schema
    tabellen = {name: lies(ordner / f"{name}.csv") for name in schema}
    beziehungen = 0
    for name, info in schema.items():
        for spalte, ziel in info.get("fk", {}).items():
            t, s = ziel.split(".")
            ids = {z[s] for z in tabellen[t]}
            for z in tabellen[name]:
                if z[spalte]:
                    assert z[spalte] in ids, f"{name}.{spalte}={z[spalte]} fehlt in {ziel}"
                    beziehungen += 1
    assert beziehungen > 0
    erd = (ordner / "erd.md").read_text("utf-8")
    assert "erDiagram" in erd and "||--o{" in erd


def test_beispiele_der_anweisung(lauf):
    erg, _ = lauf("pokemon", pokemon_session(), anzahl=2, normalisiert=True)
    lo = erg.ziel / "_loesung"
    pt = lies(lo / "pokemon_typ.csv")
    assert {"pokemon_id": "1", "typ_id": "12", "slot": "1"} in pt and {"pokemon_id": "1", "typ_id": "4", "slot": "2"} in pt
    assert {"von_art_id": "1", "zu_art_id": "2", "ausloeser": "level-up", "min_level": "16"} in lies(lo / "entwicklung.csv")
    assert any(r["versteckt"] == "1" for r in lies(lo / "pokemon_faehigkeit.csv"))

    erg, _ = lauf("minecraft", minecraft_session(), normalisiert=True)
    rz = lies(erg.ziel / "_loesung" / "rezept_zutat.csv")
    assert rz and all(int(r["menge"]) >= 1 for r in rz)

    erg, _ = lauf("fussball", fussball_session(), normalisiert=True)
    spiel = lies(erg.ziel / "_loesung" / "spiel.csv")
    assert spiel[0]["heim_verein_id"] == "qatar" and spiel[0]["gast_verein_id"] == "ecuador"
    assert lies(erg.ziel / "_loesung" / "vertrag.csv")[0]["saison"] == "2022"
    tor = lies(erg.ziel / "_loesung" / "tor.csv")
    assert list(tor[0])[:3] == ["spiel_id", "nr", "spieler_id"]
