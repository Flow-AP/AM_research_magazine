"""Abruf von Meldungen aus RSS/Atom-Feeds, arXiv und Crossref (nur Python-Standardbibliothek)."""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import email.utils
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

USER_AGENT = "Mozilla/5.0 (compatible; AM-Magazin-Reader/1.0)"
TIMEOUT = 25

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "arxiv": "http://arxiv.org/schemas/atom",
}


# --------------------------------------------------------------------------- Hilfsfunktionen

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.teile: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "figure", "figcaption"):
            self._skip += 1
        elif tag in ("p", "br", "div", "li"):
            self.teile.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "figure", "figcaption") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.teile.append(data)


def html_zu_text(text: str | None) -> str:
    if not text:
        return ""
    p = _TextExtractor()
    try:
        p.feed(text)
        p.close()
        text = "".join(p.teile)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    # typische WordPress-Anhängsel entfernen
    text = re.sub(r"The post .{0,300}? appeared first on .{0,200}?\.?\s*$", "", text, flags=re.S)
    text = re.sub(r"Der Beitrag .{0,300}? erschien zuerst auf .{0,200}?\.?\s*$", "", text, flags=re.S)
    text = re.sub(r"\[(…|\.\.\.|&#8230;)\]", "…", text)
    return re.sub(r"\s+", " ", text).strip()


_GRIECH = {n: chr(0x3B1 + i) for i, n in enumerate(
    ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa", "lambda",
     "mu", "nu", "xi", "omicron", "pi", "rho", "varsigma", "sigma", "tau", "upsilon", "phi", "chi",
     "psi", "omega"])}
_GRIECH.update({"varepsilon": "ε", "vartheta": "θ", "varphi": "φ", "Delta": "Δ", "Omega": "Ω",
                "times": "×", "sim": "~", "approx": "≈", "pm": "±", "circ": "°", "leq": "≤", "geq": "≥"})


def latex_formeln_entfernen(text: str) -> str:
    """Wandelt einfache Inline-Formeln aus arXiv ($\\alpha$, $\\mu$m, $_2$) in Klartext um."""
    def formel(m):
        f = re.sub(r"\\([A-Za-z]+)", lambda g: _GRIECH.get(g.group(1), ""), m.group(1))
        return re.sub(r"[{}^_\\]", "", f).replace("mathrm", "")
    return re.sub(r"\$([^$]{1,60})\$", formel, text)


def kuerzen(text: str, max_zeichen: int) -> str:
    if len(text) <= max_zeichen:
        return text
    schnitt = text[:max_zeichen]
    satzende = max(schnitt.rfind(". "), schnitt.rfind("! "), schnitt.rfind("? "))
    if satzende > max_zeichen * 0.5:
        return schnitt[: satzende + 1]
    return schnitt.rsplit(" ", 1)[0] + " …"


