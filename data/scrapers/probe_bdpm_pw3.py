"""Probe BDPM detail/extrait pages."""
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
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        locale="fr-FR", ignore_https_errors=True)
    pg = ctx.new_page()
    for path in ["/medicament/60206332/extrait", "/medicament/60206332"]:
        print("\n\n########", path)
        goto_with_retry(pg, BASE + path)
        txt = pg.inner_text("body")
        print("LEN", len(txt))
        print(txt[:3000])
        print("=== LINKS ===")
        for h, t in pg.eval_on_selector_all("a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,70)])"):
            if h and ("dum.archivos" in h or ".pdf" in h.lower() or "notice" in h.lower() or "rcp" in h.lower()):
                print(repr(t), "->", h[:170])
    ctx.close()
    b.close()
