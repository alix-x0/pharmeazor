"""Quality check of the produced corpus: coverage per drug and per section."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_corpus import KEY_SECTIONS
from drugs import DRUGS
from store import OUT_ROOT, SOURCES, drug_dir

CORE = ["indications", "posologie", "contre_indications", "interactions",
        "composition", "ingredients", "effets_indesirables", "mises_en_garde"]


def main():
    total_rows = 0
    missing_core = []
    print(f"{'#':>3} {'drug':46s} {'docs':>6} {'sections':>9}  sources present")
    print("-" * 110)
    for (drug_id, klass, name, dci, atc) in DRUGS:
        folder = drug_dir(drug_id, name)
        rows = []
        sp = os.path.join(folder, "sections.jsonl")
        if os.path.exists(sp):
            with open(sp, encoding="utf-8") as fh:
                rows = [json.loads(l) for l in fh if l.strip()]
        total_rows += len(rows)
        keys = {r["section_key"] for r in rows}
        srcs = Counter(r["source"] for r in rows)
        present = [f"{s}:{srcs.get(s, 0)}" for s, _ in sorted(SOURCES.items())]
        miss = [c for c in CORE if c not in keys]
        if miss:
            missing_core.append((drug_id, name, miss))
        print(f"{drug_id:3d} {name[:46]:46s} {len(rows):6d} {len(keys):9d}  "
              f"{' '.join(present)}")
    print("-" * 110)
    print("TOTAL section rows:", total_rows)
    print("\nDrugs missing a core section:")
    for drug_id, name, miss in missing_core:
        print(f"  [{drug_id:2d}] {name:46s} -> {', '.join(miss)}")
    if not missing_core:
        print("  (none)")


if __name__ == "__main__":
    main()
