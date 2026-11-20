import sys
import time

sys.path.insert(0, r"C:\data\scrapers")
from anpp import AnppClient, parse_results

c = AnppClient()


def show(q, n=40):
    h, _ = c.search(q)
    res = parse_results(h)
    print(f"\n### {q!r} -> {len(res)} results")
    for it in res[:n]:
        t = it["text"].replace("\n", " ")
        print("   -", t[:130])
    return res


show("AMO")
show("INE")
show("OL")
show("parac")
show("Parac")
show("E")
