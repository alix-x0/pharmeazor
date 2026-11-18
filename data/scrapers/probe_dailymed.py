import re
import sys

sys.path.insert(0, r"C:\data\scrapers")
from http_util import get

# ---- DailyMed SPL XML structure
r = get("https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/"
        "d37f2e3c-01f0-4a81-a46f-1615b82e2499.xml", timeout=180)
x = r.text
print("XML LEN", len(x))
print("--- codes present")
for m in sorted(set(re.findall(r"<code[^>]*>([^<]{2,60})</code>", x)))[:60]:
    print("   ", m)
print("--- top-level structure")
for m in re.findall(r"<(/?)([a-zA-Z][a-zA-Z0-9]{2,30})>", x[:4000]):
    pass
print(x[:1500])
