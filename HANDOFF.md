# Store Time Machine — Handoff

Updated: 2026-05-07

## Resume in one paragraph

Live web app at **https://ldm-baller.github.io/store-locator/** (map) and **/dashboard.html** (analytics). Source repo: **https://github.com/LDM-baller/store-locator**. Local working dir: `G:\My Drive\Programs\store-map\`. Loads 3 retailer JSONs (Lulu 972, Alo 225, Gucci 598 = **1,795 stores total**) onto a temporal Leaflet map with year-slider scrubbing 2000→2026, plus a 6-card analytics dashboard. Git Credential Manager is authenticated, so Claude can push directly from Bash without re-prompting.

---

## File structure

### In the public repo (deployed by GitHub Pages)

```
index.html          map page shell
app.js              map viewer logic (Leaflet + smart chips + manifest/detail)
styles.css          shared styles (light theme, mobile-first)
dashboard.html      analytics page shell
dashboard.js        analytics + hand-rolled SVG charts
dashboard.css       dashboard-specific styles
data/
  lululemon.json    972 stores
  alo-yoga.json     225 stores
  gucci.json        598 stores
README.md           run instructions
.gitignore          ignores _scripts/_inline_*, data/_*, *.bak, etc.
```

### Local-only (gitignored, lives only on G:\)

```
_scripts/                       data engineering
  scrape_lululemon.py           original NA Yext scrape
  scrape_lululemon_intl.py      international Demandware scrape
  scrape_alo-yoga.py            Builder.io scrape
  fetch_lulu_10ks.py            SEC EDGAR 10-K puller
  estimate_lulu_year_opened.py  rank-bucket year estimator
  enrich_alo_year_opened.py     Alo year enrichment
  add_lulu_china.py             China store loader
  add_lulu_mena.py              MENA franchise loader
  add_lulu_mexico.py            Mexico loader
  add_lulu_mexico_more.py       Cancun/Merida add-on
  apply_alo_year_corrections.py corrections from web search
  patch_lululemon.py            ad-hoc patches
  probe_lulu_intl.py            geocoding probes
  probe_lulu_mx.py              Mexico geocoding probes
  tag_alo_year_validation.py    validation-tag stamper
  enrich_lulu_year_opened.py    Lulu year_opened pipeline
  _inline_add_2026_05_06.py     KR/SG/MY/ES/NO additions (one-shot)
  _backfill_lulu_china_years.py China year backfill (initial pass)
  _backfill_lulu_popup_years.py Popup year defaulting
  _validate_lulu_popups.py      Popup status check via Lulu locator
  _scrape_gucci.py              Gucci normalizer
  _translate_lulu_cn_names.py   Chinese -> English translator
  _repatch_lulu_china_years.py  PR-anchored China year revision

data/
  _lulu_intl_cache/             Demandware HTML cache (~25 files)
  _lulu_10k_cache/              SEC 10-K HTML/PDF cache
  _alo_wayback_cache/           Wayback snapshots for Alo dating
  _lulu_10k_store_counts.json   parsed 10-K country/year matrix
  _lulu_popup_validation.json   71-popup status check output
  _gucci_raw.json               raw Gucci API response (1.6MB)
  _gucci_cookies.txt            Akamai session cookies
  *.bak                         pre-modification backups
  _lulu_sitemap.xml             cached sitemap

manual_overrides.json           Alo year corrections (read by enrich script)
manual_overrides_lulu.json      Lulu year + country corrections
NEXT_STEPS.md, SPEC.md, etc.    older planning docs (superseded by this file)
```

---

## Data schema (per-store)

```json
{
  "id": "lululemon-cn-北京三里屯",
  "retailer": "Lululemon",
  "name": "Beijing Sanlitun",
  "address": "...",
  "city": "Beijing",
  "state": null,
  "country": "CN",
  "postal_code": null,
  "lat": 39.9333, "lng": 116.4536,
  "coord_is_estimated": true,
  "store_type": "flagship",
  "status": "active",
  "phone": null,
  "hours": null,
  "url": null,
  "year_opened": 2016,
  "year_opened_validation": "china-pr-confirmed",
  "scraped_at": "2026-05-06T...",
  "raw": {
    "_year_opened_method": "PR Dec 2016: opened with first 3 mainland stores",
    "name_zh": "北京三里屯",
    ...
  }
}
```

### `year_opened_validation` tags (sorted by confidence)

