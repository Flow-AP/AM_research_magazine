"""Kurz-Abstracts zu jeder Meldung.

Ablauf je Artikel:
1. Originalseite abrufen und Fließtext extrahieren (Fallback: Teaser/Abstract aus dem Feed).
2. Mit Claude einen kurzen deutschen Abstract schreiben lassen, sofern das Paket
   `anthropic` installiert und ein API-Schlüssel vorhanden ist (ANTHROPIC_API_KEY
   oder `ant auth login`).
3. Sonst: extraktiver Abstract aus den ersten Sätzen des Textes.
"""

from __future__ import annotations

import concurrent.futures
import os
import re
from html.parser import HTMLParser

from .quellen import abrufen, html_zu_text, kuerzen

MODELL = os.environ.get("AM_MAGAZIN_MODELL", "claude-opus-5-5")
MAX_VOLLTEXT = 12000  # Zeichen, die an das Modell gehen

SYSTEM_PROMPT = """Du schreibst Kurz-Abstracts für ein deutschsprachiges Fachmagazin zur additiven Fertigung.
Leser sind Ingenieurinnen, Forschende und Fachleute aus der Industrie.

Schreibe zu der Meldung einen Abstract auf Deutsch:
- 2 bis 3 Sätze, höchstens 70 Wörter, sachlicher Magazinstil, kein Marketington.
- Nenne das Wesentliche: Wer hat was gemacht oder angekündigt, welches Verfahren oder Material,
  welches Ergebnis oder welche Kennzahl, und warum es für die additive Fertigung relevant ist.
- Gängige Fachbegriffe und Abkürzungen (LPBF, DED, Binder Jetting, Ti-6Al-4V …) bleiben erhalten.
- Verwende ausschließlich Informationen aus dem gelieferten Text. Erfinde keine Zahlen, Namen oder Daten.
  Wenn der Text wenig hergibt, schreibe entsprechend kürzer.
- Gib nur den Abstract-Text aus: keine Überschrift, keine Einleitung, keine Aufzählung, kein Markdown."""


# --------------------------------------------------------------------------- Volltext

class _Absaetze(HTMLParser):
    """Sammelt den Text aller <p>-Elemente, bevorzugt innerhalb von <article>/<main>."""

    def __init__(self):
        super().__init__()
        self.alle: list[str] = []
        self.im_artikel: list[str] = []
        self._p = None
        self._tiefe_artikel = 0
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("article", "main"):
            self._tiefe_artikel += 1
        elif tag in ("script", "style", "nav", "footer", "aside", "form"):
            self._skip += 1
        elif tag == "p" and not self._skip:
            self._p = []

    def handle_endtag(self, tag):
        if tag in ("article", "main") and self._tiefe_artikel:
            self._tiefe_artikel -= 1
        elif tag in ("script", "style", "nav", "footer", "aside", "form") and self._skip:
            self._skip -= 1
        elif tag == "p" and self._p is not None:
            text = re.sub(r"\s+", " ", "".join(self._p)).strip()
            if len(text) > 60:
                self.alle.append(text)
                if self._tiefe_artikel:
                    self.im_artikel.append(text)
            self._p = None

    def handle_data(self, data):
        if self._p is not None and not self._skip:
            self._p.append(data)


def volltext_lesen(url: str) -> str:
    """Liest den Fließtext einer Artikelseite. Gibt '' zurück, wenn das nicht klappt."""
    if not url or not url.startswith("http"):
        return ""
    try:
        roh = abrufen(url)
    except Exception:
        return ""
    if roh[:5] == b"%PDF-":
        return ""
    p = _Absaetze()
    try:
        p.feed(roh.decode("utf-8", errors="replace"))
    except Exception:
        return ""
    absaetze = p.im_artikel if len(" ".join(p.im_artikel)) > 300 else p.alle
    return html_zu_text(" ".join(absaetze))[:MAX_VOLLTEXT]


# --------------------------------------------------------------------------- Abstract-Varianten

def abstract_extraktiv(text: str, max_zeichen: int = 420) -> str:
    """Einfacher Fallback ohne KI: die ersten Sätze des Textes."""
    text = re.sub(r"^\s*(Abstract|Purpose|Zusammenfassung)[:.]?\s*", "", text or "", flags=re.I)
    return kuerzen(text.strip(), max_zeichen)


