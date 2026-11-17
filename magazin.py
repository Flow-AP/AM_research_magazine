#!/usr/bin/env python3
"""AM-Magazin: sammelt Neuigkeiten aus der additiven Fertigung und setzt sie als LaTeX/PDF.

Start (Browser-Oberfläche):   python3 magazin.py
Ohne Browser (z. B. Cron):     python3 magazin.py --cli --tage 7 --pdf
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from am_magazin import abstract, latex, quellen

BASIS = Path(__file__).resolve().parent
CONFIG = BASIS / "config" / "quellen.json"
VORLAGEN = BASIS / "vorlagen"
AUSGABEN = BASIS / "ausgaben"
STATIC = BASIS / "static"


def config_laden() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def vorlagen_liste() -> list[str]:
    return sorted(p.name for p in VORLAGEN.glob("*.tex"))


def vorlage_laden(name: str | None) -> str:
    name = Path(name or "standard.tex").name  # keine Pfade von außen
    pfad = VORLAGEN / name
    if not pfad.exists():
        pfad = VORLAGEN / "standard.tex"
    return pfad.read_text(encoding="utf-8")


def dateiname(titel: str) -> str:
    return f"{dt.date.today().isoformat()}_am-magazin"


def tex_aus_anfrage(daten: dict) -> str:
    cfg = config_laden()
    return latex.tex_erzeugen(
        vorlage_laden(daten.get("vorlage")),
        [a for a in daten.get("artikel", []) if a.get("ausgewaehlt", True)],
        cfg["rubriken"],
        titel=daten.get("titel") or "AM-Magazin",
        untertitel=daten.get("untertitel", ""),
        ausgabe=daten.get("ausgabe", ""),
        editorial=daten.get("editorial", ""),
        teaser=bool(daten.get("teaser", True)),
    )


def speichern(name: str, inhalt: bytes | str) -> Path:
    AUSGABEN.mkdir(exist_ok=True)
    pfad = AUSGABEN / name
    if isinstance(inhalt, str):
        pfad.write_text(inhalt, encoding="utf-8")
    else:
        pfad.write_bytes(inhalt)
    return pfad


# =============================================================================== HTTP-Server

class Handler(BaseHTTPRequestHandler):
    server_version = "AMMagazin/1.0"

    def log_message(self, fmt, *args):  # ruhigere Konsole
        sys.stderr.write("  %s\n" % (fmt % args))

    def _senden(self, code: int, inhalt: bytes, typ: str, download: str | None = None):
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(inhalt)))
        if download:
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(download)}")
        self.end_headers()
        self.wfile.write(inhalt)

    def _json(self, obj, code=200):
        self._senden(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _body(self) -> dict:
        laenge = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(laenge) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._senden(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/config":
            cfg = config_laden()
            self._json({
                "quellen": cfg["quellen"],
                "rubriken": [{"id": r["id"], "titel": r["titel"]} for r in cfg["rubriken"]],
                "vorlagen": vorlagen_liste(),
                "compiler": latex.compiler_verfuegbar(),
                "ki": abstract.ki_status(),
                "werkstoffe": [{"id": k, "titel": w["titel"], "suchbegriffe": w.get("suchbegriffe", [])}
                               for k, w in cfg.get("werkstoffe", {}).items()],
                "serpapi": bool(os.environ.get("SERPAPI_KEY")),
            })
        else:
            self._senden(404, b"Nicht gefunden", "text/plain; charset=utf-8")

    def do_POST(self):
        try:
            daten = self._body()
        except json.JSONDecodeError:
            return self._json({"fehler": "Ungültige Anfrage"}, 400)

        if self.path == "/api/suche":
            ergebnis = quellen.suchen(
                config_laden(),
                quellen_ids=daten.get("quellen"),
                tage=int(daten.get("tage", 7)),
                max_pro_quelle=int(daten.get("max_pro_quelle", 15)),
                filter_text=daten.get("filter", ""),
                max_zeichen=int(daten.get("max_zeichen", 700)),
                werkstoff=daten.get("werkstoff", "alle"),
                unklare_behalten=bool(daten.get("unklare_behalten", False)),
            )
            return self._json(ergebnis)

        if self.path == "/api/abstracts":
            ergebnis = abstract.abstracts_erzeugen(
                daten.get("artikel", []),
                ki=bool(daten.get("ki", True)),
                volltext=bool(daten.get("volltext", True)),
            )
            return self._json({"abstracts": ergebnis})

        if self.path == "/api/tex":
            code = tex_aus_anfrage(daten)
            name = dateiname(daten.get("titel", "")) + ".tex"
            speichern(name, code)
            return self._senden(200, code.encode("utf-8"), "application/x-tex; charset=utf-8", name)

        if self.path == "/api/pdf":
            code = tex_aus_anfrage(daten)
            basis = dateiname(daten.get("titel", ""))
            speichern(basis + ".tex", code)
            pdf, log = latex.pdf_erzeugen(code, basis)
            if pdf is None:
                return self._json({"fehler": "PDF konnte nicht erzeugt werden.", "log": log}, 500)
            speichern(basis + ".pdf", pdf)
            return self._senden(200, pdf, "application/pdf", basis + ".pdf")

        self._json({"fehler": "Unbekannter Endpunkt"}, 404)


# =============================================================================== CLI

def cli(args):
    cfg = config_laden()
    bereich = "" if args.werkstoff == "alle" else f" im Bereich {args.werkstoff}"
    print(f"Suche Meldungen der letzten {args.tage} Tage{bereich} …")
    erg = quellen.suchen(cfg, tage=args.tage, max_pro_quelle=args.max, filter_text=args.filter or "",
                         werkstoff=args.werkstoff, unklare_behalten=args.unklare_behalten)
    for f in erg["fehler"]:
        print(f"  ! {f['quelle']}: {f['meldung']}")
    print(f"  {len(erg['artikel'])} Meldungen gefunden.")
    if args.abstracts:
        st = abstract.ki_status()
        print(f"Schreibe Abstracts ({'KI: ' + st['modell'] if st['verfuegbar'] else 'ohne KI: ' + str(st['hinweis'])}) …")
        res = abstract.abstracts_erzeugen(erg["artikel"], ki=not args.ohne_ki)
        for a in erg["artikel"]:
            a["abstract"] = res.get(a["id"], {}).get("abstract", "")
    code = latex.tex_erzeugen(vorlage_laden(args.vorlage), erg["artikel"], cfg["rubriken"],
                              titel=args.titel, untertitel=args.untertitel, ausgabe=args.ausgabe,
                              teaser=not args.ohne_teaser)
    basis = dateiname(args.titel)
    print(f"  TeX: {speichern(basis + '.tex', code)}")
    if args.pdf:
        pdf, log = latex.pdf_erzeugen(code, basis)
        if pdf is None:
            print(log[-2000:])
            sys.exit("PDF-Erzeugung fehlgeschlagen.")
        print(f"  PDF: {speichern(basis + '.pdf', pdf)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--kein-browser", action="store_true", help="Browser nicht automatisch öffnen")
    ap.add_argument("--cli", action="store_true", help="Ohne Oberfläche direkt eine Ausgabe erzeugen")
    ap.add_argument("--tage", type=int, default=7)
    ap.add_argument("--max", type=int, default=10, help="max. Meldungen pro Quelle")
    ap.add_argument("--werkstoff", default="alle", help="alle | metall | kunststoff (IDs aus config/quellen.json)")
    ap.add_argument("--unklare-behalten", action="store_true",
                    help="bei --werkstoff auch Meldungen ohne erkennbaren Werkstoff behalten")
    ap.add_argument("--filter", help="nur Meldungen mit diesen Begriffen (kommagetrennt)")
    ap.add_argument("--titel", default="AM Research Magazine")
    ap.add_argument("--untertitel", default="Neues aus der additiven Fertigung")
    ap.add_argument("--ausgabe", default=f"KW {dt.date.today().isocalendar()[1]}/{dt.date.today().year}")
    ap.add_argument("--vorlage", default="standard.tex")
    ap.add_argument("--pdf", action="store_true", help="(nur --cli) zusätzlich PDF erzeugen")
    ap.add_argument("--abstracts", action="store_true", help="(nur --cli) zu jeder Meldung einen Abstract schreiben")
    ap.add_argument("--ohne-ki", action="store_true", help="Abstracts ohne Claude, nur als Textauszug")
    ap.add_argument("--ohne-teaser", action="store_true", help="Original-Teaser nicht ins Heft übernehmen")
    args = ap.parse_args()

    if args.cli:
        return cli(args)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"AM-Magazin läuft auf {url}  (Beenden mit Strg+C)")
    if not args.kein_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")


if __name__ == "__main__":
    main()
