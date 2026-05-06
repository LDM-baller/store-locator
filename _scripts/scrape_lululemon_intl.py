"""Scrape Lululemon's international stores (everything outside US/CA) and merge into
the existing data/lululemon.json (which already has 562 NA stores from Next.js SSR).

Strategy: Lululemon's regional sites (UK, EU, AU, NZ, JP, FR, DE) run on Salesforce
Commerce Cloud (Demandware). The store-locator XHR is Cloudflare-protected and
returns coords only there. But the locator page itself SSRs the nearby stores when
loaded with explicit `?lat=X&long=Y&radius=300` query params — exposing store ID,
name, phone, and hours but NOT addresses or coordinates.

So: hit `/store-locator?lat=...&long=...&radius=300` for a grid of city centers per
region, parse the SSR'd HTML, dedupe by store ID, then geocode each store via OSM
Nominatim using "Lululemon <store_name>, <region label>". Tag every international
store with coord_is_estimated=true.
"""
import json, pathlib, re, time, datetime, urllib.request, urllib.parse, hashlib

DATA_DIR = pathlib.Path(r"G:\My Drive\Programs\store-map\data")
CACHE_DIR = DATA_DIR / "_lulu_intl_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
INPUT_PATH = DATA_DIR / "lululemon.json"
MANUAL_OVERRIDES_PATH = pathlib.Path(r"G:\My Drive\Programs\store-map\manual_overrides.json")

VALID_STORE_TYPES = {"regular", "popup", "outlet", "flagship",
                     "concession", "showroom", "experiential", "other"}
VALID_STATUSES = {"active", "coming_soon", "closed"}
DEPT_STORE_NAMES = ("fenwick", "selfridges", "harrods", "daimaru", "brown thomas")

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

# Region grid. Each regional Demandware site is queried with a set of metro lat/long
# centers to ensure complete in-country coverage. London search alone returned 38
# stores spanning UK/BE/FR/NL/DE/IE — radius=300 (max) is wide.
# Country whitelist per region — used to reject Nominatim hits that landed in the
# wrong country (e.g. "Richmond" matching Richmond, VA instead of Richmond, London).
# All European regional sites share the same EU whitelist because each cross-lists
# nearby-country stores (e.g. lululemon.fr returned a Milan store).
EUROPE_CC = {"GB","IE","FR","DE","NL","BE","ES","IT","CH","AT","SE","NO","DK","FI",
             "PL","CZ","PT","LU","IS","HU","SK","SI","HR","GR","RO","BG"}
REGION_COUNTRIES = {
    "UK + Europe":              EUROPE_CC,
    "Australia":                {"AU"},
    "New Zealand":              {"NZ"},
    "Japan":                    {"JP"},
    "France (extra coverage)":  EUROPE_CC,
    "Germany (extra coverage)": EUROPE_CC,
}

REGIONS = [
    {
        "host": "www.lululemon.co.uk", "locale": "en-gb", "label": "UK + Europe",
        "centers": [
            (51.5074,  -0.1278, "London"),
            (48.8566,   2.3522, "Paris"),
            (52.5200,  13.4050, "Berlin"),
            (50.1109,   8.6821, "Frankfurt"),
            (40.4168,  -3.7038, "Madrid"),
            (41.9028,  12.4964, "Rome"),
            (52.3676,   4.9041, "Amsterdam"),
            (59.3293,  18.0686, "Stockholm"),
            (48.2082,  16.3738, "Vienna"),
            (53.3498,  -6.2603, "Dublin"),
        ],
    },
    {
        "host": "www.lululemon.com.au", "locale": "en-au", "label": "Australia",
        "centers": [
            (-33.8688, 151.2093, "Sydney"),
            (-37.8136, 144.9631, "Melbourne"),
            (-27.4698, 153.0251, "Brisbane"),
            (-31.9505, 115.8605, "Perth"),
            (-34.9285, 138.6007, "Adelaide"),
        ],
    },
    {
        "host": "www.lululemon.co.nz", "locale": "en-nz", "label": "New Zealand",
        "centers": [
            (-36.8485, 174.7633, "Auckland"),
            (-41.2865, 174.7762, "Wellington"),
        ],
    },
    {
        "host": "www.lululemon.co.jp", "locale": "ja-jp", "label": "Japan",
        "centers": [
            (35.6762, 139.6503, "Tokyo"),
            (34.6937, 135.5023, "Osaka"),
            (35.1815, 136.9066, "Nagoya"),
            (43.0621, 141.3544, "Sapporo"),
            (33.5904, 130.4017, "Fukuoka"),
        ],
    },
    {
        "host": "www.lululemon.fr", "locale": "fr-fr", "label": "France (extra coverage)",
        "centers": [
            (48.8566,   2.3522, "Paris"),
            (45.7640,   4.8357, "Lyon"),
        ],
    },
    {
        "host": "www.lululemon.de", "locale": "de-de", "label": "Germany (extra coverage)",
        "centers": [
            (52.5200,  13.4050, "Berlin"),
            (48.1351,  11.5820, "Munich"),
        ],
    },
]


