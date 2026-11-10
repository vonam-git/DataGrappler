"""Valorant über valorant-api.com (Community-API, ohne Schlüssel) – GERÜST, noch nicht umgesetzt.

So geht es weiter (eine Datei, ein Test):
- Endpunkte: https://valorant-api.com/v1/agents?isPlayableCharacter=true&language=de-DE
             https://valorant-api.com/v1/weapons?language=de-DE   (skins[].chromas[] = Varianten)
             https://valorant-api.com/v1/maps, /v1/sprays
- Bilder: agents[].displayIcon, weapons[].displayIcon, skins[].displayIcon (Host media.valorant-api.com)
- Beziehungen: Agent n:1 Rolle; Agent 1:n Fähigkeit; Waffe 1:n Skin 1:n Variante
- Riot Games «Legal Jibber Jabber»: Fan-Projekte erlaubt, Disclaimer nötig, keine Spielerdaten.
"""
from .base import Adapter


class Valorant(Adapter):
    name = "valorant"
    titel = "Valorant"
    alter = "16"
    geruest = True
    beschreibung = "Agenten, Rollen, Fähigkeiten, Waffen, Skins (valorant-api.com) – noch Gerüst"
    kategorien = {"agent": "agenten", "weapon": "waffen", "skin": "skins", "map": "maps", "spray": "sprays"}
    entitaeten = {
        "agenten": ["id", "name", "rolle", "faehigkeiten", "beschreibung", "datei"],
        "waffen": ["id", "name", "kategorie", "preis", "datei"],
        "skins": ["id", "name", "waffe", "varianten", "datei"],
    }
    erlaubte_hosts = ("valorant-api.com", "media.valorant-api.com")
    quelle = "valorant-api.com (Community-API, nicht von Riot Games)"
    lizenz = "Riot Games Legal Jibber Jabber: https://www.riotgames.com/en/legal"
    disclaimer = ("gamegrab isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games "
                  "or anyone officially involved in producing or managing Riot Games properties.")

    def hole(self, opt, http, namen):
        raise NotImplementedError("Valorant ist noch ein Gerüst")
