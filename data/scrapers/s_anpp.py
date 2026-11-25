"""Source 1 (priority) - ANPP RCP database (rcp.anpp.dz), Algeria.

The site is a Filament/Livewire app: searching is a POST to /livewire/update.
The backend does a *case-sensitive, accent-sensitive, substring* match over
(nom de marque + DCI + etablissement pharmaceutique) and the searchable
column is stored **unaccented**, so every query must be ASCII-uppercase.

For each molecule we run a set of queries (DCI, DCI stems, brand names),
collect every matching RCP PDF, download it and split it into canonical
sections.
"""
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bs4 import BeautifulSoup
from drugs import ALL_STEMS
from http_util import get
from pypdf import PdfReader
from rcp_parse import parse_rcp_text, section_index
from textutil import fold, strip_accents

BASE = "https://rcp.anpp.dz"
RAW = r"C:\data\data\raw\anpp"
OUT = r"C:\data\data\processed\anpp"


def _ascii_upper(s):
    return re.sub(r"[^A-Z0-9 ]", " ", strip_accents(s).upper()).strip()


class AnppClient:
    def __init__(self):
        self._snap = None
        self._token = None

    def _load_page(self):
        r = get(BASE + "/", timeout=60)
        html = r.text
        m = re.search(r'name="csrf-token" content="([^"]+)"', html)
        self._token = m.group(1) if m else None
        m = re.search(r'wire:snapshot="(\{&quot;data.*?)" wire:effects', html, re.S)
        if not m:
            raise RuntimeError("Livewire snapshot not found")
        snap = (m.group(1).replace("&quot;", '"').replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&#039;", "'"))
        self._snap = json.loads(snap)

    def search(self, query, tries=4):
        """Return the rendered results html for a query."""
        if self._snap is None:
            self._load_page()
        payload = {
            "_token": self._token,
            "components": [{
                "snapshot": json.dumps(self._snap),
                "updates": {"query": query},
                "calls": [{"path": "", "method": "search", "params": []}],
            }],
        }
        last = None
        for attempt in range(tries):
            try:
                from http_util import post
                r = post(BASE + "/livewire/update", json=payload,
                         headers={"X-Livewire": "true", "Referer": BASE + "/",
                                  "Accept": "application/json"}, timeout=60)
                comp = r.json()["components"][0]
                self._snap = json.loads(comp["snapshot"])
                return comp["effects"].get("html", "")
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2)
                self._load_page()
        raise last


def parse_results(html_text):
    """Extract the result cards (brand, DCI, lab, pdf url)."""
    soup = BeautifulSoup(html_text, "lxml")
    grid = None
    for div in soup.find_all("div"):
        cls = div.get("class") or []
        if any("grid-cols-1" in c for c in cls) and any("md:grid-cols-3" in c for c in cls):
            grid = div
            break
    out, seen = [], set()
    if grid is None:
        return out
    for card in grid.find_all("div"):
        link = card.find("a", href=True)
        if not link:
            continue
        href = link["href"]
        if not href or ".pdf" not in href.lower():
            continue
        # card text is "Infos sur le RCP Etablissement ... Nom de Marque X DCI Y Voir le RCP"
        txt = card.get_text(" ", strip=True)
        brand = dci = lab = ""
        m = re.search(r"Etablissement Pharmaceutique\s+(.*?)\s+Nom de Marque\s+(.*?)\s+DCI\s+(.*?)\s+Voir le RCP", txt)
        if m:
            lab, brand, dci = m.group(1), m.group(2), m.group(3)
        else:
            brand = txt
        key = href
        if key in seen:
            continue
        seen.add(key)
        out.append({"url": href, "brand": brand.strip(), "dci": dci.strip(),
                    "lab": lab.strip(), "raw": txt})
    return out


def pdf_to_text(path):
    try:
        reader = PdfReader(path)
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:  # noqa: BLE001
                pages.append("")
        return "\n".join(pages)
    except Exception as e:  # noqa: BLE001
        return ""


def _norm_dci(s):
    d = fold(s or "")
    d = re.sub(r"[^a-z0-9 ]+", " ", d)
    return re.sub(r"\s+", " ", d).strip()


def _match_dci(card_dci, target_stems, universe_stems=None):
    """Classify a card DCI against the target molecule.

    `target_stems` is a list of *groups*; each group is either a string or a
    list of alternative spellings. A group matches when any of its
    alternatives appears in the card DCI.

    Returns "exact" (the molecule itself), "combination" (the molecule sold
    together with other actives) or None (unrelated product).
    """
    d = _norm_dci(card_dci)
    if not d:
        return None
    groups = []
    for g in target_stems:
        alts = g if isinstance(g, (list, tuple)) else [g]
        alts = [_norm_dci(a) for a in alts]
        alts = [a for a in alts if a]
        if alts:
            groups.append(alts)
    if not groups:
        return None
    for alts in groups:
        if not any(a in d for a in alts):
            return None
    if universe_stems:
        # does the DCI mention another molecule of the corpus?
        flat = {a for alts in groups for a in alts}
        for other in universe_stems:
            o = _norm_dci(other)
            if not o or o in flat:
                continue
            if o in d:
                return "combination"
    return "exact"


def harvest_drug(client, drug_id, dci, queries, stems, max_pdfs=80):
    """Search ANPP for one molecule; return list of result cards."""
    found = {}
    for q in queries:
        q = _ascii_upper(q)
        if not q:
            continue
        try:
            html = client.search(q)
        except Exception as e:  # noqa: BLE001
            print(f"    ! search failed {q!r}: {type(e).__name__}")
            continue
        for card in parse_results(html):
            kind = _match_dci(card["dci"], stems, ALL_STEMS)
            if kind is None:
                continue
            card["match_type"] = kind
            if card["url"] not in found:
                found[card["url"]] = card
            elif found[card["url"]]["match_type"] != "exact" and kind == "exact":
                found[card["url"]]["match_type"] = "exact"
        time.sleep(0.25)
    return list(found.values())[:max_pdfs]


def download_and_parse(cards, drug_id, outdir=OUT, rawdir=RAW):
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(rawdir, exist_ok=True)
    docs = []
    for card in cards:
        name = card["url"].rsplit("/", 1)[-1]
        pdf_path = os.path.join(rawdir, name)
        try:
            if not os.path.exists(pdf_path):
                r = get(card["url"], timeout=120)
                if r.status_code != 200 or len(r.content) < 2000:
                    continue
                with open(pdf_path, "wb") as fh:
                    fh.write(r.content)
        except Exception as e:  # noqa: BLE001
            print(f"    ! download failed {name}: {type(e).__name__}")
            continue
        text = pdf_to_text(pdf_path)
        if not text or len(text) < 400:
            continue
        sections = parse_rcp_text(text)
        idx = section_index(sections)
        doc = {
            "source": "anpp",
            "source_priority": 1,
            "drug_id": drug_id,
            "language": "fr",
            "title": card["brand"],
            "brand": card["brand"],
            "dci": card["dci"],
            "lab": card["lab"],
            "match_type": card.get("match_type"),
            "url": card["url"],
            "doc_type": "rcp",
            "text": text,
            "sections": [{"key": s["key"], "label": s["label"], "number": s["number"],
                          "title": s["title"], "text": s["text"]} for s in sections],
        }
        docs.append(doc)
    return docs


def save_docs(docs, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
