import sys

sys.path.insert(0, r"C:\data\scrapers")
from anpp import AnppClient, parse_results

c = AnppClient()
for q in ["PARACÉTAMOL", "ÉTAMOL", "TÉTAMOL", "PROPHARMAL", "PARACETAMOL",
          "NIFÉDIPINE", "NIFEDIPINE", "ATÉNOLOL", "ATENOLOL", "MÉTHYLDOPA", "METHYLDOPA",
          "NÉFOPAM", "NEFOPAM", "RÉNIAL", "EUGEROL", "DICLOFÉNAC", "DICLOFENAC"]:
    h, _ = c.search(q)
    res = parse_results(h)
    dcis = sorted({it["text"].split("DCI")[-1].replace("Voir le RCP", "").strip() for it in res})
    print(f"{q!r:16s} -> {len(res):3d}  {dcis[:6]}")
