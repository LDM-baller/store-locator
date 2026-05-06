"""Use Playwright to fetch Lulu Mexico store list. Direct curl times out; site likely
has geo-blocking or anti-bot for non-MX IPs."""
import json, pathlib, re
from playwright.sync_api import sync_playwright

OUT_DIR = pathlib.Path(r"G:\My Drive\Programs\store-map\data")

URLS_TO_TRY = [
    "https://www.lululemon.com.mx/es-mx/store-locator",
    "https://www.lululemon.com.mx/store-locator",
    "https://www.lululemon.com.mx/es-mx/stores/all-lululemon-stores",
    "https://www.lululemon.com.mx/",
    "https://shop.lululemon.com/en-mx/stores/all-lululemon-stores",
]

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        for url in URLS_TO_TRY:
            print(f"\n=== {url} ===")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
                title = page.title()
                body_len = len(page.inner_text("body"))
                print(f"  title: {title}")
                print(f"  body text length: {body_len}")
                html = page.content()
                # Look for __NEXT_DATA__ or store list
                if '__NEXT_DATA__' in html:
                    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', html, re.DOTALL)
                    if m:
                        try:
                            data = json.loads(m.group(1))
                            # Walk for storeLocatorList
                            def walk(o, key):
                                if isinstance(o, dict):
                                    if key in o and isinstance(o[key], list):
                                        return o[key]
                                    for v in o.values():
                                        r = walk(v, key)
                                        if r is not None: return r
                                elif isinstance(o, list):
                                    for el in o:
                                        r = walk(el, key)
                                        if r is not None: return r
                                return None
                            stores = walk(data, "storeLocatorList") or walk(data, "stores") or walk(data, "locations")
                            if stores:
                                print(f"  FOUND store list: {len(stores)} stores")
                                # Save
                                clean = re.sub(r'[^a-z0-9]+','_', url.lower())[:40]
                                out_path = OUT_DIR / f"_lulu_mx_{clean}.json"
                                out_path.write_text(json.dumps(stores, indent=2, ensure_ascii=False), encoding='utf-8')
                                print(f"  -> {out_path}")
                                # Also save NEXT_DATA in case we need more
                                (OUT_DIR / f"_lulu_mx_next_{clean}.json").write_text(json.dumps(data, indent=2)[:200000], encoding='utf-8')
                                browser.close()
                                return
                        except Exception as e:
                            print(f"  parse err: {e}")
                # Look for any links that look like /stores/mx/...
                store_urls = re.findall(r'/stores/mx/[a-z-]+/[a-z0-9-]+', html, re.I)
                print(f"  /stores/mx/ links found: {len(set(store_urls))}")
                for u in sorted(set(store_urls))[:5]:
                    print(f"    {u}")
            except Exception as e:
                print(f"  fetch err: {e}")
        browser.close()

if __name__ == "__main__":
    main()
