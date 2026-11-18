import sys

sys.path.insert(0, r"C:\data\scrapers")
from http_util import get

paths = ["/robots.txt", "/sitemap.xml", "/rcps", "/rcp", "/medicaments", "/admin",
         "/api/rcps", "/browse", "/liste", "/products", "/api/documents",
         "/storage/rcp-pdfs/", "/js/app.js", "/livewire/livewire.js"]
for p in paths:
    try:
        r = get("https://rcp.anpp.dz" + p, timeout=40)
        print(f"{p:28s} {r.status_code} len={len(r.content):8d} {r.headers.get('content-type','')[:30]}")
        if p in ("/robots.txt", "/sitemap.xml") and r.status_code == 200:
            print("   >>>", r.text[:1500].replace("\n", " ")[:1500])
    except Exception as e:
        print(f"{p:28s} ERR {type(e).__name__}")
