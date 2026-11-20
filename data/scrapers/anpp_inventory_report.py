import json
import sys

inv = json.load(open(r"C:\data\data\raw\anpp_inventory.json", encoding="utf-8"))
print("docs", len(inv))
dcis = {}
for c in inv:
    dcis.setdefault(c["dci"], []).append((c["brand"], c["lab"]))
print("unique DCIs", len(dcis))
for d in sorted(dcis):
    print(f"  {d}   [x{len(dcis[d])}]")

print("\n=== BRANDS ===")
brands = sorted({c["brand"] for c in inv})
print(len(brands))
for b in brands:
    print("   ", b)

print("\n=== LABS ===")
labs = sorted({c["lab"] for c in inv})
for l in labs:
    print("   ", l)
