"""ANPP RCP scraper - Livewire (Filament) search API."""
import html as html_mod
import json
import re
import sys
import time
import urllib.parse

from bs4 import BeautifulSoup
from http_util import get, post

BASE = "https://rcp.anpp.dz"
COMPONENT = "app.filament.resources.rcp-resource.pages.browse-rcp"


class AnppClient:
    def __init__(self):
        self._snap = None
        self._token = None
        self._cookie = None

    def _load_page(self):
        r = get(BASE + "/")
        html = r.text
        self._token = re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)
        m = re.search(r'wire:snapshot="(\{&quot;data.*?)" wire:effects', html, re.S)
        if not m:
            raise RuntimeError("snapshot not found")
        snap = (m.group(1).replace("&quot;", '"').replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&#039;", "'"))
        self._snap = json.loads(snap)

    def search(self, query, tries=3):
        """Run a Livewire search, return (html, snapshot)."""
        if self._snap is None:
            self._load_page()
        payload = {
            "_token": self._token,
            "components": [{
                "snapshot": json.dumps(self._snap),
                "updates": {"query": query},
                "calls": [{"path": "", "method": "search", "params": []}],
            }],
        }
        last = None
        for attempt in range(tries):
            try:
                r = post(BASE + "/livewire/update", json=payload,
                         headers={"X-Livewire": "true", "Referer": BASE + "/",
                                  "Accept": "application/json"})
                data = r.json()
                comp = data["components"][0]
                self._snap = json.loads(comp["snapshot"])
                return comp["effects"].get("html", ""), self._snap
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2)
                self._load_page()
        raise last


def parse_results(html_text):
    """Extract result cards from the rendered Livewire html."""
    soup = BeautifulSoup(html_text, "lxml")
    grid = None
    for div in soup.find_all("div"):
        cls = div.get("class") or []
        if any("grid-cols-1" in c for c in cls) and any("md:grid-cols-3" in c for c in cls):
            grid = div
            break
    items = []
    if grid is None:
        return items
    for card in grid.find_all(["div", "article"], recursive=True):
        link = card.find("a", href=True)
        if not link:
            continue
        if link.find_parent("div") is not grid and card is not grid:
            # keep only direct-ish cards
            pass
        txt = card.get_text(" ", strip=True)
        href = link["href"]
        if not txt or not href:
            continue
        items.append({"title": link.get_text(" ", strip=True), "href": href, "text": txt})
    # dedupe
    seen, out = set(), []
    for it in items:
        k = (it["href"], it["title"])
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


if __name__ == "__main__":
    c = AnppClient()
    for q in ["Paracétamol", "PARACETAMOL", "Doliprane", "paracetamol", "Ibuprofène", "Amoxicilline"]:
        h, _ = c.search(q)
        res = parse_results(h)
        print(f"\n### {q!r} -> {len(res)} results")
        for it in res[:8]:
            print("   -", it["title"][:80], "|", it["href"][:90])
            print("     text:", it["text"][:200])
