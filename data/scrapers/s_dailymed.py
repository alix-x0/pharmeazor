"""Source 3 - DailyMed (US Structured Product Labels).

API:  https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?drug_name=X
       https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml   (HL7 v3 SPL)

The XML is parsed into the same canonical section keys used for the French RCPs
so that the RAG index is uniform across sources.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bs4 import BeautifulSoup
from http_util import get

API = "https://dailymed.nlm.nih.gov/dailymed/services/v2"

# SPL section code -> canonical key
SECTION_CODES = {
    "34067-9": ("indications", "Indications and Usage"),
    "34068-7": ("posologie", "Dosage and Administration"),
    "34070-3": ("contre_indications", "Contraindications"),
    "34073-7": ("interactions", "Drug Interactions"),
    "34084-4": ("effets_indesirables", "Adverse Reactions"),
    "34088-5": ("surdosage", "Overdosage"),
    "34089-3": ("description", "Description"),
    "34090-1": ("pharmacologie", "Clinical Pharmacology"),
    "42228-7": ("fertilite_grossesse", "Pregnancy"),
    "43678-2": ("formes_et_dosages", "Dosage Forms and Strengths"),
    "43679-0": ("mecanisme_action", "Mechanism of Action"),
    "43680-8": ("toxicologie", "Nonclinical Toxicology"),
    "43682-4": ("pharmacocinetique", "Pharmacokinetics"),
    "43684-0": ("populations_specifiques", "Use in Specific Populations"),
    "43685-7": ("mises_en_garde", "Warnings and Precautions"),
    "43683-2": ("changements_majeurs", "Recent Major Changes"),
    "34076-0": ("information_patient", "Information for Patients"),
    "43692-3": ("grossesse", "Pregnancy"),
    "42229-5": ("non_classifie", "Unclassified"),
}

TITLE_TO_KEY = {
    "INDICATIONS & USAGE": "indications",
    "DOSAGE & ADMINISTRATION": "posologie",
    "CONTRAINDICATIONS": "contre_indications",
    "DRUG INTERACTIONS": "interactions",
    "ADVERSE REACTIONS": "effets_indesirables",
    "OVERDOSAGE": "surdosage",
    "DESCRIPTION": "description",
    "CLINICAL PHARMACOLOGY": "pharmacologie",
    "PREGNANCY": "fertilite_grossesse",
    "DOSAGE FORMS & STRENGTHS": "formes_et_dosages",
    "MECHANISM OF ACTION": "mecanisme_action",
    "NONCLINICAL TOXICOLOGY": "toxicologie",
    "PHARMACOKINETICS": "pharmacocinetique",
    "USE IN SPECIFIC POPULATIONS": "populations_specifiques",
    "WARNINGS AND PRECAUTIONS": "mises_en_garde",
    "HOW SUPPLIED": "conditionnement",
}


def _txt(el):
    """Readable text of an HL7 element (keeps list/table structure)."""
    if el is None:
        return ""
    from lxml import etree
    html = etree.tostring(el, encoding="unicode")
    soup = BeautifulSoup(html, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for td in soup.find_all(["td", "th"]):
        td.append(" | ")
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
    txt = soup.get_text()
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n\n", txt)
    return txt.strip()


def search_spls(drug_name, pagesize=20, tries=4):
    url = f"{API}/spls.json?drug_name={drug_name}&pagesize={pagesize}"
    last = None
    for _ in range(tries):
        try:
            r = get(url, timeout=120)
            return r.json().get("data", [])
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2)
    raise last


def fetch_spl(setid, tries=4):
    """Download (and cache) the SPL XML of a set id."""
    cache_dir = r"C:\data\data\raw\dailymed"
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, f"{setid}.xml")
    if os.path.exists(cache) and os.path.getsize(cache) > 2000:
        with open(cache, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    url = f"{API}/spls/{setid}.xml"
    last = None
    for _ in range(tries):
        try:
            r = get(url, timeout=240)
            if r.status_code == 200 and len(r.content) > 2000:
                with open(cache, "wb") as fh:
                    fh.write(r.content)
                return r.text
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(2)
    if last:
        raise last
    return None


def parse_spl(xml_text, drug_id, meta):
    """Parse an SPL XML document into a structured document."""
    from lxml import etree
    root = etree.fromstring(xml_text.encode("utf-8"), parser=etree.XMLParser(recover=True))

    def find_all(tag):
        # the SPL uses a default namespace (urn:hl7-org:v3) -> match on local-name
        return root.xpath("//*[local-name()='%s']" % tag)

    def find_first(tag):
        found = find_all(tag)
        return found[0] if found else None

    def text_of(el):
        return (el.text or "").strip() if el is not None else ""

    title = text_of(find_first("title"))
    setid_el = find_first("setId")
    setid = setid_el.get("root") if setid_el is not None else meta.get("setid")
    eff = find_first("effectiveTime")
    effective = eff.get("value") if eff is not None else ""
    manufacturer = ""
    author = find_first("author")
    if author is not None:
        names = author.xpath(".//*[local-name()='name']")
        if names:
            manufacturer = (names[0].text or "").strip()
    ver = find_first("versionNumber")
    version = ver.get("value") if ver is not None else ""

    sections = []
    ingredients = []

    def section_text(sec):
        """Text belonging to *this* section (not to a nested subsection)."""
        chunks = []

        def walk(el):
            for ch in el:
                if not isinstance(ch.tag, str):
                    continue
                tag = etree.QName(ch).localname
                if tag == "section":
                    continue          # nested subsection -> handled on its own
                if tag == "text":
                    chunks.append(_txt(ch))
                    continue
                walk(ch)

        walk(sec)
        return "\n\n".join(c for c in chunks if c.strip()).strip()

    for comp in find_all("component"):
        secs = comp.xpath("./*[local-name()='section']")
        if not secs:
            continue
        sec = secs[0]
        code_els = sec.xpath("./*[local-name()='code']")
        code = code_els[0].get("code") if code_els else ""
        disp = (code_els[0].get("displayName") if code_els else "") or ""
        title_els = sec.xpath("./*[local-name()='title']")
        sec_title = text_of(title_els[0]) if title_els else disp
        text = section_text(sec)
        key = SECTION_CODES.get(code)
        if key is None:
            t = (sec_title or disp).upper()
            key = TITLE_TO_KEY.get(t)
        if key is None:
            key = "section_" + re.sub(r"[^a-z0-9]+", "_", (sec_title or disp).lower()).strip("_")[:40]
        label = SECTION_CODES.get(code, (None, sec_title or disp))[1]
        if code == "48780-1":
            ingredients = _parse_ingredients(sec)
            key, label = "ingredients", "Ingredients"
        if not text.strip():
            continue
        sections.append({"key": key, "label": label, "number": code,
                         "title": sec_title or disp, "text": text})

    doc = {
        "source": "dailymed",
        "source_priority": 3,
        "drug_id": drug_id,
        "language": "en",
        "doc_type": "label",
        "label_type": _root_label_type(root),
        "title": meta.get("title") or title.split("\n")[0],
        "brand": meta.get("title", "").split("[")[0].strip(),
        "dci": "",
        "manufacturer": manufacturer,
        "setid": setid,
        "spl_version": version,
        "published_date": meta.get("published_date"),
        "effective_date": effective,
        "url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}",
        "source_url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}",
        "sections": sections,
        "ingredients": ingredients,
        "text": "\n\n".join(f"{s['label']}\n{s['text']}" for s in sections),
    }
    return doc


def _parse_ingredients(sec):
    """Active + inactive ingredients of the 'SPL product data elements' section."""
    out = []
    for ing in sec.xpath(".//*[local-name()='ingredient']"):
        cls = ing.get("classCode") or ""
        subs = ing.xpath("./*[local-name()='ingredientSubstance']")
        if not subs:
            continue
        sub = subs[0]
        name_els = sub.xpath("./*[local-name()='name']")
        name = (name_els[0].text or "").strip() if name_els else ""
        if not name:
            continue
        nums = ing.xpath(".//*[local-name()='numerator']")
        qty = ""
        if nums:
            val = nums[0].get("value")
            unit = nums[0].get("unit") or ""
            if val:
                qty = f"{val} {unit}".strip()
        kind = "Active" if cls == "ACTIM" else ("Inactive" if cls == "IACT" else cls)
        out.append(f"{name} ({kind})" + (f" - {qty}" if qty else ""))
    return out


def _root_label_type(root):
    """'HUMAN PRESCRIPTION DRUG LABEL' / 'HUMAN OTC DRUG LABEL' / ..."""
    for c in root.xpath("//*[local-name()='code']"):
        name = c.get("displayName") or ""
        if "DRUG LABEL" in name.upper():
            return name
    return ""


def _title_score(title, primary, all_names):
    """Prefer the label of the plain molecule over fixed-dose combinations."""
    t = (title or "").lower()
    score = 0.0
    prim = re.sub(r"[^a-z0-9 ]+", " ", primary.lower())
    prim = re.sub(r"\s+", " ", prim).strip()
    if prim and prim in t:
        score += 10.0
    # penalise labels that advertise several other actives
    for n in all_names:
        nn = re.sub(r"[^a-z0-9 ]+", " ", n.lower())
        nn = re.sub(r"\s+", " ", nn).strip()
        if nn and nn != prim and nn in t:
            score -= 2.0
    return score


def harvest(drug_id, names, max_labels=3, max_candidates=14, primary=None):
    """Search + fetch the most relevant labels for a molecule.

    Prescription labels are preferred (they carry contraindications,
    interactions and posology); OTC labels are used as a fallback.
    """
    primary = primary or names[0]
    seen_sets = set()
    candidates = []
    for nm in names:
        try:
            for item in search_spls(nm, pagesize=max_candidates):
                if item["setid"] in seen_sets:
                    continue
                seen_sets.add(item["setid"])
                candidates.append(item)
        except Exception as e:  # noqa: BLE001
            print(f"    ! dailymed search {nm}: {type(e).__name__}")
    # relevance order of DailyMed is kept, but the plain molecule comes first
    candidates.sort(key=lambda x: -_title_score(x.get("title", ""), primary, names))
    candidates = candidates[:max_candidates]

    rx, otc = [], []
    used_mfr = set()
    for item in candidates:
        if len(rx) >= max_labels and len(otc) >= 1:
            break
        try:
            xml = fetch_spl(item["setid"])
        except Exception as e:  # noqa: BLE001
            print(f"    ! dailymed fetch {item['setid']}: {type(e).__name__}")
            continue
        if not xml:
            continue
        try:
            doc = parse_spl(xml, drug_id, item)
        except Exception as e:  # noqa: BLE001
            print(f"    ! dailymed parse: {type(e).__name__}")
            continue
        if not doc["sections"]:
            continue
        mfr = (doc.get("manufacturer") or "").lower()
        if mfr and mfr in used_mfr:
            continue
        used_mfr.add(mfr)
        if "PRESCRIPTION" in (doc.get("label_type") or "").upper():
            rx.append(doc)
        else:
            otc.append(doc)
    docs = rx[:max_labels]
    if len(docs) < max_labels and otc:
        docs += otc[:max_labels - len(docs)]
    return docs