_client = None
_client_fehler = None


def _ki_client():
    """Erzeugt einmalig einen Anthropic-Client. Gibt None zurück, wenn nicht verfügbar."""
    global _client, _client_fehler
    if _client is not None or _client_fehler is not None:
        return _client
    try:
        import anthropic
        client = anthropic.Anthropic()
        profil = os.path.isdir(os.path.expanduser("~/.config/anthropic"))
        if not (getattr(client, "api_key", None) or getattr(client, "auth_token", None) or profil):
            _client_fehler = ("Kein API-Schlüssel gefunden – ANTHROPIC_API_KEY setzen "
                              "oder einmal 'ant auth login' ausführen")
        else:
            _client = client
    except ImportError:
        _client_fehler = "Paket 'anthropic' nicht installiert (pip install anthropic)"
    except Exception as e:  # z. B. fehlende Zugangsdaten
        _client_fehler = f"{type(e).__name__}: {e}"
    return _client


def _ki_abschalten(grund: str):
    global _client, _client_fehler
    _client, _client_fehler = None, grund


def ki_status() -> dict:
    client = _ki_client()
    return {"verfuegbar": client is not None, "modell": MODELL, "hinweis": _client_fehler}


def abstract_ki(artikel: dict, text: str) -> str:
    import anthropic

    client = _ki_client()
    nutzer = (f"Titel: {artikel.get('titel', '')}\n"
              f"Quelle: {artikel.get('quelle', '')}\n"
              f"Autoren: {artikel.get('autoren', '') or 'unbekannt'}\n\n"
              f"Text der Meldung:\n{text}")
    antwort = client.beta.messages.create(
        model=MODELL,
        max_tokens=4000,
        output_config={"effort": "low"},
        # Lehnt das Modell eine Anfrage ab, übernimmt automatisch ein passendes Ersatzmodell.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": nutzer}],
    )
    if antwort.stop_reason == "refusal":
        raise anthropic.AnthropicError("Anfrage vom Modell abgelehnt")
    ergebnis = "".join(b.text for b in antwort.content if b.type == "text").strip()
    if not ergebnis:
        raise anthropic.AnthropicError("Leere Antwort")
    return re.sub(r"\s+", " ", ergebnis)


def abstract_fuer(artikel: dict, ki: bool = True, volltext: bool = True) -> dict:
    """Erzeugt den Abstract für einen Artikel. Rückgabe: {'abstract', 'methode', 'hinweis'}."""
    text = volltext_lesen(artikel.get("link", "")) if volltext else ""
    basis = "Volltext"
    teaser = artikel.get("text", "") or ""
    if len(text) < len(teaser) + 200:  # Seite gesperrt oder kaum Text -> Teaser/Abstract aus dem Feed
        text, basis = (teaser + ("\n\n" + text if text else "")).strip(), "Teaser"
    if not text:
        return {"abstract": "", "methode": "keine", "hinweis": "Kein Text verfügbar"}

    hinweis = None
    if ki and _ki_client() is not None:
        try:
            return {"abstract": abstract_ki(artikel, text), "methode": f"KI ({basis})", "hinweis": None}
        except Exception as e:  # API-Fehler -> extraktiver Fallback
            hinweis = f"KI nicht möglich ({type(e).__name__}: {str(e)[:160]})"
            if type(e).__name__ in ("AuthenticationError", "PermissionDeniedError", "TypeError"):
                _ki_abschalten(hinweis)  # Zugang fehlt: nicht für jeden Artikel erneut versuchen
    elif ki:
        hinweis = _client_fehler
    return {"abstract": abstract_extraktiv(text), "methode": f"Auszug ({basis})", "hinweis": hinweis}


def abstracts_erzeugen(artikel: list[dict], ki: bool = True, volltext: bool = True,
                       parallel: int = 4) -> dict[str, dict]:
    """Erzeugt Abstracts für alle Artikel parallel. Rückgabe: {artikel_id: ergebnis}."""
    ergebnisse: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = {pool.submit(abstract_fuer, a, ki, volltext): a["id"] for a in artikel}
        for fut in concurrent.futures.as_completed(futures):
            try:
                ergebnisse[futures[fut]] = fut.result()
            except Exception as e:
                ergebnisse[futures[fut]] = {"abstract": "", "methode": "Fehler", "hinweis": str(e)}
    return ergebnisse
