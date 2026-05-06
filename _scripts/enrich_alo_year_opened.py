"""Fill year_opened for each store in data/alo-yoga.json using the Wayback Machine.

Strategy (cheap, no paid API):

  Phase 2 first (per-flagship URL): for each store with a `url` (storeLink) — i.e.,
  the ~26 dedicated /pages/<slug>-store pages — ask Wayback's availability API for
  the earliest snapshot of that exact URL. The snapshot timestamp's year ≈ the year
  the page was published ≈ the year the store opened.

  Phase 1 (sweep): CDX-list every snapshot of aloyoga.com/pages/stores and
  /pages/find-a-store. Subsample roughly quarterly. Fetch each, strip to text, and
  for each store name find the earliest snapshot whose text contains it.

  Combine: prefer Phase 2 (per-store) over Phase 1 (sweep) when both have data.

Output: data/alo-yoga.json gets `year_opened` (int or null) on each store and
`raw._year_opened_source` ("wayback-store-page" | "wayback-stores-directory" |
null). Top-level adds `year_opened_coverage` and `year_opened_histogram`.
"""
import json, pathlib, re, time, urllib.request, urllib.parse, datetime, gzip, io
from collections import defaultdict, Counter

DATA_PATH = pathlib.Path(r"G:\My Drive\Programs\store-map\data\alo-yoga.json")
CACHE_DIR = pathlib.Path(r"G:\My Drive\Programs\store-map\data\_alo_wayback_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "store-map-scraper/1.0 (private use; ldm@oddity.com)"}
THROTTLE = 1.5  # seconds between Wayback hits — was 0.6, got 429-rate-limited


# ────────────────────────────────────────────────────────────────────────────
# Wayback API helpers
# ────────────────────────────────────────────────────────────────────────────
def http_json(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def http_text(url, timeout=60):
    """Fetch URL and decode as text. Auto-decompresses gzip content (Wayback's
    id_/ endpoint serves the original archived bytes, including original
    Content-Encoding — many snapshots are gzip-encoded under the hood)."""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    # Detect gzip magic bytes
    if raw[:2] == b'\x1f\x8b':
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")

def cdx_snapshots(url):
    """Return [(timestamp, original_url), ...] for every snapshot Wayback has."""
    api = ("http://web.archive.org/cdx/search/cdx?"
           f"url={urllib.parse.quote(url)}&output=json&filter=statuscode:200&filter=mimetype:text/html")
    try:
        data = http_json(api)
    except Exception as e:
        print(f"  CDX error for {url}: {e}")
        return []
    if not data or len(data) < 2: return []
    # First row is the column header
    rows = data[1:]
    return [(row[1], row[2]) for row in rows]

def earliest_snapshot(url):
    """Get the earliest snapshot timestamp for `url` via CDX (less rate-limited
    than the availability API, which 429s aggressively). Returns YYYYMMDDhhmmss or None."""
    snaps = cdx_snapshots(url)
    if not snaps: return None
    return min(snaps, key=lambda x: x[0])[0]

def fetch_archived(timestamp, url):
    """Fetch the raw archived content for a specific snapshot. Cached to disk."""
    cache = CACHE_DIR / f"{timestamp}_{re.sub(r'[^a-z0-9]+', '_', url.lower())[:50]}.html"
    if cache.exists():
        return cache.read_text(encoding="utf-8", errors="replace")
    snap_url = f"http://web.archive.org/web/{timestamp}id_/{url}"
    try:
        text = http_text(snap_url)
    except Exception as e:
        print(f"  archived-fetch error for {timestamp}: {e}")
        return None
    cache.write_text(text, encoding="utf-8")
    time.sleep(THROTTLE)
    return text

def subsample_quarterly(snaps):
    """Keep one snapshot per (year, quarter)."""
    by_q = {}
    for ts, url in snaps:
        if len(ts) < 6: continue
        try:
            year = int(ts[:4]); month = int(ts[4:6])
        except ValueError:
            continue
        q = (year, (month - 1) // 3)
        if q not in by_q:
            by_q[q] = (ts, url)
    return sorted(by_q.values(), key=lambda x: x[0])


# ────────────────────────────────────────────────────────────────────────────
# Text extraction & matching
# ────────────────────────────────────────────────────────────────────────────
def normalize(s):
    """Lowercase, strip HTML tags, collapse whitespace, remove punctuation noise."""
    if not s: return ""
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&[a-z]+;', ' ', s, flags=re.I)
    s = re.sub(r'[^\w\s\-]', ' ', s.lower())
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def needle_for(store):
    """Build a search needle for a store. Prefer URL slug if available, else the name."""
    needles = []
    url = store.get("url")
    if url:
        # Extract /pages/<slug>-store from URL
        m = re.search(r'/pages/([a-z0-9-]+)', url)
        if m:
            needles.append(("slug", m.group(1)))
    name = store.get("name") or ""
    name_norm = normalize(name)
    if name_norm and len(name_norm) >= 4:
        # Strip common suffixes/markers that change over time ("Coming Soon", parens)
        name_clean = re.sub(r'\s*-\s*coming soon$', '', name_norm).strip()
        name_clean = re.sub(r'\s*\(coming soon\)\s*$', '', name_clean).strip()
        if name_clean and len(name_clean) >= 4:
            needles.append(("name", name_clean))
    return needles


def text_contains(haystack_norm, needle):
    return needle in haystack_norm


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────
def main():
    print(f"Loading {DATA_PATH.name} ...")
    file = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    stores = file["stores"]
    print(f"  {len(stores)} stores")

    flagships = [s for s in stores if s.get("url")]
    no_url = [s for s in stores if not s.get("url")]
    print(f"  {len(flagships)} flagships with URLs, {len(no_url)} without")

    # ── Phase 2: per-flagship URL availability ──
    print("\n=== Phase 2: per-flagship-URL earliest snapshot ===")
    flagship_year = {}  # store_id -> (year, source_ts)
    for s in flagships:
        url = s["url"]
        ts = earliest_snapshot(url)
        if ts:
            year = int(ts[:4])
            flagship_year[s["id"]] = (year, ts)
            print(f"  {s['id']:<32} -> {year}  ({s.get('name')!r})")
        else:
            print(f"  {s['id']:<32} -> no snapshot  ({s.get('name')!r})")
        time.sleep(THROTTLE)

    # ── Phase 1: sweep of /pages/stores and /pages/find-a-store ──
    print("\n=== Phase 1: CDX sweep of stores directory pages ===")
    sweep_urls = [
        "aloyoga.com/pages/stores",
        "aloyoga.com/pages/find-a-store",
        "www.aloyoga.com/pages/stores",
        "www.aloyoga.com/pages/find-a-store",
    ]
    all_snaps = []
    for u in sweep_urls:
        snaps = cdx_snapshots(u)
        print(f"  {u}: {len(snaps)} total snapshots")
        all_snaps.extend(snaps)
        time.sleep(THROTTLE)

    snaps_by_q = subsample_quarterly(all_snaps)
    print(f"  subsampled to {len(snaps_by_q)} snapshots (one per quarter)")

    # For each snapshot, fetch & build the normalized-text corpus
    snapshot_texts = []  # list of (timestamp, normalized_text)
    for ts, url in snaps_by_q:
        text = fetch_archived(ts, url)
        if not text: continue
        norm = normalize(text)
        snapshot_texts.append((ts, norm))
        print(f"    {ts} {url}: {len(text):>6} bytes -> {len(norm):>6} normalized chars")

    # For each store, find earliest snapshot containing any of its needles
    print("\n=== Matching stores against snapshots ===")
    sweep_year = {}  # store_id -> (year, ts)
    for s in stores:
        needles = needle_for(s)
        if not needles: continue
        # iterate snapshots in time order, find earliest that contains any needle
        for ts, norm in snapshot_texts:
            hit = False
            for kind, needle in needles:
                if needle in norm:
                    hit = True
                    break
            if hit:
                year = int(ts[:4])
                sweep_year[s["id"]] = (year, ts)
                break

    print(f"\n  matched in sweep: {len(sweep_year)} stores")

    # ── Combine ──
    print("\n=== Combine + write ===")
    n_phase2 = 0; n_phase1 = 0; n_none = 0
    for s in stores:
        sid = s["id"]
        # Prefer Phase 2 (per-store-page) when available
        if sid in flagship_year:
            year, ts = flagship_year[sid]
            s["year_opened"] = year
            s.setdefault("raw", {})["_year_opened_source"] = "wayback-store-page"
            s["raw"]["_year_opened_snapshot"] = ts
            n_phase2 += 1
        elif sid in sweep_year:
            year, ts = sweep_year[sid]
            s["year_opened"] = year
            s.setdefault("raw", {})["_year_opened_source"] = "wayback-stores-directory"
            s["raw"]["_year_opened_snapshot"] = ts
            n_phase1 += 1
        else:
            s["year_opened"] = s.get("year_opened")  # leave as-is (probably None)
            s.setdefault("raw", {})["_year_opened_source"] = None
            n_none += 1

    # Coverage + histogram
    known = sum(1 for s in stores if s.get("year_opened"))
    unknown = len(stores) - known
    histogram = dict(Counter(s.get("year_opened") for s in stores if s.get("year_opened")))
    histogram = dict(sorted(histogram.items()))

    file["stores"] = stores
    file["year_opened_coverage"] = {"known": known, "unknown": unknown}
    file["year_opened_histogram"] = histogram

    DATA_PATH.write_text(json.dumps(file, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSaved.")
    print(f"  Phase 2 (per-flagship-URL): {n_phase2}")
    print(f"  Phase 1 (sweep):            {n_phase1}")
    print(f"  no match:                   {n_none}")
    print(f"  total known: {known} / {len(stores)} ({100*known/len(stores):.0f}%)")
    print(f"\n  Histogram (year_opened):")
    for y, n in histogram.items():
        bar = "#" * n
        print(f"    {y}: {n:3} {bar}")

    # List the gaps for Lindsay
    gaps = [s for s in stores if not s.get("year_opened")]
    print(f"\n=== {len(gaps)} stores still missing year_opened ===")
    by_country = defaultdict(list)
    for s in gaps:
        by_country[s.get("country") or "?"].append(s)
    for cc, slist in sorted(by_country.items(), key=lambda kv: -len(kv[1])):
        print(f"  {cc}: {len(slist)} stores")
        for s in slist[:5]:
            print(f"    {s.get('name')!r:<50}  {s.get('city')!r}")
        if len(slist) > 5:
            print(f"    ... +{len(slist)-5} more")


if __name__ == "__main__":
    main()
