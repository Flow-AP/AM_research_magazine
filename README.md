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
* **Für das PDF eine LaTeX-Installation:** TeX Live, MiKTeX oder MacTeX, mit `latexmk` oder `pdflatex` im Pfad.
  Ohne LaTeX lädst du einfach die `.tex`-Datei herunter und übersetzt sie zum Beispiel in Overleaf.

## Start

```bash
python3 magazin.py
```

Unter Windows startest du stattdessen `start.bat` per Doppelklick. Der Browser öffnet sich auf `http://127.0.0.1:8765/`.

1. **Suche:** Zeitraum, Anzahl pro Quelle und Quellen wählen, dann auf *Netz durchsuchen* klicken.
2. **Auswahl:** Meldungen an- oder abhaken, die Rubrik ändern und Zusammenfassungen direkt bearbeiten.
3. **Ausgabe:** Titel, Ausgabe und Editorial eintragen, dann *TeX-Datei herunterladen* oder *PDF erzeugen* wählen.
   Alle Dateien landen zusätzlich im Ordner `ausgaben/`.

### Ohne Oberfläche (z. B. wöchentlich per Cron/Aufgabenplanung)

```bash
python3 magazin.py --cli --tage 7 --pdf
```

Weitere Optionen zeigt `python3 magazin.py --help`.

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
\artikel{Titel}{Quelle}{Datum}{URL}{Autoren}{Zusammenfassung}
...
\rubrikende
\editorial{Text}
```

Als Ausgangspunkt dient `vorlagen/standard.tex`. Alle Texte kommen bereits LaTeX-sicher escaped an.

## Aufbau

```
magazin.py            Webserver + CLI
am_magazin/quellen.py Abruf (RSS/Atom, arXiv, Crossref), Dubletten, Rubriken
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
