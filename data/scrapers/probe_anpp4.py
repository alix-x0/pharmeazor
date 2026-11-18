import sys
import time

sys.path.insert(0, r"C:\data\scrapers")
from anpp import AnppClient, parse_results

c = AnppClient()
for q in ["AMOXIC", "AMOXICILL", "AMOXICILLINE", "AMOXICILLINE ACIDE CLAVULANIQUE",
          "AMOXICILLINE +", "ACID", "ACIDE", "CEF", "CEFIX", "CEFIXIME",
          "SPIR", "SPIRON", "METH", "MÉTH", "PARAC", "PARACETAMOL "]:
    h, _ = c.search(q)
    res = parse_results(h)
    print(f"{q!r:36s} -> {len(res):3d}")
    for it in res[:3]:
        print("      ", it["text"][:110].replace("\n", " "))
    time.sleep(0.3)
