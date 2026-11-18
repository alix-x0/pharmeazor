"""Final assembly: one folder per drug with everything.

For every drug the folder contains
    drug.json       aggregated index (documents + canonical sections + coverage)
    sections.jsonl  one row per section -> ready for a RAG / vector index
    RCP.md          readable merged RCP (sources ordered by rank)
    1_anpp/ 2_pharmnet/ 3_dailymed/ 4_bdpm/   one .json + .md per document
"""
import glob
import json
import os
import sys
from collections import OrderedDict, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drugs import DRUGS
from store import OUT_ROOT, SOURCES, drug_dir, write_json, write_text

# the canonical sections the user asked for, in reading order
KEY_SECTIONS = [
    ("ingredients", "Ingredients / Composition"),
    ("composition", "Composition"),
    ("denomination", "Denomination"),
    ("nom_commercial", "Commercial name"),
    ("dci", "DCI"),
    ("forme_pharmaceutique", "Pharmaceutical form"),
    ("formes_et_dosages", "Dosage forms and strengths"),
    ("indications", "Indications"),
    ("posologie", "Posology / Dosage"),
    ("contre_indications", "Contraindications"),
    ("mises_en_garde", "Warnings and precautions"),
    ("interactions", "Interactions"),
    ("fertilite_grossesse", "Fertility, pregnancy and breastfeeding"),
    ("populations_specifiques", "Use in specific populations"),
    ("aptitude_conduite", "Driving ability"),
    ("effets_indesirables", "Adverse effects"),
    ("surdosage", "Overdose"),
    ("pharmacodynamique", "Pharmacodynamics"),
    ("pharmacocinetique", "Pharmacokinetics"),
    ("mecanisme_action", "Mechanism of action"),
    ("pharmacologie", "Clinical pharmacology"),
    ("securite_preclinique", "Preclinical safety"),
    ("toxicologie", "Nonclinical toxicology"),
    ("description", "Description"),
    ("excipients", "Excipients"),
    ("incompatibilites", "Incompatibilities"),
    ("duree_conservation", "Shelf life"),
    ("precautions_conservation", "Storage precautions"),
    ("conditionnement", "Packaging"),
    ("elimination", "Disposal"),
    ("titulaire", "Marketing authorisation holder"),
    ("numero_autorisation", "Authorisation number"),
    ("date_premiere_autorisation", "First authorisation date"),
    ("date_mise_a_jour", "Revision date"),
    ("dosimetrie", "Dosimetry"),
    ("radiopharma", "Radiopharmaceutical instructions"),
    ("information_patient", "Patient information"),
    ("info_importante", "Important information"),
    ("rcp_link", "RCP document link"),
    ("notice_link", "Notice document link"),
    ("observation", "Observations"),
    ("fiche_produit", "Product record"),
]
KEY_LABELS = dict(KEY_SECTIONS)


