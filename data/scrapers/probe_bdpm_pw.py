"""Probe BDPM with Playwright (JS-rendered search)."""
import sys
from playwright.sync_api import sync_playwright

BASE = "https://base-donnees-publique.medicaments.gouv.fr"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        locale="fr-FR")
    pg = ctx.new_page()
    url = BASE + "/?choixRecherche=substance&txtCaracteres=PARACETAMOL&action=show"
    pg.goto(url, timeout=90000, wait_until="domcontentloaded")
    pg.wait_for_timeout(4000)
    print("TITLE", pg.title())
    body = pg.inner_text("body")
    print("BODYLEN", len(body))
    i = body.find("Résultats")
    print("RESULTS SNIPPET:", body[i:i+1500] if i > 0 else body[:1500])
    print("=== LINKS ===")
    for el in pg.query_selector_all("a"):
        h = el.get_attribute("href") or ""
        t = (el.inner_text() or "").strip()
        if t and ("PARACETAMOL" in t.upper() or "DOLIPRANE" in t.upper() or "detail" in h or "dum.archivos" in h):
            print(repr(t[:70]), "->", h[:150])
    print("=== ALL HREFS SAMPLE ===")
    hrefs = pg.eval_on_selector_all("a", "els => els.map(e => e.getAttribute('href'))")
    print(len(hrefs))
    for h in hrefs:
        if h and ("/recherche" in h or "/detail" in h or "dum" in h):
            print(h[:160])
    ctx.close()
    b.close()