| Tag | Confidence | Source |
|---|---|---|
| `web-search-confirmed` | High | Press release / Wayback / store URL |
| `china-pr-confirmed` | High | Lulu official PRs |
| `press-confirmed` | High | News article cited in `raw._data_source` |
| `wayback-store-page` | High | Internet Archive snapshot |
| `web-search-corrected` | High | Manual web-search correction |
| `manual-with-country-debut-context` | Medium | Country debut + flagship rank |
| `10k-fiscal-year-bucket` | Medium | SEC 10-K country count |
| `china-pr-anchored-fy-bucket-estimated` | Medium | China growth curve + tier rank |
| `country-debut-interpolated` | Low-medium | Country first-store year |
| `china-fy-bucket-estimated` | Low | Pre-PR-anchor China estimate |
| `popup-active-estimated-default-2025` | Low | Popup default |
| `popup-coming-soon-estimated-2026` | Low | Coming-soon default |
| `builder-createddate-only` | Low | Builder.io createdDate (Alo) |
| `pending` | None | Not yet estimated |

The viewer flags estimated values with an `est.` indicator in the detail panel.

---

## Operational runbook

### Local development server

```powershell
cd "G:\My Drive\Programs\store-map"
python -m http.server 8765
# open http://localhost:8765/
```

(Browsers block `fetch` on `file://`, so you need a server.)

### Push changes to GitHub Pages

GCM is authenticated, so any push works:
```bash
git add <files>
git -c user.name="Lindsay Drucker Mann" -c user.email="ldm@oddity.com" commit -m "..."
git push
```

Pages redeploy takes ~30–60s. Bump the `?v=N` cache-busting query string in `index.html` and/or `dashboard.html` whenever `app.js`, `dashboard.js`, or `styles.css` changes — otherwise mobile browsers serve stale JS.

### Add a new retailer

1. Build a normalized JSON at `data/<slug>.json` matching the schema above.
2. Append to the `RETAILERS` array in `app.js` AND `dashboard.js`:
   ```js
   { slug: 'newbrand', name: 'New Brand', file: 'data/newbrand.json', color: '#hex' }
   ```
3. Bump `?v=N` and push.

### Add manual corrections

For Lulu: edit `manual_overrides_lulu.json` and re-run `_scripts/enrich_lulu_year_opened.py`. The override format keys by store ID with `year_opened` and optional `country` fixes.

For Alo: edit `manual_overrides.json` similarly and run `_scripts/apply_alo_year_corrections.py`.

---

## Key learnings (the actual hard-won stuff)

### Bot protection: every luxury / DTC site is behind Akamai or Cloudflare

- **Symptom**: simple `urllib`/`requests`/`curl` calls return 403 or hang on SSL renegotiation.
- **Fix**: use curl with the **full Chrome header set** (User-Agent, Accept, Accept-Language, Sec-Fetch-Dest, Sec-Fetch-Mode, Sec-Fetch-Site, Sec-Fetch-User, Upgrade-Insecure-Requests, --compressed). For Gucci specifically, do a **warmup fetch** of the public store page first to seed cookies, then hit the API with `-b cookiejar`.
- **Don't hammer**: Akamai tracks request patterns; ~5 requests in quick succession from the same IP triggers a temporary block. Add `time.sleep(0.4)` between requests.

### Platform fingerprints (use when scraping a new retailer)

| Platform | Tells | Endpoint shape |
|---|---|---|
| Yext | `cdn.yextapis.com`, `experienceKey`, `apiKey` in source | `cdn.yextapis.com/v2/accounts/.../search/vertical/query?...&offset=N` |
| Builder.io | `cdn.builder.io` in source, `?model=...&apiKey=...` URLs | `cdn.builder.io/api/v3/content/<model>?apiKey=...` |
| Next.js SSR | `<script id="__NEXT_DATA__">{...}</script>` | parse the JSON inside; full state often pre-rendered |
| Salesforce Demandware | country sub-sites (`lululemon.de`), Cloudflare-protected XHRs | server-side render the locator page (`?lat=&long=&radius=300`) |
| SAP Hybris (Solr storefinder) | `_ui/responsive`, `solrStoreLocatorPage`, `window.Config = { EndPoint: 'store' }` | `${ContextPath}/store/all` returns GeoJSON FeatureCollection |
| Custom Algolia | `*-dsn.algolia.net` XHR, `appId` + `searchApiKey` exposed | POST `/1/indexes/<index>/query` with `hitsPerPage: 1000` |

