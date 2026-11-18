import json
import sys

sys.path.insert(0, r"C:\data\scrapers")
from http_util import get, post

SU = "https://yqhaaitrqqpvtcnomljm.supabase.co"
KEY = "sb_publishable_kCraKHzowqNyXwv9jfC81w_BQI7dIpK"
H = {"apikey": KEY, "Authorization": "Bearer " + KEY, "Accept": "application/json"}

for q in ["/rest/v1/produits?select=*&limit=2",
          "/rest/v1/notices?select=*&limit=2",
          "/rest/v1/rcp?select=*&limit=2",
          "/rest/v1/dossiers?select=*&limit=2"]:
    try:
        r = get(SU + q, headers=H, timeout=60)
        print("\n==", q, r.status_code)
        print(r.text[:1200])
    except Exception as e:
        print(q, "ERR", type(e).__name__, str(e)[:120])
