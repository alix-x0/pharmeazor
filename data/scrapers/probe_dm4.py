import sys

sys.path.insert(0, r"C:\data\scrapers")
from lxml import etree
from s_dailymed import fetch_spl, search_spls

items = search_spls("acetaminophen", pagesize=1)
xml = fetch_spl(items[0]["setid"])
root = etree.fromstring(xml.encode("utf-8"), parser=etree.XMLParser(recover=True))


def tree(el, depth=0, maxdepth=6):
    if depth > maxdepth:
        return
    tag = etree.QName(el).localname if isinstance(el.tag, str) else str(el.tag)
    extra = ""
    if tag == "code":
        extra = f" code={el.get('code')} name={el.get('displayName')}"
    txt = (el.text or "").strip()[:35]
    print("  " * depth + f"<{tag}>{extra} {txt!r}")
    for ch in el:
        tree(ch, depth + 1, maxdepth)


tree(root, 0, 6)
