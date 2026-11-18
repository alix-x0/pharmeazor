"""Probe BDPM RCP tab mechanism."""
import re
import time
from playwright.sync_api import sync_playwright

BASE = "https://base-donnees-publique.medicaments.gouv.fr"


def goto_with_retry(pg, url, tries=6, wait=2500):
    last = None
    for i in range(tries):
        try:
            pg.goto(url, timeout=60000, wait_until="domcontentloaded")
            pg.wait_for_timeout(wait)
            return True
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  retry {i+1}/{tries}: {type(e).__name__}")
            time.sleep(3)
    raise last


with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ChromeWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        locale="fr-FR", ignore_https_errors=True)
    pg = ctx.new_page()
    goto_with_retry(pg, BASE + "/medicament/60206332/extrait")
    html = pg.content()
    open(r"C:\data\data\raw\bdpm_extrait.html", "w", encoding="utf-8").write(html)
    print("HTMLLEN", len(html))
    for kw in ["Résumé des caractéristiques", "iframe", "dum.archivos", "pdf", "tabpanel", "data-tab"]:
        print(f"--- occurrences of {kw}:", html.lower().count(kw.lower()))
    i = html.find("Résumé des caractéristiques")
    print("=== CONTEXT ===")
    print(html[max(0, i - 3000):i + 3000])
    ctx.close()
    b.close()
