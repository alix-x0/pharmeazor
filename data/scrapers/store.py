"""Output layout: one folder per drug.

C:\\data\\output\\<NN>_<slug>\\
    drug.json          aggregated index for the drug (all sources, all sections)
    sections.jsonl     one record per RCP/notice section (RAG chunks)
    RCP.md             merged, readable RCP of the drug (all sources, ranked)
    1_anpp/            rank 1 - ANPP RCP (rcp.anpp.dz, Algeria)
    2_pharmnet/        rank 2 - Pharm'Net DZ product register
    3_dailymed/        rank 3 - DailyMed US labels
    3_bdpm/            rank 3 - BDPM / ANSM French RCP + notices
"""
import json
import os
import re
import unicodedata

OUT_ROOT = r"C:\data\output"
RAW_ROOT = r"C:\data\data\raw"

# rank -> (source id, display name, base url, role)
SOURCES = {
    1: ("anpp", "ANPP - RCP (Agence Nationale des Matieres Pharmaceutiques, Algerie)",
        "https://rcp.anpp.dz/", "RCP officiel algerien (PDF)"),
    2: ("pharmnet", "Pharm'Net DZ - referentiel des medicaments (Algerie)",
        "https://www.pharmnet-dz.com/", "fiche produit, DCI, laboratoire, RCP/notice"),
    3: ("dailymed", "DailyMed - US Structured Product Labels (FDA/NLM)",
        "https://dailymed.nlm.nih.gov/", "label US (indications, posologie, interactions...)"),
    4: ("bdpm", "BDPM - Base de Donnees Publique des Medicaments (ANSM, France)",
        "https://base-donnees-publique.medicaments.gouv.fr/", "RCP francais + notice"),
}
SOURCE_BY_ID = {v[0]: (k,) + v[1:] for k, v in SOURCES.items()}


def source_rank(source_id):
    for rank, (sid, *_rest) in SOURCES.items():
        if sid == source_id:
            return rank
    return 99


def source_folder(source_id):
    rank = source_rank(source_id)
    return f"{rank}_{source_id}"


def slugify(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def drug_dir(drug_id, name):
    d = os.path.join(OUT_ROOT, f"{drug_id:02d}_{slugify(name)}")
    os.makedirs(d, exist_ok=True)
    return d


def doc_dir(drug_id, name, source_id):
    d = os.path.join(drug_dir(drug_id, name), source_folder(source_id))
    os.makedirs(d, exist_ok=True)
    return d


def source_doc_path(drug_id, name, source_id, base, ext="json"):
    return os.path.join(doc_dir(drug_id, name, source_id), f"{base}.{ext}")


def safe_name(s, maxlen=60):
    s = slugify(s)
    return (s[:maxlen] or "doc")


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def append_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def raw_dir(source):
    d = os.path.join(RAW_ROOT, source)
    os.makedirs(d, exist_ok=True)
    return d


# ------------------------------------------------------------------ markdown
def sections_to_markdown(doc):
    """Render one document (RCP or notice) as readable markdown."""
    lines = []
    title = doc.get("title") or doc.get("brand") or doc.get("dci") or "Document"
    lines.append(f"# {title}")
    meta = []
    for k in ("source", "source_priority", "doc_type", "brand", "dci", "lab",
              "manufacturer", "atc", "language", "published_date", "match_type",
              "reg_number", "dosage", "form"):
        v = doc.get(k)
        if v:
            meta.append(f"- **{k}** : {v}")
    if doc.get("url"):
        meta.append(f"- **url** : {doc['url']}")
    if meta:
        lines.append("\n".join(meta))
        lines.append("")
    if doc.get("ingredients"):
        lines.append("## Composition / Ingrédients")
        lines.append("")
        for ing in doc["ingredients"]:
            lines.append(f"- {ing}")
        lines.append("")
    for s in doc.get("sections", []):
        label = s.get("label") or s.get("title") or s.get("key")
        head = f"## {label}"
        if s.get("number"):
            head += f" ({s['number']})"
        lines.append(head)
        lines.append("")
        body = (s.get("text") or "").strip()
        if body:
            lines.append(body)
        else:
            lines.append("*(section vide)*")
        lines.append("")
    return "\n".join(lines)