# ────────────────────────────────────────────────────────────────────────────
# Fetching
# ────────────────────────────────────────────────────────────────────────────
def cache_path_for(url):
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{h}.html"

def fetch_ssr(host, locale, lat, lng, radius=300):
    url = f"https://{host}/{locale}/store-locator?lat={lat}&long={lng}&radius={radius}"
    cp = cache_path_for(url)
    if cp.exists():
        return url, cp.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8")
    cp.write_text(text, encoding="utf-8")
    time.sleep(0.4)
    return url, text


# ────────────────────────────────────────────────────────────────────────────
# SSR parsing — store-details-card blocks
# ────────────────────────────────────────────────────────────────────────────
HTML_ENTITIES = {
    "&amp;": "&", "&Eacute;": "É", "&eacute;": "é", "&Egrave;": "È", "&egrave;": "è",
    "&Aacute;": "Á", "&aacute;": "á", "&Iacute;": "Í", "&iacute;": "í",
    "&Oacute;": "Ó", "&oacute;": "ó", "&Uacute;": "Ú", "&uacute;": "ú",
    "&Ntilde;": "Ñ", "&ntilde;": "ñ", "&ouml;": "ö", "&auml;": "ä", "&uuml;": "ü",
    "&Ouml;": "Ö", "&Auml;": "Ä", "&Uuml;": "Ü", "&szlig;": "ß",
    "&apos;": "'", "&#39;": "'", "&quot;": "\"", "&nbsp;": " ",
    "&ndash;": "–", "&mdash;": "—",
}
def unescape_html(s):
    if not s: return s
    for k, v in HTML_ENTITIES.items():
        s = s.replace(k, v)
    return s

def parse_store_cards(html):
    """Yield {store_id, name, phone, hours} for each store-details-card in the SSR HTML."""
    cards = re.findall(
        r'<div class="store-details-card" data-store-id="(\d+)">(.+?)(?=<div class="store-details-card"|</div>\s*</label>\s*</div>\s*</div>\s*</div>\s*<div class="card-body" id=)',
        html, re.DOTALL,
    )
    out = []
    for sid, body in cards:
        # name
        nm = re.search(r'<span class="store-name">([^<]+)</span>', body)
        name = unescape_html(nm.group(1).strip()) if nm else None
        if name:
            name = re.sub(r'^\d+\.\s*', '', name).strip()
        # phone
        ph = re.search(r'<a [^>]*href="tel:([^"]+)"', body)
        phone = ph.group(1).strip() if ph else None
        # hours: collect all "Day: HH:MM - HH:MM" lines from inside store-hours
        hb = re.search(r'class="store-hours"\s*>(.*?)</div>\s*</div>\s*<', body, re.DOTALL)
        hours_text = None
        if hb:
            ht_lines = re.findall(r'((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[^<]*?\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}|Closed)', hb.group(1))
            ht_lines = [re.sub(r'\s+', ' ', l).strip() for l in ht_lines]
            hours_text = "; ".join(ht_lines) or None
        out.append({"store_id": sid, "name": name, "phone": phone, "hours": hours_text})
    return out


