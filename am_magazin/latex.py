"""Erzeugt aus den gesammelten Meldungen eine .tex-Datei und optional ein PDF."""

from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]

_TEX_ZEICHEN = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}

_UNICODE = {
    "™": r"\texttrademark{}", "®": r"\textregistered{}", "©": r"\textcopyright{}",
    "°": r"\textdegree{}", "µ": r"\textmu{}", "μ": r"\textmu{}", "×": r"\texttimes{}",
    "±": r"\textpm{}", "€": r"\texteuro{}", "·": r"\textperiodcentered{}",
    "≈": r"\ensuremath{\approx}", "≤": r"\ensuremath{\leq}", "≥": r"\ensuremath{\geq}",
    "→": r"\ensuremath{\rightarrow}", "←": r"\ensuremath{\leftarrow}", "−": "-",
    "‐": "-", "‑": "-", "\u00a0": "~", "\u2009": r"\,", "\u202f": r"\,",
    "²": r"\textsuperscript{2}", "³": r"\textsuperscript{3}", "¹": r"\textsuperscript{1}",
    "₂": r"\textsubscript{2}", "₃": r"\textsubscript{3}", "Ω": r"\ensuremath{\Omega}",
}
_GRIECHISCH = {chr(0x3B1 + i): n for i, n in enumerate(
    ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa",
     "lambda", "mu", "nu", "xi", "o", "pi", "rho", "varsigma", "sigma", "tau", "upsilon",
     "phi", "chi", "psi", "omega"])}

# Zeichen, die pdflatex mit T1/utf8 sicher setzen kann
_ERLAUBT_PUNKT = set("–—‘’‚“”„…•‹›«»")


def tex(text: str | None) -> str:
    """Escaped beliebigen Text für LaTeX und entschärft exotische Unicode-Zeichen."""
    if not text:
        return ""
    raus = []
    for ch in str(text):
        if ch in _TEX_ZEICHEN:
            raus.append(_TEX_ZEICHEN[ch])
        elif ch in _UNICODE:
            raus.append(_UNICODE[ch])
        elif ch in _GRIECHISCH:
            n = _GRIECHISCH[ch]
            raus.append(r"\ensuremath{\%s}" % n if n != "o" else "o")
        elif ord(ch) < 0x180 or ch in _ERLAUBT_PUNKT:
            if ch in "\t\r\n":
                raus.append(" ")
            elif ord(ch) >= 32:
                raus.append(ch)
        else:
            # Rest: auf Grundbuchstaben zurückführen (z. B. ﬁ → fi) oder weglassen
            ersatz = unicodedata.normalize("NFKD", ch)
            ersatz = "".join(c for c in ersatz if ord(c) < 0x180 and not unicodedata.combining(c))
            raus.append(tex(ersatz) if ersatz and ersatz != ch else "")
    return "".join(raus)


def tex_url(url: str | None) -> str:
    """URL für \\href: kritische Zeichen prozentkodieren, % und # escapen."""
    if not url:
        return ""
    url = re.sub(r"[\s\\{}~^`\"<>|]", lambda m: "%%%02X" % ord(m.group()), url.strip())
    return url.replace("%", r"\%").replace("#", r"\#")


def datum_deutsch(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        d = dt.datetime.fromisoformat(iso)
    except ValueError:
        return ""
    return f"{d.day}.\\,{d.month}.\\,{d.year}"


def artikel_tex(a: dict, teaser: bool = True) -> str:
    return "\\artikel{%s}{%s}{%s}{%s}{%s}{%s}{%s}\n" % (
        tex(a.get("titel")), tex(a.get("quelle")), datum_deutsch(a.get("datum")),
        tex_url(a.get("link")), tex(a.get("autoren")),
        tex(a.get("text")) if teaser else "", tex(a.get("abstract")))


def inhalt_erzeugen(artikel: list[dict], rubriken: list[dict], teaser: bool = True) -> str:
    teile = []
    for r in rubriken:
        liste = [a for a in artikel if a.get("rubrik") == r["id"]]
        if not liste:
            continue
        teile.append(f"\\rubrik{{{tex(r['titel'])}}}\n")
        for a in liste:
            teile.append(artikel_tex(a, teaser))
        teile.append("\\rubrikende\n")
    # Artikel mit unbekannter Rubrik nicht verlieren
    bekannte = {r["id"] for r in rubriken}
    rest = [a for a in artikel if a.get("rubrik") not in bekannte]
    if rest:
        teile.append("\\rubrik{Weitere Meldungen}\n")
        for a in rest:
            teile.append(artikel_tex(a, teaser))
        teile.append("\\rubrikende\n")
    return "\n".join(teile)


def tex_erzeugen(vorlage: str, artikel: list[dict], rubriken: list[dict], titel: str,
                 untertitel: str = "", ausgabe: str = "", editorial: str = "",
                 teaser: bool = True) -> str:
    heute = dt.date.today()
    editorial_tex = ""
    if editorial.strip():
        absaetze = [tex(p.strip()) for p in re.split(r"\n\s*\n", editorial) if p.strip()]
        editorial_tex = "\\editorial{%s}" % "\\par ".join(absaetze)
    ersetzungen = {
        "<<TITEL>>": tex(titel),
        "<<UNTERTITEL>>": tex(untertitel),
        "<<AUSGABE>>": tex(ausgabe),
        "<<DATUM>>": f"{heute.day}.~{MONATE[heute.month - 1]} {heute.year}",
        "<<ANZAHL>>": str(len(artikel)),
        "<<EDITORIAL>>": editorial_tex,
        "<<INHALT>>": inhalt_erzeugen(artikel, rubriken, teaser),
    }
    zeilen = []
    for zeile in vorlage.splitlines(keepends=True):
        if not zeile.lstrip().startswith("%"):  # Platzhalter in Kommentaren unberührt lassen
            for k, v in ersetzungen.items():
                zeile = zeile.replace(k, v)
        zeilen.append(zeile)
    return "".join(zeilen)


# --------------------------------------------------------------------------- PDF

def compiler_verfuegbar() -> str | None:
    for c in ("latexmk", "pdflatex", "lualatex"):
        if shutil.which(c):
            return c
    return None


def pdf_erzeugen(tex_code: str, dateiname: str = "magazin") -> tuple[bytes | None, str]:
    """Kompiliert den TeX-Code in einem Temp-Ordner. Rückgabe: (pdf_bytes oder None, Log-Auszug)."""
    compiler = compiler_verfuegbar()
    if not compiler:
        return None, "Kein LaTeX-Compiler gefunden (latexmk/pdflatex/lualatex)."
    with tempfile.TemporaryDirectory() as tmp:
        pfad = Path(tmp) / f"{dateiname}.tex"
        pfad.write_text(tex_code, encoding="utf-8")
        if compiler == "latexmk":
            befehle = [["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", pfad.name]]
        else:
            befehle = [[compiler, "-interaction=nonstopmode", "-halt-on-error", pfad.name]] * 2
        log = ""
        for b in befehle:
            try:
                p = subprocess.run(b, cwd=tmp, capture_output=True, text=True, timeout=180,
                                   encoding="utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                return None, "LaTeX-Lauf hat zu lange gedauert (Timeout)."
            log = p.stdout[-4000:]
            if p.returncode != 0:
                return None, log
        pdf = Path(tmp) / f"{dateiname}.pdf"
        return (pdf.read_bytes() if pdf.exists() else None), log
