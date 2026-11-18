"""Probe the ANPP RCP Livewire search API."""
import json
import re
import sys
import requests

sys.path.insert(0, r"C:\data\scrapers")
from drugs import DRUGS

BASE = "https://rcp.anpp.dz"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

s = requests.Session()
s.headers.update({"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"})

r = s.get(BASE + "/", timeout=60)
html = r.text
token = re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)
snap_m = re.search(r'wire:snapshot="(\{&quot;data.*?)" wire:effects', html, re.S)
snapshot = (
    snap_m.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
)
print("token", token)
print("snapshot head", snapshot[:200])
snap = json.loads(snapshot)
print("memo", snap["memo"]["name"], snap["memo"]["id"], snap["memo"]["path"])

payload = {
    "_token": token,
    "components": [
        {
            "snapshot": json.dumps(snap),
            "updates": {"query": "paracetamol"},
            "calls": [{"path": "", "method": "search", "params": []}],
        }
    ],
}
r2 = s.post(
    BASE + "/livewire/update",
    json=payload,
    headers={"X-Livewire": "true", "Referer": BASE + "/", "Accept": "application/json"},
    timeout=60,
)
print("status", r2.status_code)
print(r2.text[:3000])
