import sys
import time

sys.path.insert(0, r"C:\data\scrapers")
from anpp import AnppClient, parse_results

c = AnppClient()
for q in ["AMO", "AMOX", "AMOXICILLINE", "PAR", "PARA", "PARAC", "PARACET", "PARACETAM",
          "PARACETAMOL", "PARACETAMOL/CHLOR", "PARACÉT", "PARACÉTAMOL", "DOLI", "DOLIPRANE",
          "IBUPRO", "IBUP", "IBUPROF", "IBUPROFEN", "IBUPROFÈNE"]:
    h, _ = c.search(q)
    res = parse_results(h)
    dcis = sorted({it["text"].split("DCI")[-1].replace("Voir le RCP", "").strip() for it in res})
    print(f"{q!r:22s} -> {len(res):3d}  dcis={dcis[:8]}")
    time.sleep(0.3)
