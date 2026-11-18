"""Inventory the ANPP RCP database by scanning with short contains-queries."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s_anpp import AnppClient, parse_results

OUT = r"C:\data\data\raw\anpp_inventory.json"

TOKENS = ["A", "E", "I", "O", "U", "AN", "EN", "IN", "ON", "ER", "TE", "AL", "RE", "AR",
          "ES", "OL", "OR", "AM", "IM", "INE", "INE ", "INE/", "TINE", "CILL", "CINE",
          "PRIL", "OLOL", "OXACIN", "AZOL", "AZIN", "MYCIN", "THROMY", "CYCLINE",
          "SPAN", "TIN", "TAN", "XICAM", "OXINE", "PIR", "ZOLE", "DINE", "CIN", "PHINE",
          "MINE", "SULFA", "OXAZOLE", "SIL", "ZOL", "PEN", "COX", "DOPA", "METHYL",
          "GLYC", "IDE", "IBE", "PRAZOLE", "ZIN", "MOX", "TIZ", "ZAN", "VAST", "RIL"]


def main():
    client = AnppClient()
    inv = {}
    for tok in TOKENS:
        try:
            html = client.search(tok)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {tok}: {type(e).__name__}")
            continue
        cards = parse_results(html)
        for c in cards:
            inv[c["url"]] = c
        print(f"{tok!r:12s} -> {len(cards):4d} (unique total {len(inv)})")
        time.sleep(0.2)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(list(inv.values()), fh, ensure_ascii=False, indent=1)
    print("UNIQUE RCPs:", len(inv))
    dcis = sorted({c["dci"] for c in inv.values()})
    print("UNIQUE DCIs:", len(dcis))


if __name__ == "__main__":
    main()
