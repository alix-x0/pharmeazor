"""Determine ANPP search query semantics + pagination."""
import sys
import time

sys.path.insert(0, r"C:\data\scrapers")
from anpp import AnppClient, parse_results

c = AnppClient()
queries = ["PARACETAMOL", "IBUPROFENE", "IBUPROFÈNE", "AMOXICILLINE", "AMOXICILLINE+ACIDE",
           "ACIDE CLAVULANIQUE", "CEFIXIME", "TRAMADOL", "DICLOFENAC", "DICLOFÉNAC",
           "LOSARTAN", "SPIRONOLACTONE", "METHYLDOPA", "MÉTHYLDOPA", "PARACETAMOL/CODEINE"]
for q in queries:
    try:
        h, _ = c.search(q)
        res = parse_results(h)
        # look for pagination markers
        soup_pag = "pagination" in h.lower()
        print(f"{q!r:28s} -> {len(res):3d} results  pagination={soup_pag}")
    except Exception as e:
        print(f"{q!r:28s} -> ERR {type(e).__name__} {str(e)[:80]}")
    time.sleep(0.4)
