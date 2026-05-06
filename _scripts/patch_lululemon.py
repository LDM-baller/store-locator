"""Surgical patch for data/lululemon.json. Replaces a full re-scrape.

Steps it performs (in order):
  1. Backfill `store_type` and `status` on every store currently in the file.
       - NA stores: derive from raw.storeStatus / raw.storeType.
       - International stores: derive from store name (auto-classify).
  2. Drop stores classified as 'closed'.
  3. For each entry in manual_overrides.json:
       - If the store exists in the file: FIX it (replace coords if override has
         a geocode_query; stamp store_type/status from override).
       - If the store is missing from the file: ADD it. Pull name/phone/hours from
         the cached SSR HTML at data/_lulu_intl_cache/, geocode the override's
         geocode_query, append.
  4. Recompute top-level store_count, geocoded_count, store_type_counts,
     status_counts. Save back.

Network: ~8 Nominatim calls, ~10 seconds total.
"""
import json, pathlib, re, time, urllib.request, urllib.parse
from collections import Counter

DATA = pathlib.Path(r"G:\My Drive\Programs\store-map\data\lululemon.json")
OVERRIDES = pathlib.Path(r"G:\My Drive\Programs\store-map\manual_overrides.json")
CACHE_DIR = pathlib.Path(r"G:\My Drive\Programs\store-map\data\_lulu_intl_cache")

VALID_STORE_TYPES = {"regular","popup","outlet","flagship","concession",
                     "showroom","experiential","other"}
VALID_STATUSES = {"active","coming_soon","closed"}
DEPT_STORE_NAMES = ("fenwick","selfridges","harrods","daimaru","brown thomas")


def classify_from_name(name):
    if not name: return ("regular","active")
    nl = name.lower()
    if "closed" in nl: return ("regular","closed")
    status = "coming_soon" if ("coming soon" in nl or "(coming" in nl) else "active"
    if "pop-up" in nl or "popup" in nl: return ("popup", status)
    if "factory outlet" in nl or "outlet" in nl: return ("outlet", status)
    for ds in DEPT_STORE_NAMES:
        if ds in nl: return ("concession", status)
    return ("regular", status)


def backfill_classification(s):
    """Add store_type and status fields from existing data."""
    raw = s.get("raw") or {}
    rs = raw.get("storeStatus")
    rt = raw.get("storeType")
    if rs or rt:  # NA store with original Lulu fields
        if rs == "active_soon": s["status"] = "coming_soon"
        elif rs in VALID_STATUSES: s["status"] = rs
        else: s["status"] = "active"
        s["store_type"] = rt if rt in VALID_STORE_TYPES else "regular"
    else:  # International — derive from name
        st, status = classify_from_name(s.get("name") or "")
        s["store_type"] = st
        s["status"] = status


def find_in_cache(store_id):
    """Find a Demandware store-card in the cached SSR responses. Returns (name, phone, hours_text)."""
    needle = f'data-store-id="{store_id}"'
    for cf in CACHE_DIR.glob("*.html"):
        try:
            html = cf.read_text(encoding="utf-8")
        except Exception:
            continue
        if needle not in html:
            continue
        m = re.search(rf'<div class="store-details-card" data-store-id="{store_id}">', html)
        if not m: continue
        start = m.start()
        nxt = html.find('<div class="store-details-card" data-store-id=', m.end())
        end = nxt if nxt > 0 else start + 5000
        card = html[start:end]
        nm = re.search(r'<span class="store-name">([^<]+)</span>', card)
        name = nm.group(1).strip() if nm else None
        if name: name = re.sub(r'^\d+\.\s*', '', name)
        # html-unescape a few common entities
        for k, v in {"&amp;":"&","&Eacute;":"É","&eacute;":"é","&nbsp;":" "}.items():
            if name: name = name.replace(k, v)
        ph = re.search(r'<a [^>]*href="tel:([^"]+)"', card)
        phone = ph.group(1).strip() if ph else None
        hb = re.search(r'class="store-hours"\s*>(.+?)</div>\s*</div>\s*<', card, re.DOTALL)
        hours = None
        if hb:
            ht = re.findall(r'((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[^<]*?\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}|Closed)', hb.group(1))
            ht = [re.sub(r'\s+',' ',l).strip() for l in ht]
            hours = "; ".join(ht) or None
        return name, phone, hours
    return None, None, None


def nominatim(query):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"format":"json","limit":1,"addressdetails":1,"q":query}
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "store-map-scraper/1.0 (private use; contact ldm@oddity.com)",
        "Accept-Language": "en",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"    nominatim error for {query!r}: {e}")
        return None
    finally:
        time.sleep(1.05)
    if not data: return None
    d = data[0]
    addr = d.get("address") or {}
    return {
        "lat": float(d["lat"]), "lng": float(d["lon"]),
        "country_code": (addr.get("country_code") or "").upper() or None,
        "country": addr.get("country"),
        "city": addr.get("city") or addr.get("town") or addr.get("village") or addr.get("suburb"),
        "state": addr.get("state") or addr.get("region"),
        "postal_code": addr.get("postcode"),
        "display_name": d.get("display_name"),
    }


