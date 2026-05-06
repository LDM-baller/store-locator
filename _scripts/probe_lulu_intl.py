"""Probe Lululemon UK locator with Playwright. Capture FindStores XHR + response shape."""
import json, pathlib
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

OUT_DIR = pathlib.Path(r"G:\My Drive\Programs\store-map\data")
LOG_PATH = OUT_DIR / "_lulu_uk_xhr_log.json"

LOCATOR_URL = "https://www.lululemon.co.uk/en-gb/store-locator"
SEARCH_CENTERS = [
    # (lat, long, label) — major UK metros
    (51.5074,  -0.1278, "London"),
    (53.4808,  -2.2426, "Manchester"),
    (55.9533,  -3.1883, "Edinburgh"),
]

xhr_log = []

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="en-GB",
        )
        page = ctx.new_page()

        def on_response(response):
            try:
                url = response.url
                if "FindStores" not in url and "Stores-" not in url:
                    return
                ct = response.headers.get("content-type", "")
                try:
                    body = response.body()
                except Exception:
                    return
                txt = body.decode("utf-8", errors="replace")
                xhr_log.append({
                    "url": url,
                    "status": response.status,
                    "method": response.request.method,
                    "content_type": ct,
                    "size": len(txt),
                    "preview": txt[:400],
                })
                print(f"  [{response.status}] {response.request.method} {url[:140]} size={len(txt)}")
            except Exception as e:
                print(f"  err: {e}")

        page.on("response", on_response)

        print(f"loading {LOCATOR_URL} ...")
        page.goto(LOCATOR_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        # Try a variety of param shapes — Cloudflare may accept some and reject others
        test_queries = [
            "postalCode=W1A%201AA&radius=300&showMap=false",
            "postalCode=SW1A%201AA&radius=300&showMap=false",
            "postalCode=London&radius=300&showMap=false",
            "postalCode=London&radius=300&showMap=true",
            "postalCode=W1A%201AA&radius=300",
            "lat=51.5074&long=-0.1278&radius=300&showMap=false",
            "lat=51.5074&long=-0.1278&radius=300&showMap=true",
        ]
        for q in test_queries:
            print(f"\nQuery: {q}")
            result = page.evaluate(f"""async () => {{
                const url = '/on/demandware.store/Sites-UK-Site/en_GB/Stores-FindStores?{q}';
                const r = await fetch(url, {{
                    method: 'GET',
                    headers: {{
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    }},
                    credentials: 'include',
                }});
                const text = await r.text();
                return {{ status: r.status, size: text.length, head: text.slice(0, 800) }};
            }}""")
            print(f"  status={result['status']} size={result['size']}")
            print(f"  head: {result['head'][:300]}")
            page.wait_for_timeout(500)

        LOG_PATH.write_text(json.dumps(xhr_log, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nXHR log: {len(xhr_log)} entries -> {LOG_PATH}")
        browser.close()


if __name__ == "__main__":
    main()
