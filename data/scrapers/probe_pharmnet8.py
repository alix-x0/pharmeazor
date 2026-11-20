import json
import sys

sys.path.insert(0, r"C:\data\scrapers")
from http_util import get

SU = "https://yqhaaitrqqpvtcnomljm.supabase.co"
KEY = "sb_publishable_kCraKHzowqNyXwv9jfC81w_BQI7dIpK"
H = {"apikey": KEY, "Authorization": "Bearer " + KEY, "Accept": "application/json"}

tests = [
    ("count all produits", "/rest/v1/produits?select=id&limit=1", {"Prefer": "count=exact", "Range": "0-0"}),
    ("count with rcp", "/rest/v1/produits?select=id&Rcp_url=not.is.null&limit=1", {"Prefer": "count=exact", "Range": "0-0"}),
    ("count with notice", "/rest/v1/produits?select=id&notice_url=not.is.null&limit=1", {"Prefer": "count=exact", "Range": "0-0"}),
    ("embed dci", "/rest/v1/produits?select=nom_commercial,dci(denumination,code)&dci.denomination=ilike.*parac%C3%A9tamol*&limit=3", {}),
    ("dci table match", "/rest/v1/dci?select=code,denomination&denomination=ilike.*parac%C3%A9tamol*&limit=5", {}),
]
for label, url, extra in tests:
    h = dict(H); h.update(extra)
    r = get(SU + url, headers=h, timeout=90)
    print(f"\n== {label} -> {r.status_code}")
    print(" content-range:", r.headers.get("content-range"))
    print(r.text[:700])