def datum_parsen(wert: str | None) -> dt.datetime | None:
    if not wert:
        return None
    wert = wert.strip()
    try:
        d = email.utils.parsedate_to_datetime(wert)
    except (TypeError, ValueError):
        d = None
    if d is None:
        try:
            d = dt.datetime.fromisoformat(wert.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


def abrufen(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def _text(el, pfad, ns=NS) -> str:
    x = el.find(pfad, ns)
    return (x.text or "").strip() if x is not None and x.text else ""


def artikel_id(link: str, titel: str) -> str:
    return hashlib.sha1((link or titel).encode("utf-8")).hexdigest()[:12]


def _artikel(quelle, titel, link, datum, text, autoren="", tags=None, typ="news"):
    return {
        "id": artikel_id(link, titel),
        "titel": html_zu_text(titel),
        "link": link,
        "datum": datum.isoformat() if datum else None,
        "quelle": quelle["name"],
        "quelle_id": quelle["id"],
        "autoren": autoren,
        "text": html_zu_text(text),
        "tags": tags or [],
        "typ": typ,
        "rubrik": quelle.get("rubrik", "auto"),
    }


# --------------------------------------------------------------------------- Quellentypen

def lade_feed(quelle: dict, max_anzahl: int) -> list[dict]:
    daten = abrufen(quelle["url"])
    root = ET.fromstring(daten)
    ergebnis = []

    # RSS 2.0
    for item in root.iter("item"):
        titel = _text(item, "title")
        link = _text(item, "link")
        text = _text(item, "description") or _text(item, "content:encoded")
        datum = datum_parsen(_text(item, "pubDate") or _text(item, "dc:date"))
        autor = _text(item, "dc:creator") or _text(item, "author")
        tags = [c.text.strip() for c in item.findall("category") if c.text]
        ergebnis.append(_artikel(quelle, titel, link, datum, text, autor, tags))

    # Atom
    for entry in root.iter("{%s}entry" % NS["atom"]):
        titel = _text(entry, "atom:title")
        link = ""
        for l in entry.findall("atom:link", NS):
            if l.get("rel", "alternate") == "alternate":
                link = l.get("href", "")
                break
        text = _text(entry, "atom:summary") or _text(entry, "atom:content")
        datum = datum_parsen(_text(entry, "atom:published") or _text(entry, "atom:updated"))
        autoren = ", ".join(_text(a, "atom:name") for a in entry.findall("atom:author", NS))
        tags = [c.get("term") for c in entry.findall("atom:category", NS) if c.get("term")]
        ergebnis.append(_artikel(quelle, titel, link, datum, text, autoren, tags))

    return ergebnis[:max_anzahl]


def lade_arxiv(quelle: dict, max_anzahl: int) -> list[dict]:
    params = urllib.parse.urlencode({
        "search_query": quelle["suche"],
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_anzahl,
    })
    root = ET.fromstring(abrufen("https://export.arxiv.org/api/query?" + params))
    ergebnis = []
    for entry in root.findall("atom:entry", NS):
        titel = latex_formeln_entfernen(_text(entry, "atom:title"))
        link = _text(entry, "atom:id")
        text = latex_formeln_entfernen(_text(entry, "atom:summary"))
        datum = datum_parsen(_text(entry, "atom:published"))
        namen = [_text(a, "atom:name") for a in entry.findall("atom:author", NS)]
        autoren = ", ".join(namen[:4]) + (" et al." if len(namen) > 4 else "")
        tags = [c.get("term") for c in entry.findall("atom:category", NS) if c.get("term")]
        ergebnis.append(_artikel(quelle, titel, link, datum, text, autoren, tags, typ="forschung"))
    return ergebnis


def lade_crossref(quelle: dict, max_anzahl: int, seit: dt.datetime) -> list[dict]:
    filter_ = [f"from-pub-date:{seit.date().isoformat()}", "type:journal-article"]
    params = {"rows": max_anzahl, "sort": "published", "order": "desc",
              "select": "title,URL,abstract,author,published,published-online,container-title,DOI"}
    if quelle.get("issn"):
        filter_.append(f"issn:{quelle['issn']}")
    if quelle.get("suche"):
        params["query.bibliographic"] = quelle["suche"]
    params["filter"] = ",".join(filter_)
    daten = json.loads(abrufen("https://api.crossref.org/works?" + urllib.parse.urlencode(params)))
    ergebnis = []
    for it in daten.get("message", {}).get("items", []):
        titel = (it.get("title") or [""])[0]
        if not titel:
            continue
        teile = (it.get("published-online") or it.get("published") or {}).get("date-parts", [[None]])[0]
        datum = None
        if teile and teile[0]:
            datum = dt.datetime(teile[0], (teile[1] if len(teile) > 1 else 1),
                                (teile[2] if len(teile) > 2 else 1), tzinfo=dt.timezone.utc)
        namen = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in it.get("author", [])]
        autoren = ", ".join(namen[:4]) + (" et al." if len(namen) > 4 else "")
        text = re.sub(r"^\s*(Abstract|Purpose)\s*", "", html_zu_text(it.get("abstract", "")))
        link = it.get("URL") or f"https://doi.org/{it.get('DOI', '')}"
        a = _artikel(quelle, titel, link, datum, text, autoren, typ="forschung")
        journal = (it.get("container-title") or [""])[0]
        if journal:
            a["quelle"] = journal
        ergebnis.append(a)
    return ergebnis


# --------------------------------------------------------------------------- Einordnung

def rubrik_bestimmen(artikel: dict, rubriken: list[dict], standard: str) -> str:
    if artikel["rubrik"] != "auto":
        return artikel["rubrik"]
    heu = " ".join([artikel["titel"], artikel["titel"], artikel["text"][:600], " ".join(artikel["tags"])]).lower()
    beste, punkte = standard, 0
    for r in rubriken:
        p = sum(heu.count(s.lower()) for s in r.get("schlagworte", []))
        if p > punkte:
            beste, punkte = r["id"], p
    return beste


def _normtitel(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", t.lower())[:80]


def suchen(config: dict, quellen_ids: list[str] | None = None, tage: int = 7,
           max_pro_quelle: int = 15, filter_text: str = "", max_zeichen: int = 700) -> dict:
    """Ruft alle gewählten Quellen parallel ab und liefert {'artikel': [...], 'fehler': [...]}."""
    jetzt = dt.datetime.now(dt.timezone.utc)
    seit = jetzt - dt.timedelta(days=tage)
    quellen = [q for q in config["quellen"]
               if (quellen_ids is None and q.get("aktiv", True)) or (quellen_ids and q["id"] in quellen_ids)]

    def lade(q):
        if q["typ"] == "rss":
            return lade_feed(q, max_pro_quelle * 3)
        if q["typ"] == "arxiv":
            return lade_arxiv(q, max_pro_quelle * 2)
        if q["typ"] == "crossref":
            return lade_crossref(q, max_pro_quelle, seit)
        raise ValueError(f"Unbekannter Quellentyp: {q['typ']}")

    artikel, fehler = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(lade, q): q for q in quellen}
        for fut in concurrent.futures.as_completed(futures):
            q = futures[fut]
            try:
                liste = fut.result()
            except Exception as e:  # Netzfehler, kaputter Feed …
                fehler.append({"quelle": q["name"], "meldung": f"{type(e).__name__}: {e}"})
                continue
            treffer = 0
            for a in liste:
                d = datum_parsen(a["datum"]) if a["datum"] else None
                if d and d < seit:
                    continue
                if treffer >= max_pro_quelle:
                    break
                artikel.append(a)
                treffer += 1

    # Filter, Dubletten, Rubriken, Kürzen
    begriffe = [b.strip().lower() for b in re.split(r"[,;]", filter_text or "") if b.strip()]
    gesehen, ergebnis = set(), []
    for a in sorted(artikel, key=lambda x: x["datum"] or "", reverse=True):
        schluessel = _normtitel(a["titel"])
        if not schluessel or schluessel in gesehen:
            continue
        if begriffe and not any(b in (a["titel"] + " " + a["text"]).lower() for b in begriffe):
            continue
        gesehen.add(schluessel)
        a["rubrik"] = rubrik_bestimmen(a, config["rubriken"], config.get("standard_rubrik", "trends"))
        a["text"] = kuerzen(a["text"], max_zeichen)
        ergebnis.append(a)

    return {"artikel": ergebnis, "fehler": fehler, "zeitpunkt": jetzt.isoformat(), "seit": seit.isoformat()}