# ────────────────────────────────────────────────────────────────────────────
# Nominatim geocoding (returns lat/lng + country)
# ────────────────────────────────────────────────────────────────────────────
def nominatim_geocode(query, cache):
    if not query: return None
    if query in cache: return cache[query]
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "format": "json", "limit": 1, "addressdetails": 1, "q": query,
    })
    headers = {
        "User-Agent": "store-map-scraper/1.0 (private use; contact ldm@oddity.com)",
        "Accept-Language": "en",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data:
            d = data[0]
            lat, lng = float(d["lat"]), float(d["lon"])
            addr = d.get("address") or {}
            cc = (addr.get("country_code") or "").upper() or None
            cn = addr.get("country") or None
            city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("suburb")
            postal = addr.get("postcode")
            state = addr.get("state") or addr.get("region")
            full = d.get("display_name")
            cache[query] = {"lat": lat, "lng": lng, "country_code": cc,
                            "country_name": cn, "city": city, "state": state,
                            "postal_code": postal, "display_name": full}
            return cache[query]
        cache[query] = None
        return None
    except Exception as e:
        print(f"    nominatim error for {query!r}: {e}")
        cache[query] = None
        return None
    finally:
        time.sleep(1.05)


# ────────────────────────────────────────────────────────────────────────────
# Auto-classification & manual overrides
# ────────────────────────────────────────────────────────────────────────────
def load_manual_overrides():
    """Load the per-store-ID overrides file. Skip metadata keys (start with '_')."""
    if not MANUAL_OVERRIDES_PATH.exists():
        return {}
    raw = json.loads(MANUAL_OVERRIDES_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}

def classify_from_name(name):
    """Return (store_type, status). Closed stores get status='closed' (caller drops them)."""
    if not name:
        return ("regular", "active")
    nl = name.lower()
    if "closed" in nl or "permanently closed" in nl:
        return ("regular", "closed")
    status = "coming_soon" if ("coming soon" in nl or "(coming" in nl) else "active"
    if "pop-up" in nl or "popup" in nl:
        return ("popup", status)
    if "factory outlet" in nl or "outlet" in nl:
        return ("outlet", status)
    for ds in DEPT_STORE_NAMES:
        if ds in nl:
            return ("concession", status)
    return ("regular", status)

def backfill_na_classification(s):
    """Add store_type and status to an existing NA store from raw.storeStatus + raw.storeType.
    Lululemon NA's raw fields use the same vocabulary; minor mapping for active_soon."""
    raw = s.get("raw") or {}
    rs = raw.get("storeStatus")
    rt = raw.get("storeType")
    if rs == "active_soon":
        s["status"] = "coming_soon"
    elif rs == "closed":
        s["status"] = "closed"
    else:
        s["status"] = "active"
    s["store_type"] = rt if rt in VALID_STORE_TYPES else "regular"


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────
def main():
    print(f"Loading existing file: {INPUT_PATH}")
    existing = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    all_existing = existing["stores"]
    # Separate "NA baseline" (exact coords from the original Next.js scrape) from
    # any international stores added by a prior run — those will be re-derived.
    na_stores = [s for s in all_existing if not s.get("coord_is_estimated", False)
                 and s.get("country") in ("US", "CA")]
    print(f"  NA baseline (exact coords, US/CA): {len(na_stores)}")
    print(f"  ignoring {len(all_existing) - len(na_stores)} previously-added intl/estimated stores — will re-derive")

    for s in na_stores:
        s.setdefault("coord_is_estimated", False)
        s.setdefault("raw", {})
        s["raw"].setdefault("_coord_source", "embedded")
        # Backfill store_type and status from the original raw storeStatus/storeType
        backfill_na_classification(s)

    # Drop any NA stores that come back as closed (rare for Lulu NA but be safe)
    pre_drop = len(na_stores)
    na_stores = [s for s in na_stores if s.get("status") != "closed"]
    if pre_drop != len(na_stores):
        print(f"  dropped {pre_drop - len(na_stores)} closed NA stores")

    existing_ids = {s["id"] for s in na_stores}

    # Manual overrides for problem stores (read once, used during geocoding)
    overrides = load_manual_overrides()
    print(f"  manual overrides loaded: {len(overrides)}")

    # ── 1. Scrape SSR per region ──
    by_id = {}            # store_id -> {raw_card, region_label, search_centers_seen[]}
    fetch_log = []
    for region in REGIONS:
        host, locale, label = region["host"], region["locale"], region["label"]
        print(f"\n=== {label} ({host}) ===")
        for lat, lng, center_label in region["centers"]:
            try:
                url, html = fetch_ssr(host, locale, lat, lng)
            except Exception as e:
                print(f"  fetch failed {center_label}: {e}")
                fetch_log.append({"center": center_label, "url": url if 'url' in dir() else None,
                                  "status": "fetch_failed", "err": str(e)})
                continue
            cards = parse_store_cards(html)
            new_in_this_search = 0
            for c in cards:
                sid = c["store_id"]
                if sid in by_id:
                    by_id[sid]["centers_seen"].append(center_label)
                else:
                    by_id[sid] = {**c, "region_label": label, "centers_seen": [center_label]}
                    new_in_this_search += 1
            print(f"  {center_label:>12} -> {len(cards):>3} cards   ({new_in_this_search} new)")
            fetch_log.append({"center": center_label, "label": label, "cards": len(cards), "new": new_in_this_search})

    print(f"\nUnique international store IDs collected: {len(by_id)}")

    # ── 2. Geocode each store ──
    print("\nGeocoding via OSM Nominatim (1 req/sec)...")
    geo_cache = {}
    geocoded_n = 0; geocode_failed = []
    scraped_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    intl_stores = []
    rejected_wrong_country = []
    dropped_closed = []
    override_applied = []
    for sid, c in by_id.items():
        name = c["name"] or ""
        region = c["region_label"]
        store_id_full = f"lululemon-{sid}"

        # Auto-classify from name (gives store_type + status)
        auto_type, auto_status = classify_from_name(name)

        # Apply manual override on top (override always wins)
        ov = overrides.get(store_id_full) or {}
        store_type = ov.get("store_type", auto_type)
        if store_type not in VALID_STORE_TYPES:
            store_type = auto_type
        status = ov.get("status", auto_status)
        if status not in VALID_STATUSES:
            status = auto_status

        # Drop closed stores entirely
        if status == "closed":
            dropped_closed.append((sid, name))
            continue
        if ov:
            override_applied.append((sid, name))

        # Skip if already in NA file (some store IDs surprise-overlap)
        if store_id_full in existing_ids:
            print(f"  [skip] {store_id_full} already in NA file - not double-adding")
            continue

        # ── coordinate sourcing ──
        result = None
        used_q = None

        # 1. If override has explicit lat/lng, use them directly (no geocode)
        if "lat" in ov and "lng" in ov:
            result = {
                "lat": float(ov["lat"]), "lng": float(ov["lng"]),
                "country_code": (ov.get("country") or "").upper() or None,
                "city": ov.get("city"), "state": ov.get("state"),
                "postal_code": ov.get("postal_code"),
                "display_name": "(manual override coords)",
            }
            used_q = "manual_override_latlng"
        else:
            # 2. Build candidate queries.
            # If override has a hand-tuned geocode_query, that's the only candidate.
            # Otherwise, the progressive default progression.
            if "geocode_query" in ov and ov["geocode_query"]:
                candidate_queries = [ov["geocode_query"]]
            else:
                first_center = (c.get("centers_seen") or [region])[0]
                candidate_queries = [
                    f"Lululemon {name}, {first_center}, {region}",
                    f"{name}, {first_center}, {region}",
                    f"Lululemon {name}, {region}",
                    f"{name}, {region}",
                    f"Lululemon {name}, {first_center}",
                    f"{name}, {first_center}",
                    f"Lululemon {name}",
                    name,
                ]

            whitelist = REGION_COUNTRIES.get(region)
            for q in candidate_queries:
                r = nominatim_geocode(q, geo_cache)
                if not r:
                    continue
                # Whitelist validation — but bypass for manual queries (user's intent overrides)
                if whitelist and r.get("country_code") and r["country_code"] not in whitelist \
                   and "geocode_query" not in ov:
                    rejected_wrong_country.append((sid, name, region, r["country_code"], q))
                    continue
                result = r
                used_q = q
                break

        if not result:
            geocode_failed.append((sid, name, region))
            continue

        geocoded_n += 1
        intl_stores.append({
            "id":          store_id_full,
            "retailer":    "Lululemon",
            "name":        name or None,
            "address":     None,
            "city":        result.get("city"),
            "state":       result.get("state"),
            "country":     result.get("country_code"),
            "postal_code": result.get("postal_code"),
            "lat":         result["lat"],
            "lng":         result["lng"],
            "coord_is_estimated": True,
            "store_type":  store_type,
            "status":      status,
            "phone":       c.get("phone"),
            "hours":       c.get("hours"),
            "url":         None,
            "year_opened": None,
            "scraped_at":  scraped_at,
            "raw": {
                "_coord_source": "nominatim" if used_q != "manual_override_latlng" else "manual_override",
                "_geocode_query": used_q,
                "_nominatim_display_name": result.get("display_name"),
                "_region_label": c["region_label"],
                "_search_centers_seen": c["centers_seen"],
                "_demandware_store_id": sid,
                "_auto_classification": {"store_type": auto_type, "status": auto_status},
                "_manual_override": ov if ov else None,
            },
        })

    print(f"\n  geocoded: {geocoded_n} / {len(by_id)} international stores")
    print(f"  manual overrides applied: {len(override_applied)}")
    for sid, n in override_applied:
        print(f"    {sid} {n!r}")
    print(f"  closed stores dropped: {len(dropped_closed)}")
    for sid, n in dropped_closed:
        print(f"    {sid} {n!r}")
    if rejected_wrong_country:
        print(f"  rejected wrong-country results: {len(rejected_wrong_country)}")
        for sid, n, r, cc, q in rejected_wrong_country:
            print(f"    {sid} {n!r} expected={r} got={cc}  query={q!r}")
    if geocode_failed:
        print(f"  FAILED to geocode {len(geocode_failed)}:")
        for sid, n, r in geocode_failed: print(f"    {sid} {n!r} ({r})")

    # ── 3. Merge & write ──
    all_stores = na_stores + intl_stores
    geocoded_count = sum(1 for s in all_stores if s.get("coord_is_estimated"))

    from collections import Counter as _C
    type_counts = dict(_C(s.get("store_type", "regular") for s in all_stores))
    status_counts = dict(_C(s.get("status", "active") for s in all_stores))

    output = {
        "retailer":     "Lululemon",
        "slug":         "lululemon",
        "source_url":   "https://shop.lululemon.com/stores/all-lululemon-stores (NA) + https://www.lululemon.<region>/<locale>/store-locator?lat=&long=&radius=300 (international, SSR)",
        "platform":     "custom-nextjs-ssr (NA) + Salesforce Commerce Cloud SSR (international)",
        "scope":        "global",
        "scraped_at":   scraped_at,
        "store_count":  len(all_stores),
        "geocoded_count": geocoded_count,
        "store_type_counts": type_counts,
        "status_counts":     status_counts,
        "geocoded_note": (
            "All international Lululemon stores (everything outside US/CA) have estimated "
            "coordinates from OSM Nominatim. Lululemon's regional sites run on Salesforce "
            "Commerce Cloud — the locator XHR is Cloudflare-protected, so coordinates and "
            "addresses are not directly retrievable. The SSR locator page exposes store name, "
            "phone, and hours but no address. We geocode each by store name + region "
            "(typically a famous landmark or street like 'Covent Garden' or 'Champs-Élysées'), "
            "yielding city-block accuracy. NA stores (562) retain their exact coordinates from "
            "Lululemon's Next.js __NEXT_DATA__ payload and are flagged coord_is_estimated=false."
        ),
        "stores":       all_stores,
    }

    INPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(all_stores)} stores -> {INPUT_PATH}")
    print(f"  NA exact:               {len(na_stores)}")
    print(f"  international estimated: {len(intl_stores)}")

    # Validation
    from collections import Counter
    cc = Counter(s["country"] for s in all_stores)
    sources = Counter(s["raw"].get("_coord_source") for s in all_stores)
    print("\n--- VALIDATION ---")
    print(f"All have coordinates: {'YES' if all(s.get('lat') for s in all_stores) else 'NO'}")
    print(f"Coord source: {dict(sources)}")
    print(f"store_type counts: {type_counts}")
    print(f"status counts:     {status_counts}")
    print(f"Top countries:")
    for c, n in cc.most_common(15):
        print(f"  {c}: {n}")

    print("\n--- SAMPLE INTERNATIONAL STORES ---")
    for s in intl_stores[:6] + intl_stores[-3:]:
        print(f"  [{s['country']}] {s['name']:<40} ({s['lat']:.4f}, {s['lng']:.4f}) phone={s['phone']!r}")


if __name__ == "__main__":
    main()
