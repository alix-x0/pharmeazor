"""Run the ANPP harvest (rank 1) for all 40 molecules and write into the
per-drug folders.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drugs import ANPP, DRUGS
from s_anpp import _match_dci, _norm_dci, download_and_parse, save_docs
from store import source_doc_path, write_json, write_text, sections_to_markdown

INV = r"C:\data\data\raw\anpp_inventory.json"
OUT = r"C:\data\data\processed\anpp"

COMBINATION_PARTNERS = [
    "CAFEINE", "CHLORPHENAMINE", "PHENYLEPHRINE", "PSEUDOEPHEDRINE",
    "DIPHENHYDRAMINE", "PARACETAMOL", "CODEINE", "IBUPROFENE", "TRAMADOL",
    "AMLODIPINE", "VALSARTAN", "IRBESARTAN", "HYDROCHLOROTHIAZIDE",
    "SULFAMETHOXAZOLE", "TRIMETHOPRIME", "CLAVULANIQUE",
]


def extra_stems(name):
    """ANPP contains a few typo'd DCIs - map them as alternatives."""
    return {
        "ciprofloxacine": [["CIPROFLOXACINE", "CIOROFLOXACINE"]],
    }.get(name, [])


def main():
    os.makedirs(OUT, exist_ok=True)
    inv = json.load(open(INV, encoding="utf-8"))
    print(f"inventory: {len(inv)} ANPP documents")

    summary = []
    total = 0
    for (drug_id, klass, name, dci, atc) in DRUGS:
        cfg = ANPP.get(name)
        if not cfg:
            continue
        stems = [list(cfg["stems"])] + extra_stems(name)
        selected = []
        for card in inv:
            kind = _match_dci(card["dci"], stems, [])
            if kind is None:
                continue
            nd = _norm_dci(card["dci"])
            if kind == "exact":
                own = {_norm_dci(a) for g in stems for a in
                       ([g] if isinstance(g, str) else list(g))}
                for partner in COMBINATION_PARTNERS:
                    if _norm_dci(partner) in nd and _norm_dci(partner) not in own:
                        kind = "combination"
                        break
            card = dict(card)
            card["match_type"] = kind
            selected.append(card)

        t0 = time.time()
        docs = download_and_parse(selected, drug_id)
        save_docs(docs, os.path.join(OUT, f"drug_{drug_id:02d}.jsonl"))
        for i, doc in enumerate(docs, 1):
            base = f"{i:03d}_{doc.get('brand') or 'rcp'}"
            doc["source_rank"] = 1
            write_json(source_doc_path(drug_id, name, "anpp", base), doc)
            write_text(source_doc_path(drug_id, name, "anpp", base, "md"),
                       sections_to_markdown(doc))
        n_ex = sum(1 for d in docs if d["match_type"] == "exact")
        total += len(docs)
        summary.append({"drug_id": drug_id, "name": name, "cards": len(selected),
                        "docs": len(docs), "exact": n_ex,
                        "brands": sorted({d["brand"] for d in docs})[:12]})
        flag = "" if selected else "   <-- absent from the ANPP database"
        print(f"[{drug_id:2d}] {name:48s} cards={len(selected):3d} docs={len(docs):3d} "
              f"exact={n_ex:3d} ({time.time()-t0:.1f}s){flag}")

    with open(os.path.join(OUT, "_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print("TOTAL ANPP DOCS:", total)


if __name__ == "__main__":
    main()
