import re
import sys

sys.path.insert(0, r"C:\data\scrapers")
from bs4 import BeautifulSoup

h = open(r"C:\data\data\raw\bdpm_extrait.html", encoding="utf-8").read()
soup = BeautifulSoup(h, "lxml")
panel = soup.find(id="tabpanel-rcp-panel")
print("PANEL TAG", panel.name, panel.get("class"))

# show structure of the first 40 descendants
for i, el in enumerate(panel.find_all(True, recursive=True)[:60]):
    txt = el.get_text(" ", strip=True)[:70]
    print(f"{i:3d} <{el.name}> {el.get('class')} :: {txt}")
