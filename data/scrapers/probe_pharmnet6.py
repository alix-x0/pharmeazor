import json
import sys

sys.path.insert(0, r"C:\data\scrapers")
from http_util import get

SU = "https://yqhaaitrqqpvtcnomljm.supabase.co"
KEY = "sb_publishable_kCraKHzowqNyXwv9jfC81w_BQI7dIpK"
H = {"apikey": KEY, "Authorization": "Bearer " + KEY,
     "Accept": "application/openapi+json"}

r = get(SU + "/rest/v1/", headers=H, timeout=90)
print("status", r.status_code)
try:
    spec = r.json()
except Exception:
    print(r.text[:1500]); raise SystemExit
defs = spec.get("definitions", {})
print("TABLES:", len(defs))
for name in sorted(defs):
    props = list((defs[name].get("properties") or {}).keys())
    print(f"\n== {name} ({len(props)})")
    print("   ", props)
