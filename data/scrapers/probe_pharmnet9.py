import json
import sys

sys.path.insert(0, r"C:\data\scrapers")
from http_util import get

SU = "https://yqhaaitrqqpvtcnomljm.supabase.co"
KEY = "sb_publishable_kCraKHzowqNyXwv9jfC81w_BQI7dIpK"
H = {"apikey": KEY, "Authorization": "Bearer " + KEY, "Accept": "application/json"}

tests = [
    ("dci like paracetamol", "/rest/v1/dci?select=code,denomination&denomination=ilike.*paracetamol*&limit=5", {}),
    ("dci like parac", "/rest/v1/dci?select=code,denomination&denomination=ilike.*parac*&limit=10", {}),
    ("dci first 5", "/rest/v1/dci?select=code,denomination&limit=5", {}),
    ("embed dci_1", "/rest/v1/produits?select=nom_commercial,dci_1(denomination,code)&dci_1.denomination=ilike.*paracetamol*&limit=3", {}),
    ("produits with rcp url", "/rest/v1/produits?select=nom_commercial,dci_1(denomination),Rcp_url,notice_url,forme,dosage,laboratoire_id&Rcp_url=not.is.null", {}),
]
for label, url, extra in tests:
    h = dict(H); h.update(extra)
    r = get(SU + url, headers=h, timeout=90)
    print(f"\n== {label} -> {r.status_code}")
    print(r.text[:1200])
