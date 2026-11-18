import re
from collections import Counter

h = open(r"C:\data\pharmnet_home.html", encoding="utf-8").read()
c = Counter()
for pat in [r"qb\(['\"]([a-zA-Z_é ]+)['\"]\)",
            r"from\(['\"]([a-zA-Z_é ]+)['\"]\)",
            r"REST\+/['\"]([a-zA-Z_é ]+)['\"]",
            r"REST\+'/([a-zA-Z_é ]+)'",
            r"table\s*=\s*['\"]([a-zA-Z_é ]+)['\"]",
            r"\.rpc\(['\"]([a-zA-Z_é ]+)['\"]",
            r"table:\s*['\"]([a-zA-Z_é ]+)['\"]"]:
    for m in re.findall(pat, h):
        c[m] += 1
for k, v in sorted(c.items()):
    print(f"{v:4d}  {k}")
