"""Source 3 - BDPM (Base de Données Publique des Médicaments, France / ANSM).

The public specialty page  /medicament/{CIS}/extrait  embeds:
  * tabpanel-rcp-panel     -> the full RCP (HTML with Amm* CSS classes)
  * tabpanel-notice-panel  -> the patient notice
  * the "fiche info" block  -> indications, composition, presentations

The mapping substance -> CIS codes comes from the official open-data file
CIS_COMPO_bdpm.txt.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bs4 import BeautifulSoup
from http_util import get
from rcp_parse import parse_rcp_html

BASE = "https://base-donnees-publique.medicaments.gouv.fr"
COMPO = r"C:\data\data\raw\CIS_COMPO_bdpm.txt"
SPEC = r"C:\data\data\raw\CIS_bdpm.txt"


def _asc(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(c)).upper()


def load_compo():
    """CIS -> list of active substances (accent free)."""
    out = {}
    with open(COMPO, encoding="latin-1") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 7:
                continue
            cis, substance, kind = parts[0], parts[3], parts[6]
            if kind != "SA":
                continue
            out.setdefault(cis, []).append(_asc(substance))
    return out


def load_specialites():
    """CIS -> specialty record (name, form, lab, status...)."""
    out = {}
    with open(SPEC, encoding="latin-1") as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) < 2:
                continue
            out[p[0]] = {"cis": p[0], "name": p[1], "form": p[2] if len(p) > 2 else "",
                         "route": p[3] if len(p) > 3 else "",
                         "status": p[4] if len(p) > 4 else "",
                         "procedure": p[5] if len(p) > 5 else "",
                         "marketing": p[6] if len(p) > 6 else "",
                         "lab": p[10] if len(p) > 10 else ""}
    return out


def find_cis(substance_groups, compo, limit=40):
    """CIS codes whose active substances match every group."""
    groups = [[_asc(x) for x in g] for g in substance_groups]
    groups = [g for g in groups if g]
    hits = {}
    for cis, substances in compo.items():
        blob = " | ".join(substances)
        ok = True
        for g in groups:
            if not any(a in blob for a in g):
                ok = False
                break
        if ok:
            hits[cis] = substances
    return hits


def fetch_extract(cis, tries=4):
    """Download (and cache) the /extrait page of a specialty."""
    cache_dir = r"C:\data\data\raw\bdpm"
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, f"{cis}.html")
    if os.path.exists(cache) and os.path.getsize(cache) > 5000:
        with open(cache, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    url = f"{BASE}/medicament/{cis}/extrait"
    last = None
    for _ in range(tries):
        try:
            r = get(url, timeout=120)
            if r.status_code == 200 and "tabpanel-rcp-panel" in r.text:
                with open(cache, "w", encoding="utf-8") as fh:
                    fh.write(r.text)
                return r.text
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(2)
    if last:
        raise last
    return None


def parse_extract(html_text, cis, spec, drug_id):
    soup = BeautifulSoup(html_text, "lxml")
    name = spec.get("name") if spec else ""
    title_el = soup.find("h3", attrs={"role": "heading"})
    if title_el:
        name = title_el.get_text(" ", strip=True) or name

    def panel_text(pid):
        el = soup.find(id=pid)
        if el is None:
            return ""
        for bad in el.select("nav.fr-sidemenu, .fr-sidemenu, button"):
            bad.decompose()
        return el.get_text("\n", strip=True)

    rcp_panel = soup.find(id="tabpanel-rcp-panel")
    notice_panel = soup.find(id="tabpanel-notice-panel")
    rcp_sections = parse_rcp_html(rcp_panel) if rcp_panel else []
    notice_sections = parse_rcp_html(notice_panel) if notice_panel else []

    # fiche info: indications + composition as displayed by the ANSM
    fiche_sections = []
    info_block = soup.find(id="tabpanel-fiche-info-panel")
    if info_block:
        txt = info_block.get_text("\n", strip=True)
        m = re.search(r"Indications\s+thérapeutiques\s*\n(.*?)(?:\nGroupe\(s\) générique|\nComposition en|$)",
                      txt, re.S)
        if m:
            fiche_sections.append({"key": "indications", "label": "Indications thérapeutiques",
                                   "number": "4.1", "title": "Indications thérapeutiques",
                                   "text": m.group(1).strip()})
        m = re.search(r"Composition en substances actives\s*\n(.*?)(?:\nPrésentations|\n|$)", txt, re.S)
        if m:
            fiche_sections.append({"key": "composition", "label": "Composition en substances actives",
                                   "number": "2", "title": "Composition",
                                   "text": m.group(1).strip()})
        m = re.search(r"Forme pharmaceutique\s*\n(.*?)(?:\nComposition|\n|$)", txt, re.S)
        if m:
            fiche_sections.append({"key": "forme_pharmaceutique", "label": "Forme pharmaceutique",
                                   "number": "3", "title": "Forme pharmaceutique",
                                   "text": m.group(1).strip()})

    rcp_text = panel_text("tabpanel-rcp-panel")
    notice_text = panel_text("tabpanel-notice-panel")

    doc = {
        "source": "bdpm",
        "source_priority": 3,
        "drug_id": drug_id,
        "language": "fr",
        "doc_type": "rcp",
        "title": name,
        "brand": name,
        "dci": " / ".join(dict.fromkeys(spec.get("dci", "") if spec else [])),
        "lab": spec.get("lab") if spec else "",
        "manufacturer": spec.get("lab") if spec else "",
        "cis": cis,
        "form": spec.get("form") if spec else "",
        "status": spec.get("status") if spec else "",
        "marketing_status": spec.get("marketing") if spec else "",
        "url": f"{BASE}/medicament/{cis}/extrait",
        "source_url": f"{BASE}/medicament/{cis}/extrait",
        "sections": fiche_sections + rcp_sections,
        "rcp_text": rcp_text,
        "notice_text": notice_text,
        "text": rcp_text,
        "ingredients": [],
    }
    for s in doc["sections"]:
        if s["key"] == "composition":
            doc["ingredients"] = [l.strip() for l in s["text"].split("\n") if l.strip()]

    notice = None
    if notice_text.strip():
        notice = {
            "source": "bdpm", "source_priority": 3, "drug_id": drug_id,
            "language": "fr", "doc_type": "notice", "title": f"{name} - Notice",
            "brand": name, "dci": doc["dci"], "lab": doc["lab"],
            "url": f"{BASE}/medicament/{cis}/extrait",
            "sections": notice_sections or [{"key": "notice", "label": "Notice",
                                             "number": None, "title": "Notice",
                                             "text": notice_text}],
            "text": notice_text, "ingredients": [],
        }
    return doc, notice
