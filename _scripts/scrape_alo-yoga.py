"""Scrape Alo Yoga global store locations.

Source: Alo's /pages/stores is built with Builder.io. The page payload at
cdn.builder.io/api/v3/query/<APIKEY>/web-component-page?...urlPath=/pages/stores
embeds 224+ stores under
  data.web-component-page[0].data.state.storeDataByLocation.results

Each result is a country (selectCountry='Global') or US/Canada region with a
storeList. Per-store fields: name, city, location (HTML w/ Google Maps link),
phone, hours, yogaStudio, aloStudioAvailability, rsvpLink, storeLink.

Coordinates come from the Google Maps URL embedded in the location HTML:
  - newer entries: @<lat>,<lng>,17z form -> direct extract
  - older entries: goo.gl/maps/<id> short URL -> follow 302 redirect to the long URL,
    then extract @<lat>,<lng>
"""
import json, pathlib, re, time, datetime, urllib.request, urllib.error, urllib.parse

RETAILER_NAME = "Alo Yoga"
RETAILER_SLUG = "alo-yoga"
PLATFORM      = "custom-builder.io"
SCOPE         = "global"
SOURCE_URL    = "https://www.aloyoga.com/pages/stores"
BUILDER_API_KEY = "aa96744e7fe74e2a90d22918299c1f1d"
BUILDER_URL = (
    f"https://cdn.builder.io/api/v3/query/{BUILDER_API_KEY}/web-component-page"
    f"?omit=meta.componentsUsed"
    f"&apiKey={BUILDER_API_KEY}"
    f"&includeUnpublished=false"
    f"&locale=en"
    f"&userAttributes.urlPath=%2Fpages%2Fstores"
    f"&userAttributes.host=www.aloyoga.com"
    f"&userAttributes.device=desktop"
    f"&userAttributes.isLoggedIn=false"
    f"&userAttributes.countryCode=US"
    f"&userAttributes.isApp=false"
    f"&userAttributes.contentSemantic=members-exclusive"
    f"&options.web-component-page.model=%22web-component-page%22"
)

