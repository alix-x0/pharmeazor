import re

h = open(r"C:\data\pharmnet_home.html", encoding="utf-8").read()
print("LEN", len(h))
print("--- /api/ paths")
pats = set(re.findall(r'["\'`](/api/[A-Za-z0-9_\-/\.$\{\}]*)', h))
for p in sorted(pats):
    print(p[:140])
print("--- fetch calls")
for m in set(re.findall(r'fetch\(([^)]{0,140})', h)):
    print(m[:160])
print("--- inline script tags:", len(re.findall(r'<script', h)))
print("--- other urls")
for m in set(re.findall(r'https://[a-z0-9\.\-]+\.[a-z]{2,}/[A-Za-z0-9_\-/\.]*', h)):
    if 'google' not in m and 'fonts' not in m and 'unpkg' not in m and 'w3.org' not in m:
        print(m[:140])
