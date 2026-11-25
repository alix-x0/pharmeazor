import sys
import traceback

sys.path.insert(0, r"C:\data\scrapers")
from s_dailymed import fetch_spl, parse_spl, search_spls

items = search_spls("acetaminophen", pagesize=3)
print("items", len(items))
for it in items[:2]:
    try:
        xml = fetch_spl(it["setid"])
        print("xml", len(xml) if xml else None)
        d = parse_spl(xml, 1, it)
        print("  brand:", d["brand"], "| mfr:", d["manufacturer"],
              "| sections:", len(d["sections"]), "| ing:", len(d["ingredients"]))
        print("  keys:", [s["key"] for s in d["sections"]])
        print("  ing:", d["ingredients"][:4])
        for s in d["sections"]:
            if s["key"] in ("indications", "interactions", "posologie"):
                print(f"  --- {s['key']}: {s['text'][:200]!r}")
    except Exception:
        traceback.print_exc()