OUTPUT_DIR = pathlib.Path(r"G:\My Drive\Programs\store-map\data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}

# Country name -> ISO 3166-1 alpha-2 (covers everything in Alo's list)
COUNTRY_TO_CODE = {
    "United States": "US", "Canada": "CA",
    "Australia": "AU", "Bahrain": "BH", "Brazil": "BR", "Colombia": "CO",
    "Dominican Republic": "DO", "France": "FR", "Indonesia": "ID",
    "Ireland": "IE", "Israel": "IL", "Italy": "IT", "Kuwait": "KW",
    "Lebanon": "LB", "Malaysia": "MY", "Mexico": "MX", "Netherlands": "NL",
    "Panama": "PA", "Peru": "PE", "Philippines": "PH", "Qatar": "QA",
    "Saudi Arabia": "SA", "Singapore": "SG", "South Korea": "KR",
    "Thailand": "TH", "Turkey": "TR", "UAE": "AE", "United Kingdom": "GB",
}

COORD_RE = re.compile(r'@(-?\d+\.\d+),(-?\d+\.\d+)')
GOOGL_RE = re.compile(r'https://goo\.gl/maps/[A-Za-z0-9]+')
GOOGL_APP_RE = re.compile(r'https://maps\.app\.goo\.gl/[A-Za-z0-9]+')
GPAGE_RE = re.compile(r'https://g\.page/[A-Za-z0-9_.\-]+(?:\?[^"\s<>]*)?')
LONG_PLACE_RE = re.compile(r'https://www\.google\.com/maps/place/[^"\s<>]+')
DATA_3D4D_RE = re.compile(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)')

def http_get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")

def resolve_googl(short_url, cache):
    """Follow goo.gl redirect and return the final long URL (or None on failure)."""
    if short_url in cache:
        return cache[short_url]
    try:
        req = urllib.request.Request(short_url, headers=HEADERS, method="HEAD")
        # use the urllib opener that follows redirects
        with urllib.request.urlopen(req, timeout=15) as r:
            final = r.geturl()
        cache[short_url] = final
        time.sleep(0.3)
        return final
    except Exception as e:
        cache[short_url] = None
        print(f"    goo.gl resolve failed for {short_url}: {e}")
        return None

def strip_html(s):
    if not s: return None
    # convert <br> / </br> to newline; strip other tags
    s = re.sub(r'<\s*br\s*/?\s*>|</\s*br\s*>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&#39;|&apos;', "'", s)
    s = re.sub(r'&quot;', '"', s)
    s = re.sub(r'&ndash;', '–', s)
    s = re.sub(r'&mdash;', '—', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip() or None

def parse_address_from_link_text(link_text):
    """Older entries embed the address as link text with <br> separators.
    Returns (address_lines, last_line_with_city_state_zip)."""
    if not link_text: return None
    parts = re.split(r'<\s*br\s*/?\s*>|</\s*br\s*>', link_text, flags=re.I)
    parts = [strip_html(p) for p in parts]
    parts = [p for p in parts if p]
    return parts  # list of address lines

US_CITY_STATE_RE = re.compile(r'^(?P<city>[^,]+?),\s*(?P<state>[A-Z]{2})(?:,)?\s*(?P<zip>\d{5}(?:-\d{4})?)?$')

def parse_us_address_lines(lines):
    """Given the address lines from the link text, derive
    (street, city, state, postal). Designed for US/CA store entries."""
    if not lines: return (None, None, None, None)
    # last line should be 'City, ST 12345' (US) or 'City, PROV  K1A 0B1' (CA)
    last = lines[-1]
    m = US_CITY_STATE_RE.match(last.strip())
    if m:
        street = ", ".join(lines[:-1]) if len(lines) > 1 else None
        return (street, m.group("city").strip(), m.group("state"), m.group("zip"))
    # Canadian postal: 'City, PROV K1A 0B1'
    m_ca = re.match(r'^(?P<city>[^,]+?),\s*(?P<state>[A-Z]{2})\s+(?P<zip>[A-Z]\d[A-Z]\s?\d[A-Z]\d)$', last.strip())
    if m_ca:
        street = ", ".join(lines[:-1]) if len(lines) > 1 else None
        return (street, m_ca.group("city").strip(), m_ca.group("state"), m_ca.group("zip"))
    # Fallback: everything as 'address', leave city/state/zip null
    return (", ".join(lines), None, None, None)

def slugify(s):
    s = re.sub(r"[^\w\s-]", "", (s or "").lower())
    s = re.sub(r"[\s-]+", "-", s).strip("-")
    return s or "x"

def _coords_from_url(url):
    """Pull (lat, lng) from a Maps URL or None. Tries @lat,lng then !3d/!4d."""
    if not url: return None
    m = COORD_RE.search(url)
    if m: return (float(m.group(1)), float(m.group(2)))
    m = DATA_3D4D_RE.search(url)
    if m: return (float(m.group(1)), float(m.group(2)))
    return None

def nominatim_geocode(query, cache):
    """OSM Nominatim geocode. ToS: 1 req/sec max, real User-Agent. Returns (lat, lng) or None."""
    if not query: return None
    if query in cache: return cache[query]
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"format": "json", "limit": 1, "addressdetails": 0, "q": query}
    )
    headers = {
        "User-Agent": "store-map-scraper/1.0 (private use; contact ldm@oddity.com)",
        "Accept-Language": "en",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data and isinstance(data, list):
            lat = float(data[0]["lat"]); lng = float(data[0]["lon"])
            cache[query] = (lat, lng)
            return (lat, lng)
        cache[query] = None
        return None
    except Exception as e:
        print(f"    nominatim error for {query!r}: {e}")
        cache[query] = None
        return None
    finally:
        time.sleep(1.05)  # ToS: 1 req/sec max

def extract_coords(loc_html, redirect_cache):
    """Extract (lat, lng, source) from a store's location HTML.

    Tries (in order): embedded @lat,lng, goo.gl short URL, maps.app.goo.gl
    short URL, g.page short URL, fetching the long /maps/place/<addr> URL."""
    if not loc_html:
        return (None, None, None)

    # 1. Direct @lat,lng or !3d/!4d already present
    direct = _coords_from_url(loc_html)
    if direct:
        return (direct[0], direct[1], "embedded")

    # 2. Short URLs that 302-redirect to a coord-bearing long URL
    for pat, source in ((GOOGL_RE, "googl-redirect"),
                        (GOOGL_APP_RE, "googl-app-redirect"),
                        (GPAGE_RE, "gpage-redirect")):
        m = pat.search(loc_html)
        if m:
            long_url = resolve_googl(m.group(0), redirect_cache)
            if long_url:
                c = _coords_from_url(long_url)
                if c: return (c[0], c[1], source)

    # 3. Long /maps/place/<addr>/data=... URLs that lack @lat,lng — follow them
    #    (Google sometimes returns a redirect with coords or HTML containing them)
    m = LONG_PLACE_RE.search(loc_html)
    if m:
        long_url = m.group(0).replace("&amp;", "&")
        # only fetch if it doesn't already contain coords (cheap check)
        if not _coords_from_url(long_url):
            try:
                req = urllib.request.Request(long_url, headers=HEADERS, method="HEAD")
                with urllib.request.urlopen(req, timeout=15) as r:
                    final = r.geturl()
                c = _coords_from_url(final)
                if c:
                    time.sleep(0.3)
                    return (c[0], c[1], "long-place-redirect")
                time.sleep(0.3)
            except Exception:
                pass
    return (None, None, None)

def main():
    cache_path = OUTPUT_DIR / f"_{RETAILER_SLUG}_builder.json"
    if cache_path.exists():
        print(f"Using cached Builder payload: {cache_path}")
        payload_text = cache_path.read_text(encoding="utf-8")
    else:
        print(f"Fetching Builder.io payload...")
        payload_text = http_get(BUILDER_URL)
        cache_path.write_text(payload_text, encoding="utf-8")

    builder = json.loads(payload_text)
    groups = builder["web-component-page"][0]["data"]["state"]["storeDataByLocation"]["results"]
    print(f"  groups: {len(groups)}")

    googl_cache = {}
    stores = []
    skipped_empty = 0
    scraped_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    for g in groups:
        gd = g.get("data") or {}
        select_country = gd.get("selectCountry")  # "United States" / "Canada" / "Global"
        location_label = gd.get("location") or "" # "Alabama" / "Alberta" / "Brazil"
        location_label = location_label.strip()

        # Determine country code + state field
        if select_country == "United States":
            country = "US"
            state_or_province = location_label
            country_label = "United States"
        elif select_country == "Canada":
            country = "CA"
            state_or_province = location_label
            country_label = "Canada"
        else:  # "Global" -> location_label is the country name
            country_label = location_label
            country = COUNTRY_TO_CODE.get(location_label)
            state_or_province = None

        for item in gd.get("storeList", []):
            store = ((item.get("store") or {}).get("value") or {}).get("data") or {}
            name = store.get("name")
            city = store.get("city")
            if not name and not city:
                skipped_empty += 1
                continue

            loc_html = store.get("location") or ""
            lat, lng, coord_source = extract_coords(loc_html, googl_cache)

            # Parse address from link text inside the location HTML
            link_text_match = re.search(r'<a[^>]*>(.+?)</a>', loc_html, re.DOTALL)
            link_text = link_text_match.group(1) if link_text_match else None
            addr_lines = parse_address_from_link_text(link_text) if link_text else None
            if country in ("US", "CA"):
                street, addr_city, addr_state, addr_zip = parse_us_address_lines(addr_lines or [])
            else:
                # International: keep the full address as a single string
                street = ", ".join(addr_lines) if addr_lines else None
                addr_city, addr_state, addr_zip = None, None, None

            # Prefer parsed address city/state if matches; otherwise keep group's
            final_city = addr_city or (strip_html(city) or "").split(",")[0].strip() or None
            final_state = addr_state or state_or_province
            final_postal = addr_zip

            store_id = f"{RETAILER_SLUG}-{slugify(country_label)}-{slugify(name or city or 'unknown')}"

            stores.append({
                "id":          store_id,
                "retailer":    RETAILER_NAME,
                "name":        strip_html(name),
                "address":     street,
                "city":        final_city,
                "state":       final_state,
                "country":     country,
                "postal_code": final_postal,
                "lat":         lat,
                "lng":         lng,
                "coord_is_estimated": False,        # set True below if we fall back to geocoding
                "phone":       (strip_html(store.get("phone")) or None),
                "hours":       strip_html(store.get("hours")),
                "url":         store.get("storeLink") or None,
                "year_opened": None,
                "scraped_at":  scraped_at,
                "raw": {
                    "_group_country": country_label,
                    "_group_state":   state_or_province,
                    "_coord_source":  coord_source,
                    **store,
                },
            })

    # --- Nominatim geocoding fallback for stores without coords from Google ---
    # We try a progression of queries from most to least specific. Mall/store names
    # often outperform messy street addresses (e.g. "The Dubai Mall, AE" beats a
    # multi-suite street that confuses the geocoder).
    geo_cache = {}
    geocoded_n = 0
    geocode_failed = []
    needs_geocode = [s for s in stores if s["lat"] is None]

    # Country code -> human country name (Nominatim takes either)
    code_to_name = {v: k for k, v in COUNTRY_TO_CODE.items()}

    def cleaned_street(addr):
        """Drop suite/unit/local/space tokens that confuse Nominatim."""
        if not addr: return None
        a = re.sub(r',?\s*(Suite|Ste\.?|Unit|Local|Space|Sp\.?|#)\s*[\w-]+', '', addr, flags=re.I)
        a = re.sub(r'\s+', ' ', a).strip(' ,')
        return a or None

    def build_queries(s):
        """Yield progressively-simpler geocode queries for a store."""
        name = s.get("name") or ""
        # Strip Coming Soon / similar marker so the geocoder works on the actual location name
        name = re.sub(r'\s*-?\s*Coming\s*Soon\s*$', '', name, flags=re.I).strip()
        city = s.get("city")
        state = s.get("state")
        postal = s.get("postal_code")
        country_code = s.get("country") or ""
        country_name = code_to_name.get(country_code, country_code)
        addr = s.get("address")

        # 1) Mall/store name + city + country  (often best for malls)
        if name and city:
            yield f"{name}, {city}, {country_name}"
        # 2) Cleaned street + city + state + postal + country
        cs = cleaned_street(addr)
        if cs and city:
            parts = [cs, city, state, postal, country_name]
            yield ", ".join(p for p in parts if p)
        # 3) Cleaned street + city + country (no state/zip)
        if cs and city and country_name:
            yield f"{cs}, {city}, {country_name}"
        # 4) Just city + country  (last-resort coarse pin)
        if city and country_name:
            yield f"{city}, {country_name}"

    if needs_geocode:
        print(f"\nGeocoding {len(needs_geocode)} stores via OSM Nominatim "
              f"(progressive fallback queries, 1 req/sec)...")
    for s in needs_geocode:
        coords = None
        used_query = None
        for query in build_queries(s):
            coords = nominatim_geocode(query, geo_cache)
            if coords:
                used_query = query
                break
        if coords:
            s["lat"], s["lng"] = coords
            s["coord_is_estimated"] = True
            s["raw"]["_coord_source"] = "nominatim"
            s["raw"]["_geocode_query"] = used_query
            geocoded_n += 1
        else:
            geocode_failed.append((s["name"], list(build_queries(s))[0] if list(build_queries(s)) else None))

    # Deduplicate by id
    seen = {}
    for s in stores:
        seen[s["id"]] = s
    if len(seen) != len(stores):
        print(f"  collapsed {len(stores) - len(seen)} duplicate IDs")
    stores = list(seen.values())

    output = {
        "retailer":    RETAILER_NAME,
        "slug":        RETAILER_SLUG,
        "source_url":  SOURCE_URL,
        "platform":    PLATFORM,
        "scope":       SCOPE,
        "scraped_at":  scraped_at,
        "store_count": len(stores),
        "geocoded_count": geocoded_n,    # how many stores have coord_is_estimated=true
        "geocoded_note": ("Alo's CMS does not store coordinates for some entries (newer "
                          "international markets, US mall locations, 'Coming Soon' stores). "
                          "We extract coords from Google Maps URLs in the source where "
                          "available; otherwise we geocode the full address via OSM Nominatim. "
                          "Geocoded stores are flagged with coord_is_estimated=true and "
                          "raw._coord_source='nominatim'. Geocode accuracy is typically "
                          "~50m for US/CA addresses with postal codes, looser for "
                          "international entries with sparser source data."),
        "stores":      stores,
    }

    out_path = OUTPUT_DIR / f"{RETAILER_SLUG}.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSaved {len(stores)} stores -> {out_path}")
    print(f"  skipped empty templates: {skipped_empty}")
    print(f"  geocoded via Nominatim:   {geocoded_n}")
    if geocode_failed:
        print(f"  geocode FAILED for {len(geocode_failed)}: ")
        for n, q in geocode_failed: print(f"    {n!r} <- {q!r}")

    # Validation
    from collections import Counter
    no_coord = [s for s in stores if s["lat"] is None or s["lng"] is None]
    countries = Counter(s["country"] for s in stores)
    sources = Counter(s["raw"].get("_coord_source") for s in stores)
    print("\n--- VALIDATION ---")
    print(f"Stores with coordinates: {len(stores) - len(no_coord)} / {len(stores)}")
    if no_coord:
        print(f"  Missing coords: {len(no_coord)}")
        for s in no_coord[:8]:
            print(f"    [{s['country']}/{s['state']}] {s['name']!r} ({s['city']!r})")
    print(f"Countries: {dict(countries)}")
    print(f"Coord source: {dict(sources)}")

    print("\n--- SAMPLE ---")
    for s in (stores[0], stores[len(stores)//2], stores[-1]):
        print(f"  {s['name']} ({s['country']}/{s['state']}) - {s['address']!r} {s['city']!r} {s['postal_code']!r}")
        print(f"    lat/lng: {s['lat']}, {s['lng']}  source: {s['raw'].get('_coord_source')}")


if __name__ == "__main__":
    main()
