"""Sweep Wayback Machine snapshots of shop.lululemon.com/stores/all-lululemon-stores
and assign each NA store an upper-bound year_opened based on the earliest snapshot
containing its name/slug.

The Lulu page is server-rendered (every store name is in the static HTML), so
unlike Alo's JS-rendered page, Wayback's snapshots actually contain usable data.

Output: writes year_opened to each NA store in data/lululemon.json with status
'wayback-stores-directory-upper-bound' for matched stores.
"""
import json, pathlib, re, time, urllib.request, urllib.parse, gzip
from collections import Counter, defaultdict

DATA = pathlib.Path(r"G:\My Drive\Programs\store-map\data\lululemon.json")
CACHE_DIR = pathlib.Path(r"G:\My Drive\Programs\store-map\data\_lulu_wayback_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "store-map-scraper/1.0 (private use; ldm@oddity.com)"}
THROTTLE = 1.5

def http_text(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    if raw[:2] == b'\x1f\x8b':
        try: raw = gzip.decompress(raw)
        except Exception: pass
    return raw.decode("utf-8", errors="replace")

def cdx_snapshots(url):
    api = ("http://web.archive.org/cdx/search/cdx?"
           f"url={urllib.parse.quote(url)}&output=json&filter=statuscode:200&filter=mimetype:text/html")
    data = json.loads(http_text(api, timeout=30))
    if not data or len(data) < 2: return []
    return [(row[1], row[2]) for row in data[1:]]

def fetch_archived(timestamp, url):
    cache = CACHE_DIR / f"{timestamp}.html"
    if cache.exists():
        return cache.read_text(encoding="utf-8", errors="replace")
    snap_url = f"http://web.archive.org/web/{timestamp}id_/{url}"
    try:
        text = http_text(snap_url)
    except Exception as e:
        print(f"  fetch error {timestamp}: {e}")
        return None
    cache.write_text(text, encoding="utf-8")
    time.sleep(THROTTLE)
    return text

def main():
    file = json.loads(DATA.read_text(encoding="utf-8"))
    stores = file["stores"]
    na = [s for s in stores if s.get("country") in ("US","CA") and not s.get("coord_is_estimated")]
    print(f"NA stores: {len(na)}")

    target_url = "shop.lululemon.com/stores/all-lululemon-stores"
    snaps = cdx_snapshots(target_url)
    print(f"CDX snapshots: {len(snaps)}")

    # Subsample: keep one per quarter, plus the 2 from 2025
    by_q = {}
    for ts, url in snaps:
        if len(ts) < 6: continue
        try: y, m = int(ts[:4]), int(ts[4:6])
        except ValueError: continue
        q = (y, (m-1)//3)
        if q not in by_q: by_q[q] = (ts, url)
    snaps_q = sorted(by_q.values(), key=lambda x: x[0])
    print(f"Quarterly snapshots to fetch: {len(snaps_q)}")

    # For each snapshot, fetch + extract Lulu store names from the HTML
    snapshot_data = []  # list of (year, ts, set_of_stores_seen)
    for ts, url in snaps_q:
        html = fetch_archived(ts, url)
        if not html: continue
        # Lulu's all-stores page renders each store's name in <h2 class="store-name"> or similar.
        # The Next.js __NEXT_DATA__ payload also contains the full list — easier to parse.
        # Try to extract __NEXT_DATA__ first
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)
        names_in_snap = set()
        slugs_in_snap = set()
        if m:
            try:
                nd = json.loads(m.group(1))
                # Walk to storeLocatorList
                def walk(o, key="storeLocatorList"):
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
                lst = walk(nd) or []
                for s in lst:
                    if isinstance(s, dict):
                        if s.get("name"): names_in_snap.add(s["name"].lower().strip())
                        if s.get("slug"): slugs_in_snap.add(s["slug"].lower())
                        if s.get("id"):   names_in_snap.add(f"id:{s['id']}")
            except Exception as e:
                print(f"  parse error in {ts}: {e}")
        # Fallback: regex over raw HTML
        if not names_in_snap:
            for sn in re.findall(r'"name"\s*:\s*"([^"]+)"', html):
                names_in_snap.add(sn.lower().strip())
        snapshot_data.append((int(ts[:4]), ts, names_in_snap, slugs_in_snap))
        print(f"  {ts} ({len(html):,} bytes): {len(names_in_snap)} names, {len(slugs_in_snap)} slugs")

    print(f"\n=== Matching stores against snapshots ===")
    # Sort snapshots oldest to newest
    snapshot_data.sort(key=lambda x: x[1])
    matched = 0
    not_in_any = []

    for s in na:
        name = (s.get("name") or "").lower().strip()
        slug = (s.get("raw") or {}).get("slug","").lower()
        sid = (s.get("raw") or {}).get("id","")
        first_year = None; first_ts = None
        for year, ts, names, slugs in snapshot_data:
            if (name and name in names) or (slug and slug in slugs) or (sid and f"id:{sid}" in names):
                first_year = year; first_ts = ts
                break
        if first_year:
            s["year_opened"] = first_year
            s.setdefault("raw", {})
            s["raw"]["_year_opened_source"] = "wayback-stores-directory-upper-bound"
            s["raw"]["_year_opened_snapshot"] = first_ts
            s["raw"]["_year_opened_signals"] = {"wayback_earliest_year": first_year, "wayback_snapshot": first_ts}
            matched += 1
        else:
            s["year_opened"] = None
            not_in_any.append(s)

    print(f"\nMatched: {matched}/{len(na)}")
    print(f"Not found in any snapshot: {len(not_in_any)}")
    print(f"\nHistogram:")
    hist = Counter(s.get("year_opened") for s in na if s.get("year_opened"))
    for y, n in sorted(hist.items()):
        print(f"  ≤{y}: {n}")

    # Save
    file["stores"] = stores  # NA modified, intl untouched (no year_opened set)
    DATA.write_text(json.dumps(file, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved -> {DATA}")

    if not_in_any:
        print(f"\nFirst 15 stores not in any Wayback snapshot:")
        for s in not_in_any[:15]:
            print(f"  {s['country']}/{s.get('state')}: {s['name']} (id={s['raw'].get('id')})")

if __name__ == "__main__":
    main()
