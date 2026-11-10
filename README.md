# DataGrappler · `gamegrab`

Rohdaten-Sammler für die **Durchblick-Werkstatt** (Modul 141, Datenbanken in Betrieb nehmen).
`gamegrab` holt Spieldaten aus offenen Quellen und legt sie als Ordner ab: Bilder, Töne und eine CSV pro Entität.
Diesen Ordner ziehst du direkt in die Werkstatt von [Durchblick](https://github.com/vonam-git/durchblick).

> 🔒 Die Bilder und Töne gehören den Spielefirmen. Verwende sie **nur im Unterricht**, veröffentliche sie nicht
> und lade sie nie in ein öffentliches Repository hoch. Jeder Ausgabeordner enthält darum eine `.gitignore` mit `*`.

| Spiel | Befehl | Quelle | PEGI |
|---|---|---|---|
| Fortnite | `gamegrab fortnite` | Fortnite-API.com (Community) | 12 |
| Minecraft | `gamegrab minecraft` | PrismarineJS minecraft-data (MIT) + eigene Installation | 7 |
| Fussball | `gamegrab fussball` | openfootball (CC0), optional football-data.org, StatsBomb | – (echte Daten) |
| Pokémon | `gamegrab pokemon` | PokéAPI | 3–7 |
| GTA V (nur Fahrzeuge) | `gamegrab gtav` | FiveM-Doku | **18** |
| Valorant | `gamegrab valorant` | valorant-api.com (Community) | 16 · Gerüst, noch nicht umgesetzt |

---

## Installation

Du brauchst Python 3.9 oder neuer.

```bash
git clone https://github.com/vonam-git/DataGrappler.git
cd DataGrappler
python -m pip install .
gamegrab liste
```

Unter Windows heisst der Befehl ebenfalls `gamegrab` (oder `python -m gamegrab`).

## Beispiele

```bash
# Fortnite: je 20 Skins, Rucksäcke und Tänze auf Deutsch -> 60 Bilder
gamegrab fortnite --typ outfit,backpack,emote --anzahl 20 --sprache de

# nur legendäre Skins der aktuellen Season, grössere Bilder, zusätzlich als ZIP
gamegrab fortnite --typ outfit --seltenheit legendary --neu-seit 2026-09-01 --bild icon --zip

# Namenssuche und Songs (nur Metadaten und Cover)
gamegrab fortnite --suche "Peely"
gamegrab fortnite --typ track --anzahl 10

# Minecraft: nur Daten (CSV)
gamegrab minecraft
# Minecraft mit Texturen und Tönen aus DEINER Installation (Standardpfad oder eigener Pfad)
gamegrab minecraft --lokal
gamegrab minecraft --lokal "C:\Users\du\AppData\Roaming\.minecraft" --typ items,bloecke --anzahl 50

# Fussball: WM 2022 mit Nationen, Spielen und Toren (Wappen erzeugt das Tool selbst)
gamegrab fussball --wettbewerb wm --saison 2022
gamegrab fussball --wettbewerb en.1 --saison 2024-25          # Premier League
gamegrab fussball --quelle statsbomb --wettbewerb wm --saison 2022 --anzahl 3   # Ereignisse pro Spiel
FOOTBALL_DATA_TOKEN=dein_schluessel gamegrab fussball --quelle football-data --wettbewerb BL1 --saison 2024

# Pokémon: 20 Pokémon mit Sprites und Schreien (OGG); Artworks mit --bild featured
gamegrab pokemon --anzahl 20
gamegrab pokemon --typ fire,water --anzahl 30 --bild featured

# GTA V: 20 Fahrzeuge (Hinweis PEGI 18!)
gamegrab gtav --anzahl 20
gamegrab gtav --typ super,sports --anzahl 10
```

### Alle Optionen

| Option | Bedeutung |
|---|---|
| `--typ a,b` | Kategorien (Fortnite: `outfit,backpack,emote,pickaxe,glider,track`; Minecraft: `items,bloecke,kreaturen,biome,rezepte,verzauberungen`; Pokémon: Pokémon-Typ wie `fire`; GTA: Klasse wie `super`) |
| `--anzahl N` | höchstens N Einträge (Fortnite/Minecraft pro Typ, Pokémon/Fussball total) |
| `--seltenheit X` | Fortnite: z.B. `legendary` |
| `--neu-seit DATUM` | nur Einträge, die seit diesem Datum dazukamen |
| `--suche TEXT` | Namenssuche |
| `--bild small\|icon\|featured` | Bildvariante, Standard `small` (spart Platz) |
| `--sprache de` | Sprache der Namen |
| `--lokal [PFAD]` | Minecraft: Texturen/Töne aus der eigenen Installation |
| `--spielversion V` | Minecraft: Java-Version, Standard die neueste |
| `--quelle Q`, `--wettbewerb W`, `--saison S` | Fussball |
| `--normalisiert` | zusätzlich `_loesung/` mit Beziehungstabellen und ERD (für die Lehrperson) |
| `--ziel ORDNER` | Ausgabeordner, Standard `./rohdaten/<spiel>_<datum>/` |
| `--zip` | zusätzlich als ZIP |
| `--max-mb 50` | bricht ab, bevor der Ordner grösser wird |

## Was herauskommt

```
rohdaten/fortnite_2026-11-10/
├── skins/            renegade_raider.png …   (type = outfit)
├── rucksaecke/       …                       (type = backpack)
├── taenze/           …  Icons der Emotes; eigene Clips legst du hier dazu
├── spitzhacken/      …                       (type = pickaxe)
├── items.csv         eine Zeile pro Item
├── items.json        dieselben Daten + Quelle, Abrufdatum, Disclaimer
├── QUELLEN.txt       Quelle, Abrufdatum, Lizenz, Disclaimer
└── .gitignore        *  (nie committen)
```

- **CSV:** UTF-8, Komma, Kopfzeile, Werte mit Komma in Anführungszeichen. Jede Zeile hat `id`, `name` und – falls vorhanden – `datei` (relativer Pfad).
- **Mehrwertige Felder stehen bewusst in einer Zelle**, getrennt mit `|`, z.B. `typen = grass|poison` oder `zutaten = 3x oak_planks|2x stick`. Das Zerlegen ist deine Aufgabe (siehe unten).
- **Dateinamen** sind bereinigt wie in Durchblick: Kleinbuchstaben, `ä→ae`, Leerzeichen→`_`, nur `a-z 0-9 . _ -`, bei gleichen Namen `_2`, `_3`.
- **Videos:** Fortnite liefert pro Cosmetic höchstens eine YouTube-ID. Das Tool speichert nur den Link (`video_link`) – YouTube-Videos herunterzuladen verbieten die Nutzungsbedingungen. Eigene Tanz-Clips nimmst du im Spiel selbst auf (Bildschirmaufnahme) und legst sie in `taenze/`. Die Werkstatt macht daraus 5-Sekunden-Clips.

## Weiter in Durchblick

1. Durchblick starten, Reiter **🛠️ Werkstatt → 1 · Rohdaten**.
2. Den ganzen Ordner (z.B. `rohdaten/fortnite_2026-11-10`) hineinziehen oder das ZIP wählen.
3. Ablage im ZIP: **«In Benutzerordner einsortieren»**, Benutzer **`gamer`**, Projektname z.B. `fortnite`.
4. **🗜️ Rohdaten verkleinern** → weiter zu **2 · CSV generieren** → **3 · CSV prüfen** (Ziel: ✅ gültig).
5. Nach dem Import zeigt die Galerie Bilder und Audio, gruppiert nach Kategorie (Ordner).

Tipps:
- Die Werkstatt überspringt Textdateien über 200 KB (Einstellung «Maximalgrösse übrige Dateien»). Bei grossen Minecraft-Läufen meldet `gamegrab` das. Erhöhe dann die Einstellung oder nimm `--anzahl`.
- Wenn du mit `--normalisiert` gearbeitet hast: Den Ordner `_loesung/` vor dem Weitergeben an Lernende entfernen.

## Von der Rohform zum ERD

Die CSVs sind absichtlich **nicht normalisiert**. So gehst du vor:

1. **Entitäten finden:** Jede CSV ist ein Kandidat. Welche Spalten wiederholen sich (z.B. `seltenheit`, `set`, `klasse`)? Das sind eigene Entitäten.
2. **1. Normalform:** Zellen mit `|` zerlegen. Aus `pokemon.typen = grass|poison` wird eine Tabelle `pokemon_typ(pokemon_id, typ_id, slot)`.
3. **2./3. Normalform:** Attribute, die nur von einem Teil des Schlüssels oder von einem Nicht-Schlüssel abhängen, auslagern (z.B. `generation` gehört zur Art, nicht zum Pokémon).
4. **Beziehungen mit Attributen** erkennen: Menge im Rezept, Slot beim Typ, Lernart und Level bei Attacken, Saison beim Vertrag.
5. **Sonderfälle:** Rekursion (Pokémon-Entwicklung Art → Art), zwei Beziehungen zur selben Tabelle (Spiel → Heimverein und Gastverein), schwache Entität (Tor gehört zu einem Spiel: Schlüssel `spiel_id + nr`).

| Spiel | gut für |
|---|---|
| Fussball | alle Muster: 1:n, n:m mit Zeitbezug (Vertrag pro Saison), zwei Beziehungen zur selben Entität, schwache Entität (Tor) |
| Minecraft | n:m mit Attribut (Rezept–Zutat mit Menge), Block–Werkzeug, Kreatur–Drop |
| Pokémon | n:m mit Attributen, rekursive Beziehung (Entwicklung), Typ–Typ mit Schadensfaktor |
| Fortnite, GTA V | flach – erfinde eine eigene Entität, z.B. **Loadout** (Skin + Rucksack + Tanz + Spitzhacke) mit einer n:m-Tabelle, oder **Garage/Rennen** mit Fahrzeugen. Die Daten dafür erfasst du selbst, ohne echte Personen. |

Für Lehrpersonen: `--normalisiert` erzeugt in `_loesung/` die fertigen Entitäts- und Beziehungstabellen und `erd.md` (Mermaid). Alle Fremdschlüssel werden vor dem Schreiben geprüft und verweisen auf existierende IDs.

## Urheberrecht und Datenschutz

Dies ist keine Rechtsberatung.

- **Epic Games:** Die Fan Content Policy erlaubt nicht-kommerzielle Fan-Inhalte und verlangt einen Disclaimer. Er steht in `QUELLEN.txt` und `items.json`.
- **Minecraft:** Texturen und Töne gehören Mojang. Sie werden nie aus dem Internet geladen, sondern nur mit `--lokal` aus **deiner** Installation gelesen – und nur die ausgewählten Dateien. Spieler-Skins und Benutzernamen fragt das Tool nie ab.
- **Fussball:** Spielerdaten sind Personendaten (nDSG). Gespeichert werden nur Name, Position, Nation und Verein, **keine** Geburtsdaten, Grössen, Gewichte oder Fotos. Vereinslogos sind Marken: Das Tool erzeugt eigene Wappen (zwei Farbflächen, ohne Text). StatsBomb verlangt die Quellenangabe «Data provided by StatsBomb».
- **GTA V** ist ab 18. Es werden nur Fahrzeuge geladen (keine Militärfahrzeuge, Waffen, Figuren oder Story). Den Einsatz vorher mit der Schulleitung klären.
- **Keine Personendaten:** keine Spielerstatistiken, Accounts oder Benutzernamen, auch wenn eine API das könnte.
- **Keine Downloads** von YouTube oder anderen Videoplattformen, keine Leaks.

### Fair zur API und sicher

- höchstens 2 Anfragen pro Sekunde (FiveM 1/s, football-data 10/Minute), User-Agent `gamegrab/1.0 (Schulprojekt)`
- Cache in `.gamegrab-cache/` (Listen 24 h, Dateien dauerhaft): Ein zweiter Lauf lädt nichts neu, ein abgebrochener Lauf setzt fort.
- bei HTTP 429 wartet das Tool so lange, wie der Server mit `Retry-After` verlangt
- nur HTTPS und nur Hosts aus einer festen Liste pro Spiel (auch bei Weiterleitungen)
- höchstens 5 MB pro Datei, Content-Type und Dateisignatur werden geprüft (nur Bilder und Audio)
- Pfade aus API-Daten werden bereinigt (kein `..`, keine absoluten Pfade)

## Neues Spiel hinzufügen

Ein neues Spiel braucht **eine neue Datei** in `gamegrab/adapters/` und einen Test – der Kern bleibt unverändert.

```python
# gamegrab/adapters/meinspiel.py
from .base import Adapter

class MeinSpiel(Adapter):
    name = "meinspiel"                     # Befehl: gamegrab meinspiel
    titel = "Mein Spiel"
    alter = "12"                           # PEGI
    beschreibung = "Was das Spiel liefert"
    entitaeten = {"items": ["id", "name", "kategorie", "datei"]}
    erlaubte_hosts = ("api.meinspiel.example",)
    quelle = "https://api.meinspiel.example"
    lizenz = "Richtlinie des Herstellers: …"
    disclaimer = "…"

    def hole(self, opt, http, namen):
        liste = http.get_json("https://api.meinspiel.example/items")      # 1 Aufruf, mit Cache
        zeilen = []
        for it in liste[: opt.anzahl or None]:
            datei = self.datei(namen, "items", it["name"], "png", it["bild_url"])  # lädt der Kern
            zeilen.append({"id": it["id"], "name": it["name"], "kategorie": "items", "datei": datei})
        return {"items": zeilen}
```

Für die Lösung (`--normalisiert`) zusätzlich `loesung_schema` und `loesung()` ergänzen (siehe `pokemon.py`).
Ein Gerüst mit Hinweisen zur Quelle liegt bereits in `valorant.py`.

## Entwicklung

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

Die Tests laufen ohne Internet: Sie verwenden aufgezeichnete, gekürzte Beispielantworten in `tests/daten/`.
GitHub Actions prüft auf Python 3.9 und 3.13. Gearbeitet wird auf `develop`, stabile Stände kommen nach `main`.

## Lizenz

Code: MIT. Die geladenen Daten, Bilder und Töne stehen unter den Bedingungen ihrer Quellen (siehe `QUELLEN.txt` in jedem Ausgabeordner).
