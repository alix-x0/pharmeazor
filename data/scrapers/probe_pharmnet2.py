import re

h = open(r"C:\data\pharmnet_home.html", encoding="utf-8").read()
for name in ["SUPABASE_URL", "SUPABASE_KEY", "REST", "AUTH", "OFF_FUNC"]:
    for m in re.finditer(r"(?:const|let|var)\s+" + name + r"\s*=\s*([^;\n]{0,200})", h):
        print(name, "=>", m.group(1)[:200])
        break
    else:
        # fall back: find assignment anywhere
        m = re.search(name + r"\s*=\s*([^;\n]{0,200})", h)
        print(name, "?? =>", (m.group(1)[:200] if m else "NOT FOUND"))
