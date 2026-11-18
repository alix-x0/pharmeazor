import sys

sys.path.insert(0, r"C:\data\scrapers")
from bs4 import BeautifulSoup
from http_util import get

for p in ["/admin", "/admin/rcps", "/admin/rcp-resources", "/admin/login", "/admin/rcp-resources/1/edit"]:
    r = get("https://rcp.anpp.dz" + p, timeout=40)
    s = BeautifulSoup(r.text, "lxml")
    title = s.title.get_text(strip=True) if s.title else ""
    print(f"\n=== {p} -> {r.status_code} '{title}'")
    # livewire components
    import re
    for m in re.finditer(r'wire:snapshot="([^"]{0,400})', r.text):
        print("   SNAP:", m.group(1)[:250])
    if r.status_code == 200 and "login" not in p:
        txt = s.get_text(" ", strip=True)
        print("   TEXT:", txt[:600])
