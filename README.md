# AM Research Magazine

Ein kleines Programm mit Browser-Oberfläche. Es sucht im Netz nach neuen Meldungen aus der **additiven Fertigung**, zum Beispiel:

* Forschungsergebnisse,
* Ankündigungen von Herstellern,
* neue Maschinen,
* Materialien,
* Markttrends.

Daraus setzt es ein Magazin als **LaTeX-Datei** und auf Wunsch direkt als **PDF**.

## Voraussetzungen

* **Python 3.9 oder neuer.** Es werden keine weiteren Pakete benötigt, nur die Standardbibliothek.
* **Optional für KI-Abstracts:** `pip install anthropic` und ein Claude-API-Schlüssel.
  Den Schlüssel setzt du als Umgebungsvariable `ANTHROPIC_API_KEY` oder hinterlegst ihn einmalig mit `ant auth login`.
* **Für das PDF eine LaTeX-Installation:** TeX Live, MiKTeX oder MacTeX, mit `latexmk` oder `pdflatex` im Pfad.
  Ohne LaTeX lädst du einfach die `.tex`-Datei herunter und übersetzt sie zum Beispiel in Overleaf.

## Start

```bash
python3 magazin.py
```

Unter Windows startest du stattdessen `start.bat` per Doppelklick. Der Browser öffnet sich auf `http://127.0.0.1:8765/`.

1. **Suche:** Zeitraum, **Werkstoffbereich** (Alle / Metall / Kunststoff), Anzahl pro Quelle und Quellen wählen.
   Dann auf *Netz durchsuchen* klicken.
   *In Google Scholar öffnen* öffnet dieselbe Suche, nach Datum sortiert, direkt in Google Scholar.
2. **Auswahl:** Meldungen an- oder abhaken, die Rubrik ändern und Zusammenfassungen direkt bearbeiten.
   Danach auf *Abstracts schreiben* klicken: Zu jeder ausgewählten Meldung entsteht ein kurzer deutscher Abstract.
   Er steht im PDF direkt unter dem Link zur Quelle und lässt sich vorher im Feld darunter bearbeiten.
3. **Ausgabe:** Titel, Ausgabe und Editorial eintragen, dann *TeX-Datei herunterladen* oder *PDF erzeugen* wählen.
   Alle Dateien landen zusätzlich im Ordner `ausgaben/`.

### Ohne Oberfläche (z. B. wöchentlich per Cron/Aufgabenplanung)

```bash
python3 magazin.py --cli --tage 7 --pdf
```

Mit Abstracts: `python3 magazin.py --cli --tage 7 --abstracts --pdf`.
Weitere Optionen zeigt `python3 magazin.py --help`, z. B. `--ohne-ki` und `--ohne-teaser`.

## Werkstoffbereich: Metall oder Kunststoff

Bei **Metall** oder **Kunststoff** passiert zweierlei:

1. Die Forschungsquellen (arXiv, Crossref, OpenAlex, Google Scholar) werden gezielt mit Werkstoff-Suchbegriffen abgefragt.
2. Alle Meldungen werden anschließend anhand von Schlagworten geprüft. Beispiele:
   * Metall: LPBF, DED, WAAM, Ti-6Al-4V, 316L, Inconel …
   * Kunststoff: FFF, SLA, SLS, MJF, PA12, PEEK, Resin …

Meldungen, die zu beiden Bereichen passen, erscheinen in beiden.
Meldungen ohne erkennbaren Werkstoff fallen weg, etwa reine Finanz- oder Personalnachrichten.
Mit dem Häkchen *auch Meldungen ohne erkennbaren Werkstoff* behältst du sie.
In der Auswahlliste zeigt eine Markierung an jeder Meldung, welcher Bereich erkannt wurde.

Die Begriffe stehen in `config/quellen.json` unter `werkstoffe` und lassen sich erweitern.
Dort kannst du auch einen weiteren Bereich anlegen, etwa `keramik`; er erscheint dann automatisch als Auswahl.
Abkürzungen in Großbuchstaben (ABS, PLA, SLM …) zählen nur in genau dieser Schreibweise. So wird z. B. „abs“ in „abstract“ nicht erkannt.

CLI: `./start.sh --cli --werkstoff metall --pdf`

## Google Scholar

Google bietet für Scholar keine offizielle Schnittstelle.
Automatisches Abfragen der Webseite ist laut Nutzungsbedingungen nicht erlaubt und wird schnell blockiert.
Es gibt daher zwei Wege:

1. **Button „In Google Scholar öffnen“:** Er öffnet die passende Suche, nach Datum sortiert, in deinem Browser.
   Das ist kostenlos und braucht keine Einrichtung.
2. **Quelle „Google Scholar (via SerpAPI)“:** Die Treffer landen automatisch im Heft.
   Dafür brauchst du einen Schlüssel von https://serpapi.com. Es gibt ein kleines kostenloses Monatskontingent, danach kostet es.
   Jede Suche verbraucht eine Anfrage. Den Schlüssel trägst du so ein und setzt danach in der Oberfläche den Haken bei der Quelle:
   ```bash
   echo 'export SERPAPI_KEY="DEIN-SERPAPI-SCHLÜSSEL"' >> ~/.bashrc && source ~/.bashrc
   ```

Scholar liefert nur kurze Snippets und kein exaktes Datum. Bei sehr neuen Treffern errechnet das Programm das Datum aus „vor X Tagen“.
Als kostenlose Ergänzung mit ähnlicher Abdeckung und vollständigen Abstracts ist **OpenAlex** standardmäßig aktiv.

