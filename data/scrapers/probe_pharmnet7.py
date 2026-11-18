import json
import sys

sys.path.insert(0, r"C:\data\scrapers")
from http_util import get

SU = "https://yqhaaitrqqpvtcnomljm.supabase.co"
KEY = "sb_publishable_kCraKHzowqNyXwv9jfC81w_BQI7dIpK"
H = {"apikey": KEY, "Authorization": "Bearer " + KEY, "Accept": "application/json"}

names = ["dcis", "dci", "laboratoires", "notifications", "diffusions", "annuaire",
         "etablissements", "prod_dci", "produit_dci", "dcip", "specialites",
         "categories", "classes", "documents", "fiches", "rcps", "sav", "signalements",
         "alertes", "rappels", "recommandations", "bon_Usage", "interactions"]
for n in names:
    try:
        r = get(SU + f"/rest/v1/{n}?select=*&limit=1", headers=H, timeout=45)
        if r.status_code == 200:
            body = r.text
            print(f"OK  {n}: {body[:400]}")
        else:
            print(f"--  {n}: {r.status_code} {r.text[:150]}")
    except Exception as e:
        print(f"ERR {n}: {type(e).__name__}")