def main():
    print(f"Loading {DATA.name} ...")
    f = json.loads(DATA.read_text(encoding="utf-8"))
    stores = f["stores"]
    print(f"  {len(stores)} stores currently")

    overrides_raw = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    overrides = {k: v for k, v in overrides_raw.items() if not k.startswith("_")}
    print(f"  {len(overrides)} overrides loaded")

    # ── 1. Backfill store_type + status ──
    for s in stores:
        backfill_classification(s)

    # ── 2. Drop closed ──
    pre = len(stores)
    stores = [s for s in stores if s.get("status") != "closed"]
    if pre != len(stores):
        print(f"  dropped {pre - len(stores)} stores classified as closed")

    # ── 3. Apply overrides ──
    fixed = 0; added = 0
    skipped = []
    by_id = {s["id"]: s for s in stores}

    for full_id, ov in overrides.items():
        sid = full_id.replace("lululemon-", "")
        # Determine coords source for this override
        coords = None; src = None
        if "geocode_query" in ov and ov["geocode_query"]:
            gr = nominatim(ov["geocode_query"])
            if gr:
                coords = gr; src = "nominatim"
        if not coords and "lat" in ov and "lng" in ov:
            coords = {"lat": float(ov["lat"]), "lng": float(ov["lng"]),
                      "country_code": (ov.get("country") or "").upper() or None,
                      "city": ov.get("city"), "state": ov.get("state"),
                      "postal_code": ov.get("postal_code"),
                      "display_name": "(manual override coords)"}
            src = "manual_override"
        if not coords:
            skipped.append((full_id, ov.get("_note","no geocode_query or lat/lng")))
            continue

        existing = by_id.get(full_id)
        if existing:
            # FIX
            existing["lat"] = coords["lat"]; existing["lng"] = coords["lng"]
            for k in ("city","state","postal_code"):
                if coords.get(k) is not None:
                    existing[k] = coords[k]
            cc = coords.get("country_code")
            if cc: existing["country"] = cc
            if "store_type" in ov and ov["store_type"] in VALID_STORE_TYPES:
                existing["store_type"] = ov["store_type"]
            if "status" in ov and ov["status"] in VALID_STATUSES:
                existing["status"] = ov["status"]
            existing["coord_is_estimated"] = True
            existing.setdefault("raw", {})
            existing["raw"]["_coord_source"] = src
            existing["raw"]["_geocode_query"] = ov.get("geocode_query")
            existing["raw"]["_nominatim_display_name"] = coords.get("display_name")
            existing["raw"]["_manual_override"] = ov
            print(f"  FIX  {full_id} {existing.get('name')!r} -> ({coords['lat']:.4f}, {coords['lng']:.4f}) {existing['country']}")
            fixed += 1
        else:
            # ADD: pull name/phone/hours from cached SSR
            name, phone, hours = find_in_cache(sid)
            if not name:
                skipped.append((full_id, "Demandware ID not found in SSR cache"))
                continue
            auto_st, auto_status = classify_from_name(name)
            store_type = ov.get("store_type", auto_st)
            if store_type not in VALID_STORE_TYPES: store_type = auto_st
            status = ov.get("status", auto_status)
            if status not in VALID_STATUSES: status = auto_status
            new_store = {
                "id":          full_id,
                "retailer":    "Lululemon",
                "name":        name,
                "address":     None,
                "city":        coords.get("city"),
                "state":       coords.get("state"),
                "country":     coords.get("country_code"),
                "postal_code": coords.get("postal_code"),
                "lat":         coords["lat"],
                "lng":         coords["lng"],
                "coord_is_estimated": True,
                "store_type":  store_type,
                "status":      status,
                "phone":       phone,
                "hours":       hours,
                "url":         None,
                "year_opened": None,
                "scraped_at":  f.get("scraped_at"),
                "raw": {
                    "_coord_source": src,
                    "_geocode_query": ov.get("geocode_query"),
                    "_nominatim_display_name": coords.get("display_name"),
                    "_demandware_store_id": sid,
                    "_auto_classification": {"store_type": auto_st, "status": auto_status},
                    "_manual_override": ov,
                },
            }
            stores.append(new_store)
            print(f"  ADD  {full_id} {name!r} ({store_type}/{status}) -> ({coords['lat']:.4f}, {coords['lng']:.4f}) {new_store['country']}")
            added += 1

    if skipped:
        print(f"\n  SKIPPED {len(skipped)}:")
        for fid, reason in skipped:
            print(f"    {fid}: {reason}")

    # ── 4. Recompute top-level summaries ──
    type_counts = dict(Counter(s.get("store_type","regular") for s in stores))
    status_counts = dict(Counter(s.get("status","active") for s in stores))
    geocoded_count = sum(1 for s in stores if s.get("coord_is_estimated"))
    f["stores"] = stores
    f["store_count"] = len(stores)
    f["geocoded_count"] = geocoded_count
    f["store_type_counts"] = type_counts
    f["status_counts"] = status_counts

    DATA.write_text(json.dumps(f, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(stores)} stores to {DATA}")
    print(f"  fixed:    {fixed} (existing entries with bad coords)")
    print(f"  added:    {added} (entries that failed in last full run)")
    print(f"  skipped:  {len(skipped)}")
    print(f"  store_type: {type_counts}")
    print(f"  status:     {status_counts}")
    print(f"  geocoded:   {geocoded_count} (all intl)")


if __name__ == "__main__":
    main()