## Abstracts

So entsteht der Abstract zu jeder Meldung:

1. Das Programm liest die verlinkte Originalseite und zieht den Fließtext heraus.
   Ist die Seite gesperrt oder enthält kaum Text, nimmt es stattdessen den Teaser bzw. das Paper-Abstract aus dem Feed.
2. **Mit KI:** Claude (`claude-opus-5-5`, Aufwand `low`) schreibt daraus 2–3 sachliche Sätze auf Deutsch, höchstens 70 Wörter.
   Claude darf dabei nur Informationen aus dem Text verwenden.
   Lehnt das Modell eine Anfrage ab, springt automatisch ein Ersatzmodell ein (serverseitiger Fallback).
   Ein anderes Modell stellst du über die Umgebungsvariable `AM_MAGAZIN_MODELL` ein.
3. **Ohne KI** (kein Paket oder kein Schlüssel): Als Abstract dienen die ersten Sätze des Textes. Sie bleiben in der Originalsprache.

An jedem Abstract zeigt eine Markierung, wie er entstanden ist, zum Beispiel „KI (Volltext)“ oder „Auszug (Teaser)“.
Die KI-Abstracts solltest du kurz gegenlesen, bevor das Heft rausgeht.
Jeder Abstract ist ein API-Aufruf. Grobe Kosten mit `claude-opus-5-5`: etwa 1–2 US-Cent pro Abstract,
also rund 0,50–2 $ für eine Ausgabe mit 40–100 Meldungen.
Deutlich günstiger, mit etwas schlichteren Texten, ist Haiku:
`export AM_MAGAZIN_MODELL=claude-haiku-5-5`. Das kostet weniger als 0,05 $ pro Ausgabe.
Mit „nur fehlende“ werden bereits vorhandene Abstracts nicht noch einmal bezahlt.

## Quellen

Alle Quellen stehen in `config/quellen.json` und lassen sich dort an- und abschalten oder ergänzen.

| Typ | Wofür | Felder |
|---|---|---|
| `rss` | News-Seiten (3DPrint.com, 3D Printing Industry, VoxelMatters, 3Druck.com, …) | `url` |
| `arxiv` | Preprints über die arXiv-API | `suche` (arXiv-Suchsyntax) |
| `crossref` | Neue Artikel aus Fachjournalen (Additive Manufacturing, Rapid Prototyping Journal, …) | `issn` und/oder `suche` |
| `openalex` | Offene Forschungsdatenbank, kostenlos, mit Abstracts | `suche` (Boolesche Suche) |
| `scholar` | Google Scholar über SerpAPI (Schlüssel nötig, siehe unten) | `suche` |

Das Feld `rubrik` legt fest, wo eine Quelle einsortiert wird:

* `auto` ordnet jede Meldung anhand der Schlagworte unter `rubriken` ein,
* eine feste Rubrik-ID wie `forschung` sortiert alle Meldungen dieser Quelle dorthin.

Die Rubriken selbst kannst du dort ebenfalls umbenennen, ergänzen oder umsortieren.
Ihre Reihenfolge ist auch die Reihenfolge im Heft.

## Eigene LaTeX-Vorlage

Lege deine Vorlage als `.tex` in den Ordner `vorlagen/`. Sie erscheint dann automatisch in der Auswahl.

Das Programm ersetzt diese Platzhalter (nicht in Kommentarzeilen):

| Platzhalter | Inhalt |
|---|---|
| `<<TITEL>>`, `<<UNTERTITEL>>`, `<<AUSGABE>>` | Angaben aus der Oberfläche |
| `<<DATUM>>` | heutiges Datum, z. B. `17.~November 2026` |
| `<<ANZAHL>>` | Anzahl der Meldungen |
| `<<EDITORIAL>>` | `\editorial{…}` oder leer |
| `<<INHALT>>` | alle Rubriken mit Artikeln |

`<<INHALT>>` besteht aus Aufrufen dieser Makros, die deine Vorlage definieren muss:

```latex
\rubrik{Titel der Rubrik}
\artikel{Titel}{Quelle}{Datum}{URL}{Autoren}{Teaser}{Abstract}   % #6 und #7 können leer sein
...
\rubrikende
\editorial{Text}
```

Als Ausgangspunkt dient `vorlagen/standard.tex`. Alle Texte kommen bereits LaTeX-sicher escaped an.

## Aufbau

```
magazin.py            Webserver + CLI
am_magazin/quellen.py Abruf (RSS/Atom, arXiv, Crossref), Dubletten, Rubriken
am_magazin/abstract.py Volltext lesen und Abstracts schreiben (Claude oder Textauszug)
am_magazin/latex.py   LaTeX-Erzeugung und PDF-Kompilierung
static/index.html     Browser-Oberfläche
config/quellen.json   Quellen und Rubriken
vorlagen/             LaTeX-Vorlagen
ausgaben/             erzeugte .tex/.pdf (nicht im Git)
```

## Hinweise

* Die Zusammenfassungen sind die Teaser bzw. Abstracts der Originalquellen. Sie sind meist englisch.
* Der Server läuft nur lokal (`127.0.0.1`) und ist nicht von außen erreichbar.
* Ist eine Quelle nicht erreichbar, zeigt die Oberfläche das an. Die übrigen Quellen werden trotzdem verarbeitet.
