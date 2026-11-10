"""Magic: The Gathering über Scryfall – GERÜST, noch nicht umgesetzt.

Regeln von Scryfall, die der fertige Adapter einhalten muss:
- Bulk-Daten statt vieler Einzelanfragen: https://api.scryfall.com/bulk-data -> «oracle_cards» bzw.
  «default_cards» (download_uri auf data.scryfall.io). Die Datei ist gross: nur einmal pro Tag laden (Cache).
- 50–100 ms Pause zwischen Anfragen (rate = 10), eigener User-Agent und Accept-Header.
- Bilder: image_uris.small direkt laden (Host cards.scryfall.io). Bilder NIE beschneiden, verzerren oder
  Copyright/Künstlername verdecken – die Werkstatt soll sie darum nicht weiter verkleinern.
- Beziehungen: Karte 1:n Druck; Set 1:n Druck; Künstler 1:n Druck; Karte–Farbe n:m;
  Karte–Format n:m mit Status (legal, banned, restricted) aus «legalities».
- Wizards of the Coast Fan Content Policy: https://company.wizards.com/en/legal/fancontentpolicy
"""
from .base import Adapter


class Mtg(Adapter):
    name = "mtg"
    titel = "Magic: The Gathering"
    alter = "– (Kartenspiel)"
    geruest = True
    rate = 10.0
    beschreibung = "Karten, Drucke, Sets, Künstler, Farben, Formate (Scryfall Bulk-Daten) – noch Gerüst"
    kategorien = {"karten": "karten"}
    entitaeten = {
        "karten": ["id", "name", "farben", "manakosten", "typzeile", "formate"],
        "drucke": ["id", "name", "karte_id", "set", "kuenstler", "seltenheit", "datei"],
        "sets": ["id", "name", "erschienen"],
    }
    erlaubte_hosts = ("api.scryfall.com", "data.scryfall.io", "cards.scryfall.io")
    quelle = "Scryfall API (Bulk-Daten): https://scryfall.com/docs/api"
    lizenz = "Wizards of the Coast Fan Content Policy; Scryfall API-Regeln (Bilder unverändert lassen)"
    disclaimer = ("Portions of the materials used are property of Wizards of the Coast. "
                  "©Wizards of the Coast LLC.")

    def hole(self, opt, http, namen):
        raise NotImplementedError("Magic: The Gathering ist noch ein Gerüst")
