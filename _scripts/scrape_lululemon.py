"""Scrape Lululemon North America stores from the all-stores page (Next.js SSR)."""
import re, json, pathlib, datetime, sys, urllib.request

RETAILER_NAME = "Lululemon"
RETAILER_SLUG = "lululemon"
PLATFORM      = "custom-nextjs-ssr"
SOURCE_URL    = "https://shop.lululemon.com/stores/all-lululemon-stores"

OUTPUT_DIR = pathlib.Path(r"G:\My Drive\Programs\store-map\data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def extract_next_data(html: str) -> dict:
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
        html, re.DOTALL,
    )
    if not m:
        raise RuntimeError("Could not find __NEXT_DATA__ in page")
    return json.loads(m.group(1))


def parse_full_address(full: str) -> dict:
    """'234 N. Gay Street, Unit C1, Auburn, AL, US, 36830'
       -> street='234 N. Gay Street, Unit C1', city/state/country/postal."""
    parts = [p.strip() for p in full.split(",")]
    if len(parts) < 4:
        return {"address": full, "city": None, "state": None, "country": None, "postal_code": None}
    postal = parts[-1]
    country = parts[-2]
    state = parts[-3]
    city = parts[-4]
    street = ", ".join(parts[:-4]) if len(parts) > 4 else parts[0]
    return {"address": street, "city": city, "state": state, "country": country, "postal_code": postal}


def normalize(raw: dict, scraped_at: str) -> dict:
    addr = parse_full_address(raw.get("fullAddress", ""))
    slug = raw.get("slug") or ""
    url = f"https://shop.lululemon.com{slug}" if slug.startswith("/") else slug or None
    return {
        "id":          f"{RETAILER_SLUG}-{raw['id']}",
        "retailer":    RETAILER_NAME,
        "name":        raw.get("name"),
        "address":     addr["address"],
        "city":        addr["city"],
        "state":       addr["state"],
        "country":     addr["country"],
        "postal_code": addr["postal_code"],
        "lat":         raw.get("latitude"),
        "lng":         raw.get("longitude"),
        "phone":       None,
        "hours":       raw.get("hours"),
        "url":         url,
        "year_opened": None,
        "scraped_at":  scraped_at,
        "raw":         raw,
    }


def main():
    print(f"Fetching {SOURCE_URL} ...")
    html = fetch_html(SOURCE_URL)
    print(f"  got {len(html):,} bytes")

    nd = extract_next_data(html)
    raw_stores = nd["props"]["pageProps"]["storeListData"]["data"]["storeLocatorList"]
    print(f"  found {len(raw_stores)} raw store records")

    scraped_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    stores = [normalize(s, scraped_at) for s in raw_stores]

    seen = {}
    for s in stores:
        seen[s["id"]] = s
    if len(seen) != len(stores):
        print(f"  WARNING: collapsed {len(stores) - len(seen)} duplicate IDs")
    stores = list(seen.values())

    output = {
        "retailer":    RETAILER_NAME,
        "slug":        RETAILER_SLUG,
        "source_url":  SOURCE_URL,
        "platform":    PLATFORM,
        "scope":       "North America only (US + CA). EU/UK/AU/JP not included — those live on different regional sites.",
        "scraped_at":  scraped_at,
        "store_count": len(stores),
        "stores":      stores,
    }

    out_path = OUTPUT_DIR / f"{RETAILER_SLUG}.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(stores)} stores -> {out_path}")

    from collections import Counter
    countries = Counter(s["country"] for s in stores)
    statuses = Counter(s["raw"].get("storeStatus") for s in stores)
    types = Counter(s["raw"].get("storeType") for s in stores)
    no_coord = [s for s in stores if s["lat"] is None or s["lng"] is None]

    print("\n--- VALIDATION ---")
    print(f"All have coordinates: {'YES' if not no_coord else f'NO ({len(no_coord)} missing)'}")
    print(f"Countries: {dict(countries)}")
    print(f"Statuses:  {dict(statuses)}")
    print(f"Types:     {dict(types)}")

    print("\n--- SAMPLE STORES ---")
    samples = [stores[0], stores[len(stores)//2], stores[-1]]
    for s in samples:
        print(f"  {s['name']} ({s['country']}) - {s['address']}, {s['city']}, {s['state']} {s['postal_code']}")
        print(f"    lat/lng: {s['lat']}, {s['lng']}")


if __name__ == "__main__":
    main()
