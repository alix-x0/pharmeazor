"""Probe 2: parse ANPP search results HTML."""
import json
import re
import sys
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, r"C:\data\scrapers")

BASE = "https://rcp.anpp.dz"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

s = requests.Session()
s.headers.update({"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"})

r = s.get(BASE + "/", timeout=60)
html = r.text
token = re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)
snap_m = re.search(r'wire:snapshot="(\{&quot;data.*?)" wire:effects', html, re.S)
snapshot = snap_m.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
snap = json.loads(snapshot)

payload = {
    "_token": token,
    "components": [{
        "snapshot": json.dumps(snap),
        "updates": {"query": "paracetamol"},
        "calls": [{"path": "", "method": "search", "params": []}],
    }],
}
r2 = s.post(BASE + "/livewire/update", json=payload,
            headers={"X-Livewire": "true", "Referer": BASE + "/", "Accept": "application/json"}, timeout=60)
data = r2.json()
eff = data["components"][0]["effects"]
h = eff["html"]
open(r"C:\data\data\raw\anpp_probe.html", "w", encoding="utf-8").write(h)
soup = BeautifulSoup(h, "lxml")
# find the section that holds results
for sec in soup.find_all("section"):
    txt = sec.get_text(" ", strip=True)
    if "résultat" in txt.lower() or "Aucun" in txt:
        print("=== SECTION ===")
        print(txt[:2000])
        for a in sec.find_all("a", href=True):
            print("LINK:", a.get_text(" ", strip=True)[:120], "->", a["href"])
        for tb in sec.find_all("table"):
            print("TABLE rows:")
            for tr in tb.find_all("tr"):
                print("  |", " || ".join(td.get_text(" ", strip=True)[:80] for td in tr.find_all(["td", "th"])))
