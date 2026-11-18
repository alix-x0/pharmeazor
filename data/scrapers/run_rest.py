"""Run the DailyMed + BDPM harvest for all 40 molecules (priority 3)."""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drugs import ALIASES, DRUGS, PHARMNET
from s_bdpm import fetch_extract, find_cis, load_compo, load_specialites, parse_extract
from s_dailymed import harvest as dm_harvest
from store import (append_jsonl, drug_dir, safe_name, sections_to_markdown,
                    source_doc_path, write_json, write_text)

OUT = r"C:\data\data\processed\rest"
MAX_BDPM = 18          # specialties kept per molecule
MAX_LABELS = 3         # DailyMed labels kept per molecule
WORKERS = 6


def run_bdpm_drug(drug_id, name, groups, compo, specs):
    hits = find_cis(groups, compo)
    # prefer commercially available specialties and generic products
    def rank(cis):
        s = specs.get(cis, {})
        gen = 1 if "GENERIQUE" in (s.get("name") or "").upper() else 0
        act = 1 if "Commercialise" in (s.get("marketing") or "") else 0
        return (act, gen)
    ciss = sorted(hits.keys(), key=rank, reverse=True)[:MAX_BDPM]
    out = []
    for cis in ciss:
        try:
            html = fetch_extract(cis)
        except Exception as e:  # noqa: BLE001
            print(f"    ! bdpm {cis}: {type(e).__name__}")
            continue
        if not html:
            continue
        try:
            doc, notice = parse_extract(html, cis, specs.get(cis), drug_id)
        except Exception as e:  # noqa: BLE001
            print(f"    ! bdpm parse {cis}: {type(e).__name__}")
            continue
        if doc["rcp_text"].strip():
            out.append(doc)
        if notice:
            out.append(notice)
    return hits, out


def main():
    os.makedirs(OUT, exist_ok=True)
    compo = load_compo()
    specs = load_specialites()
    print(f"BDPM: {len(compo)} CIS with active substances, {len(specs)} specialties")

    summary = []
    for (drug_id, klass, name, dci, atc) in DRUGS:
        t0 = time.time()
        groups = PHARMNET.get(name, [[name]])
        d = drug_dir(drug_id, name)
        rows = []

        # ---------------- DailyMed
        aliases = ALIASES.get(name, [name])[:4]
        dm_docs = dm_harvest(drug_id, aliases, max_labels=MAX_LABELS,
                              primary=ALIASES.get(name, [name])[0])
        for i, doc in enumerate(dm_docs, 1):
            base = f"{i:03d}_{safe_name(doc.get('brand') or doc.get('title'))}"
            doc["source_rank"] = 3
            write_json(source_doc_path(drug_id, name, "dailymed", base), doc)
            write_text(source_doc_path(drug_id, name, "dailymed", base, "md"),
                       sections_to_markdown(doc))
            for s in doc["sections"]:
                rows.append({
                    "drug_id": drug_id, "drug": name, "atc": atc, "class": klass,
                    "source": "dailymed", "source_priority": 3,
                    "doc_type": doc["doc_type"], "brand": doc.get("brand"),
                    "dci": doc.get("dci"), "url": doc.get("url"),
                    "section_key": s["key"], "section_label": s["label"],
                    "title": s.get("title"), "text": s.get("text", ""),
                })

        # ---------------- BDPM
        hits, bd_docs = run_bdpm_drug(drug_id, name, groups, compo, specs)
        for i, doc in enumerate(bd_docs, 1):
            base = f"{i:03d}_{safe_name(doc.get('title'))}"
            doc["source_rank"] = 4
            write_json(source_doc_path(drug_id, name, "bdpm", base), doc)
            write_text(source_doc_path(drug_id, name, "bdpm", base, "md"),
                       sections_to_markdown(doc))
            for s in doc["sections"]:
                rows.append({
                    "drug_id": drug_id, "drug": name, "atc": atc, "class": klass,
                    "source": "bdpm", "source_priority": 3,
                    "doc_type": doc["doc_type"], "brand": doc.get("brand"),
                    "dci": doc.get("dci"), "url": doc.get("url"),
                    "section_key": s["key"], "section_label": s["label"],
                    "title": s.get("title"), "text": s.get("text", ""),
                })

        with open(os.path.join(OUT, f"drug_{drug_id:02d}.jsonl"), "w", encoding="utf-8") as fh:
            for doc in dm_docs + bd_docs:
                fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
        append_jsonl(os.path.join(OUT, "_sections.jsonl"), rows)
        summary.append({"drug_id": drug_id, "name": name,
                        "dailymed": len(dm_docs), "bdpm_cis": len(hits),
                        "bdpm_docs": len(bd_docs)})
        print(f"[{drug_id:2d}] {name:44s} dailymed={len(dm_docs)} bdpm_cis={len(hits):4d} "
              f"bdpm_docs={len(bd_docs):3d} ({time.time()-t0:.1f}s)")
    write_json(os.path.join(OUT, "_summary.json"), summary)


if __name__ == "__main__":
    main()
