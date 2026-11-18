import sys

sys.path.insert(0, r"C:\data\scrapers")
from anpp import AnppClient, parse_results

c = AnppClient()
for q in ["AMOXICILL", "AMOXICIL", "AMOXY", "AMOX", "CLAVULANI", "CLAVULAN", "ACIDECLAVULAN",
          "CEFIXIM", "CEFUROXIM", "CEFTRI", "AZITHROMYC", "CLARITHROMYC", "CIPROFLOXAC",
          "LEVOFLOXAC", "DOXYCYCL", "SULFAMETHOX", "TRIMETHOPR", "METRONIDAZ", "GENTAMIC",
          "CLINDAMYC", "AMLODIPIN", "NIFEDIPIN", "PERINDOPRIL", "RAMIPRIL", "ENALAPRIL",
          "VALSARTAN", "BISOPROLOL", "ATENOLOL", "NEBIVOLOL", "HYDROCHLORO", "INDAPAMID",
          "SPIRONOLACT", "METHYLDOP", "KETOPROFEN", "NAPROXEN", "ACETYLSALICYL", "MELOXICAM",
          "PIROXICAM", "CELECOXIB", "NEFOPAM", "CODEINE"]:
    h, _ = c.search(q)
    res = parse_results(h)
    dcis = sorted({it["text"].split("DCI")[-1].replace("Voir le RCP", "").strip() for it in res})
    print(f"{q!r:16s} -> {len(res):3d}  {dcis[:5]}")
