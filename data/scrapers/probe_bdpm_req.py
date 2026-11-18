"""Probe: fetch BDPM extract page with plain requests and parse panels."""
import sys
import time

sys.path.insert(0, r"C:\data\scrapers")
from bs4 import BeautifulSoup
from http_util import get

CIS = "60206332"
url = f"https://base-donnees-publique.medicaments.gouv.fr/medicament/{CIS}/extrait"

r = get(url, timeout=90)
print("status", r.status_code, "len", len(r.text))
soup = BeautifulSoup(r.text, "lxml")

for pid in ["tabpanel-rcp-panel", "tabpanel-notice-panel"]:
    el = soup.find(id=pid)
    print("\n\n#####", pid, "found" if el else "MISSING")
    if el:
        txt = el.get_text("\n", strip=True)
        print("TEXT LEN", len(txt))
        print(txt[:2500])
