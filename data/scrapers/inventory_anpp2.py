"""Verify the ANPP inventory is complete (look for records outside the 234)."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s_anpp import AnppClient, parse_results

OUT = r"C:\data\data\raw\anpp_inventory.json"

TOKENS = ["Q", "X", "J", "K", "W", "ZZ", "0", "1", "2", "5", "9", "E ", "S ", "N ", "H ",
          "G", "B", "F", "P", "T", "V", "Y", "PH", "CH", "TH", "SH", "GN", "MN", "AE",
          "OE", "UE", "SS", "TT", "LL", "RR", "OO", "EE", "II", "UU", "AA", "ON ", " AN "]


def main():
    inv = {}
    if os.path.exists(OUT):
        for c in json.load(open(OUT, encoding="utf-8")):
            inv[c["url"]] = c
    print("start unique:", len(inv))
    client = AnppClient()
    for tok in TOKENS:
        try:
            html = client.search(tok)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {tok}: {type(e).__name__}")
            continue
        cards = parse_results(html)
        new = 0
        for c in cards:
            if c["url"] not in inv:
                inv[c["url"]] = c
                new += 1
        print(f"{tok!r:8s} -> {len(cards):4d}  new={new}  total={len(inv)}")
        time.sleep(0.2)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(list(inv.values()), fh, ensure_ascii=False, indent=1)
    print("FINAL UNIQUE:", len(inv))


if __name__ == "__main__":
    main()
