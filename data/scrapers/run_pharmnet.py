"""Run the Pharm'Net harvest for all 40 molecules."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drugs import DRUGS, PHARMNET
from s_pharmnet import (build_documents, fetch_dci_codes, fetch_laboratories,
                         fetch_notifications, fetch_produits_for_codes)
from store import (append_jsonl, drug_dir, safe_name, sections_to_markdown,
                    source_doc_path, write_json, write_text)

OUT = r"C:\data\data\processed\pharmnet"


def main():
    os.makedirs(OUT, exist_ok=True)
    labs = fetch_laboratories()
    print("laboratories:", len(labs))
    notifs = fetch_notifications()
    print("notifications:", len(notifs))

    summary = []
    for (drug_id, klass, name, dci, atc) in DRUGS:
        t0 = time.time()
        groups = PHARMNET.get(name, [[name]])
        dci_rows = fetch_dci_codes(groups)
        codes = [r["code"] for r in dci_rows]
        produits = fetch_produits_for_codes(codes)
        docs = build_documents(drug_id, groups, dci_rows, produits, labs, notifs)
        d = drug_dir(drug_id, name)
        with open(os.path.join(OUT, f"drug_{drug_id:02d}.jsonl"), "w", encoding="utf-8") as fh:
            for doc in docs:
                fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
        # write per-drug source files
        rows = []
        for i, doc in enumerate(docs, 1):
            base = f"{i:03d}_{safe_name(doc.get('brand') or doc.get('title'))}"
            doc["source_rank"] = 2
            write_json(source_doc_path(drug_id, name, "pharmnet", base), doc)
            write_text(source_doc_path(drug_id, name, "pharmnet", base, "md"),
                       sections_to_markdown(doc))
            for s in doc["sections"]:
                rows.append({
                    "drug_id": drug_id, "drug": name, "atc": atc,
                    "class": klass, "source": "pharmnet", "source_priority": 2,
                    "doc_type": doc["doc_type"], "brand": doc.get("brand"),
                    "dci": doc.get("dci"), "url": doc.get("url"),
                    "section_key": s["key"], "section_label": s["label"],
                    "title": s.get("title"), "text": s.get("text", ""),
                })
        append_jsonl(os.path.join(OUT, "_sections.jsonl"), rows)
        summary.append({"drug_id": drug_id, "name": name, "dci_codes": len(codes),
                        "produits": len(produits), "docs": len(docs)})
        print(f"[{drug_id:2d}] {name:48s} dci_codes={len(codes):3d} "
              f"produits={len(produits):4d} docs={len(docs):4d} ({time.time()-t0:.1f}s)")
    write_json(os.path.join(OUT, "_summary.json"), summary)


if __name__ == "__main__":
    main()
