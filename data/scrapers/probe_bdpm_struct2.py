import sys

sys.path.insert(0, r"C:\data\scrapers")
from bs4 import BeautifulSoup

h = open(r"C:\data\data\raw\bdpm_extrait.html", encoding="utf-8").read()
soup = BeautifulSoup(h, "lxml")
panel = soup.find(id="tabpanel-rcp-panel")
for hd in panel.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p"], limit=45):
    print(f"<{hd.name}> id={hd.get('id')!r} cls={hd.get('class')} :: {hd.get_text(' ', strip=True)[:90]}")