### `year_opened` estimation when per-store dates aren't published

Tested-and-true formula:

1. **Anchor the totals**: pull cumulative country counts from 10-Ks / annual reports / press milestones. Build a `(year → cumulative_count)` table.
2. **Lock individual stores from PR/news**: any store explicitly named in a press release gets a `*-pr-confirmed` tag.
3. **Rank the rest**: flagship → tier-1 city → tier-2 → tier-3, alphabetical for determinism.
4. **Bucket-allocate** annual openings to ranked stores in priority order until quotas are filled.
5. **Tag everything** with a `*_validation` string and a `_year_opened_method` raw field so estimates are auditable.

This worked for Lulu's 185 China stores (~30 stores PR-confirmed, rest tier-bucketed) and produced a histogram that matches public disclosures.

### Schema gotchas

- **Slugify lowercases ASCII** but preserves Chinese characters. So `lululemon-cn-上海浦东ifc` (lowercase ifc) — not `IFC`. Your hardcoded ID lookups need to match.
- **Some stores have duplicate `storeCode`**: Gucci had 9 dedupe collisions out of 607 raw → 598 unique. Always dedupe by ID after normalizing.
- **`year_opened` can be null** — popups, freshly-scraped retailers, edge cases. The viewer handles this by showing them only at `year >= state.yearMax` (i.e., "currently operating, opening date unknown"). When you add a new retailer, decide upfront whether to leave year_opened null or backfill.
- **`coord_is_estimated`** is a real signal — markers are rendered at 60% opacity when true. Used for city-centroid+jitter coords (China stores) and CMS records without lat/lng (Alo international).
- **`status: "coming_soon"`** exists alongside `"active"` — don't filter only on `=== "closed"`.

### Smart chip region detection

Final algorithm (in `app.js:detectRegion`):

1. If `zoom <= 3` or longitude span ≥ 180° → return `null` (Worldwide).
2. If map center is in Europe bounding box AND ≥3 European countries have a visible store in viewport → return `'EU'`.
3. Otherwise: country = country of the visible store **nearest the map center**.

The "nearest store" approach is simpler and more deterministic than share-of-in-view-stores heuristics, which flickered as years scrubbed (e.g., US share crossing 50% between 2011 and 2012 caused chip count to "drop" from 146 worldwide to 89 US).

### Cache invalidation on GitHub Pages

Mobile Safari and Chrome aggressively cache JS files. Without cache-busting, edits to `app.js` won't appear on phones for hours. Pattern: bump `?v=N` in every `<script>` and `<link>` reference in the HTML when you change the corresponding JS/CSS file. Currently at v=15.

---

## Open opportunities

1. **Refine more China dates** — 173 of 185 China stores are still tier-bucketed. Press releases for individual store openings (the ones Lindsay's been collecting) directly upgrade these to `china-pr-confirmed`.
2. **More aggregation regions** — only Europe is implemented; could add `NA`, `APAC`, `MENA`, `LATAM` with the same pattern in `detectRegion`.
3. **More retailers** — the pattern is well-trod. Each takes ~30-60 min: identify platform, scrape, normalize, add to RETAILERS array.
4. **Closures** — we don't track store closures over time well; the time-lapse only adds, never removes. Could enhance.
5. **Year-opened upgrade for Alo's `coord_is_estimated` stores** — Brazil, newer markets — coords are city centroids; could geocode to mall addresses for better pin precision.
6. **Gucci year_opened backfill** — currently null for all 598 stores (per skill spec). Could do Kering annual report extraction the same way we did Lulu's 10-Ks.
7. **More dashboard cards** — currently 6; original brainstorm had 13 ideas (see chat history if revisiting).
8. **Region debut timeline** — "first store in country X = year Y" view is interesting and not yet built.

---

## Notes for next conversation

- Read `MEMORY.md` first; the auto-memory entry for `store-map` will tell you to read this file.
- Don't re-create the `_scripts/` files — they're already there locally even though gitignored.
- The data files in the repo at `data/lululemon.json`, `data/alo-yoga.json`, `data/gucci.json` are the canonical published versions. The local `data/` folder may have additional `_*` working files.
- When in doubt about which version is current, check `git log` and `scraped_at` in the JSON top-level.
