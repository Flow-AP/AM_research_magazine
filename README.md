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

1. **Suche:** Zeitraum, Anzahl pro Quelle und Quellen wählen, dann auf *Netz durchsuchen* klicken.
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
Jeder Abstract ist ein API-Aufruf: Die Kosten richten sich nach der Zahl der Meldungen, pro Ausgabe meist nur wenige Cent.

## Quellen

Alle Quellen stehen in `config/quellen.json` und lassen sich dort an- und abschalten oder ergänzen.

| Typ | Wofür | Felder |
|---|---|---|
| `rss` | News-Seiten (3DPrint.com, 3D Printing Industry, VoxelMatters, 3Druck.com, …) | `url` |
| `arxiv` | Preprints über die arXiv-API | `suche` (arXiv-Suchsyntax) |
| `crossref` | Neue Artikel aus Fachjournalen (Additive Manufacturing, Rapid Prototyping Journal, …) | `issn` und/oder `suche` |

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
