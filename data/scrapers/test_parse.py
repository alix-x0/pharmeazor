import sys

sys.path.insert(0, r"C:\data\scrapers")
from pypdf import PdfReader
from rcp_parse import parse_rcp_text, section_index

r = PdfReader(r"C:\data\data\raw\sample_anpp.pdf")
text = "\n".join((p.extract_text() or "") for p in r.pages)
secs = parse_rcp_text(text)
print("N sections", len(secs))
for s in secs:
    print(f"  {s['number']!s:6s} {s['key']:26s} len={len(s['text']):6d}  {s['title'][:60]}")
idx = section_index(secs)
print("\n--- indications ---")
print(idx.get("indications", {}).get("text", "")[:600])
print("\n--- contre_indications ---")
print(idx.get("contre_indications", {}).get("text", "")[:600])
print("\n--- interactions ---")
print(idx.get("interactions", {}).get("text", "")[:600])
print("\n--- composition ---")
print(idx.get("composition", {}).get("text", "")[:500])