def load_docs(folder):
    docs = []
    for path in glob.glob(os.path.join(folder, "*", "*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                docs.append(json.load(fh))
        except Exception:  # noqa: BLE001
            continue
    return docs


def build_drug(drug_id, klass, name, dci, atc):
    folder = drug_dir(drug_id, name)
    docs = load_docs(folder)
    docs.sort(key=lambda d: (d.get("source_rank", 99), d.get("brand") or d.get("title") or ""))

    by_source = defaultdict(list)
    for d in docs:
        by_source[d.get("source", "unknown")].append(d)

    # ---- sections, grouped per canonical key
    sections = defaultdict(list)
    rows = []
    for d in docs:
        rank = d.get("source_rank", 99)
        src = d.get("source")
        for s in d.get("sections", []):
            key = s.get("key")
            text = (s.get("text") or "").strip()
            if not text:
                continue
            sections[key].append({
                "source": src, "source_rank": rank,
                "document": d.get("title") or d.get("brand"),
                "brand": d.get("brand"), "dci": d.get("dci"),
                "lab": d.get("lab") or d.get("manufacturer"),
                "url": d.get("url"), "label": s.get("label"),
                "number": s.get("number"), "text": text,
            })
            rows.append({
                "drug_id": drug_id, "drug": name, "dci": dci, "atc": atc,
                "class": klass,
                "source": src, "source_rank": rank,
                "source_name": SOURCES.get(rank, (None, src))[1] if rank in SOURCES else src,
                "doc_type": d.get("doc_type"),
                "document": d.get("title") or d.get("brand"),
                "brand": d.get("brand"), "dci_doc": d.get("dci"),
                "manufacturer": d.get("lab") or d.get("manufacturer"),
                "section_key": key, "section_label": s.get("label") or KEY_LABELS.get(key, key),
                "section_number": s.get("number"),
                "url": d.get("url"), "text": text,
            })

    # ---- coverage per source
    coverage = {}
    for rank, (sid, disp, url, role) in sorted(SOURCES.items()):
        docs_s = by_source.get(sid, [])
        coverage[sid] = {
            "rank": rank, "name": disp, "url": url, "role": role,
            "documents": len(docs_s),
            "brands": sorted({(x.get("brand") or x.get("title") or "") for x in docs_s})[:40],
            "sections": sorted({s["key"] for d in docs_s for s in d.get("sections", [])
                                if (s.get("text") or "").strip()}),
        }

    # ---- ingredients collected from every source
    ingredients = []
    for d in docs:
        for ing in d.get("ingredients", []) or []:
            if ing and ing not in ingredients:
                ingredients.append(ing)

    meta = {
        "drug_id": drug_id, "name": name, "dci": dci, "atc": atc,
        "therapeutic_class": klass,
        "documents": len(docs),
        "documents_by_source": {k: len(v) for k, v in by_source.items()},
        "coverage": coverage,
        "ingredients": ingredients,
        "section_keys": sorted(sections.keys()),
        "sections": {k: len(v) for k, v in sections.items()},
        "has": {key: bool(sections.get(key)) for key, _ in KEY_SECTIONS},
    }
    write_json(os.path.join(folder, "drug.json"),
               {"meta": meta, "documents": docs, "section_index":
                {k: [r for r in rows if r["section_key"] == k] for k in sections}})

    with open(os.path.join(folder, "sections.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- merged readable RCP
    md = build_markdown(meta, docs, sections)
    write_text(os.path.join(folder, "RCP.md"), md)
    return meta, len(rows)


def build_markdown(meta, docs, sections):
    out = []
    out.append(f"# {meta['name']} ({meta['dci']})")
    out.append("")
    out.append(f"- **Classe** : {meta['therapeutic_class']}")
    out.append(f"- **Code ATC** : {meta['atc']}")
    out.append(f"- **Documents collectes** : {meta['documents']}")
    out.append("")
    out.append("## Sources (par rang de priorité)")
    out.append("")
    for sid, cov in meta["coverage"].items():
        mark = "x" if cov["documents"] else " "
        out.append(f"- [{mark}] **Rang {cov['rank']} - {cov['name']}** "
                   f"({cov['documents']} document(s)) - {cov['url']}")
    out.append("")
    out.append("## Documents")
    out.append("")
    for d in docs:
        out.append(f"- [Rang {d.get('source_rank')}] {d.get('source')} / "
                   f"{d.get('doc_type')} : **{d.get('title') or d.get('brand')}** "
                   f"({d.get('brand') or ''}) {d.get('url') or ''}")
    out.append("")
    out.append("## Informations structurées")
    out.append("")
    for key, label in KEY_SECTIONS:
        items = sections.get(key)
        if not items:
            continue
        out.append(f"### {label}")
        out.append("")
        for it in items:
            src = it["source"]
            rank = it["source_rank"]
            out.append(f"#### [{rank} - {src}] {it['document']}")
            out.append("")
            out.append(it["text"])
            out.append("")
    return "\n".join(out)


def main():
    rows = []
    for (drug_id, klass, name, dci, atc) in DRUGS:
        meta, n = build_drug(drug_id, klass, name, dci, atc)
        rows.append(meta)
        print(f"[{drug_id:2d}] {name:46s} docs={meta['documents']:5d} "
              f"sections={n:5d}  "
              f"anpp={meta['documents_by_source'].get('anpp', 0):3d} "
              f"pharmnet={meta['documents_by_source'].get('pharmnet', 0):4d} "
              f"dailymed={meta['documents_by_source'].get('dailymed', 0):3d} "
              f"bdpm={meta['documents_by_source'].get('bdpm', 0):4d}")
    write_json(os.path.join(OUT_ROOT, "_index.json"), rows)
    print("\nTOTAL drugs:", len(rows))


if __name__ == "__main__":
    main()
