# store-map — handoff / next-steps

**Last updated:** 2026-05-06
**Read this first if context was lost. This is the single source of truth for "where are we and what's next."**

## Project at a glance

A local toolkit to map physical retail footprints. For each retailer, we scrape every store, normalize to a common schema, and visualize on an interactive map. Data lives in Google Drive; map runs from a local static `index.html`. See `SPEC.md` for full design.

**Project root:** `G:\My Drive\Programs\store-map\`

## State of each retailer

### Alo Yoga — DONE
- **`data/alo-yoga.json`:** 224 stores, all with coordinates, `year_opened`, `year_opened_validation`, and `raw._year_opened_citation`. Schema includes `store_type`, `status`, `coord_is_estimated`.
- **Methodology:** Builder.io payload (which has 224 store entries) + Wayback Machine for older flagships + 4 rounds of web-search validation/correction. 21 stores were corrected with cited sources; 63 directly web-confirmed; the rest derived from Builder.io's per-entry `createdDate`.
- **Status doc:** `YEAR_OPENED_STATUS_ALO.md` — comprehensive: methodology, every validation status counted, gaps user might want to confirm, country-debut sources.
- **Manual overrides:** `manual_overrides.json` — 8 entries for Alo edge cases (Bullring, Wertheim Outlet, etc.). Re-running `_scripts/patch_lululemon.py` is idempotent.

### Lululemon — PARTIAL (665 of ~811 stores; major Asia + Mexico gap)
- **`data/lululemon.json`:** 665 stores. Validation system fully populated (year_opened, validation status, citation per store). 562 NA exact coords + 103 international estimated coords.
- **Methodology:** SEC EDGAR 10-K country-by-year company-operated counts (FY2007-FY2025, 19 10-Ks fetched and parsed). Each store ranked by ID within country, mapped to fiscal-year-bucket via 10-K count progression. Pre-FY2019 NA via narrative totals; pre-FY2019 international via known country debut years (linearly distributed). 9 web-search-confirmed overrides (year + country corrections). 3 country misclassifications fixed (Antwerp→BE, Cologne→DE, Zurich→CH).
- **Status doc:** `YEAR_OPENED_STATUS_LULU.md` — comprehensive.
- **Manual overrides:** `manual_overrides_lulu.json` — 6 year corrections + 3 country corrections; format documented in the file.

## What's pending (in priority order)

### 1. Asia + Mexico expansion for Lululemon — BIG GAP

Lulu's actual store count per FY2025 10-K is **811 company-operated**. We have 665. Missing breakdown by country:

| Country | Lulu count | Our count | Gap |
|---|---:|---:|---:|
| **China Mainland** | 172 | 0 | -172 |
| Mexico | 26 | 0 | -26 |
| South Korea | 22 | 0 | -22 |
| Hong Kong SAR | 11 | 0 | -11 |
| Singapore | 9 | 0 | -9 |
| Taiwan | 7 | 0 | -7 |
| Malaysia | 5 | 0 | -5 |
| Thailand | 5 | 0 | -5 |
| Macau SAR | 3 | 0 | -3 |
| (smaller stragglers) | | | -3 |

**Total missing: ~263 stores** (we also have ~117 EXTRA US/CA stores because we include outlets/popups that 10-K excludes from "company-operated", so the net gap of 146 hides the actual scope).

#### How to scrape each missing market

Our intl scraper (`_scripts/scrape_lululemon_intl.py`) hit these Demandware sites: UK, AU, NZ, JP, FR, DE. To add the missing markets:

| Country | Likely site | Notes |
|---|---|---|
| China Mainland | `lululemon.cn` | Chinese e-commerce platform; different from EU/JP. Use Playwright. Will be the biggest job. |
| Mexico | `lululemon.com.mx` | **Geo-blocked from US IP** — Playwright timed out on direct connection. Per-store URLs on `shop.lululemon.com/stores/mx/<city>/<slug>` work via curl, but no aggregate directory. Need to web-search for the 26 store names + fetch each. |
| Korea | `lululemon.co.kr` (if exists) or via Demandware | Lulu has 22 KR stores, mostly Seoul/Gangnam |
| Hong Kong | `lululemon.com.hk` | Same Demandware pattern likely works |
| Singapore | `lululemon.com.sg` (if exists) | |
| Taiwan, Malaysia, Thailand, Macau | likely regional Asia sites | Smaller; could be aggregated under one Asian umbrella site |

#### Recommended phasing (matches what was discussed in the conversation)

- **Phase 1 (~1-2 hrs):** China Mainland + Mexico — biggest gaps
- **Phase 2 (~1-2 hrs):** Korea + HK + Singapore + smaller Asian markets
- **Phase 3 (~30 min):** Reconcile to 811, document residual gap

After scraping, run the 10-K-rank estimator (`_scripts/estimate_lulu_year_opened.py`) again — it'll automatically incorporate the new countries via the `COUNTRY_DEBUT` dict (which already has CN=2016, KR=2017, etc.).

### 2. Map viewer (`index.html`) — STILL PLANNED, NOT STARTED

See SPEC.md "Map viewer (planned)" section. Requirements: Leaflet + OpenStreetMap, multi-retailer overlay (Alo + Lulu visually distinct), pin styling by `store_type`, distinct rendering for `coord_is_estimated: true`, side panel on click with all store details.

Both retailers' JSONs are ready to consume.

### 3. Refinements (low priority)

- The 41 Lulu "post-10k-recent-or-excluded" stores could use per-store web search if specific dates matter. Add corrections to `manual_overrides_lulu.json` and re-run `_scripts/estimate_lulu_year_opened.py`.
- Apply the same year_opened estimator approach to Alo's 33 unverified 2023-cohort stores (per `YEAR_OPENED_STATUS_ALO.md`).
- `/enrich-stores` slash command (was in original SPEC) — never built; superseded by retailer-specific scripts.

## Where every piece of data lives

```
G:\My Drive\Programs\store-map\
├── SPEC.md                                  ← project spec
├── NEXT_STEPS.md                            ← THIS FILE; start here
├── YEAR_OPENED_STATUS_ALO.md                ← Alo methodology + state
├── YEAR_OPENED_STATUS_LULU.md               ← Lulu methodology + state
├── retailer-notes.md                        ← per-retailer registry
├── manual_overrides.json                    ← Alo per-store overrides
├── manual_overrides_lulu.json               ← Lulu per-store overrides + country fixes
├── data\
│   ├── alo-yoga.json                        ← 224 stores, FINAL
│   ├── lululemon.json                       ← 665 stores, PARTIAL (Asia+Mexico missing)
│   ├── _alo-yoga_builder.json               ← cached source payload
│   ├── _alo_wayback_cache\                  ← cached Wayback snapshots
│   ├── _lulu_intl_cache\                    ← cached Demandware SSR responses
│   ├── _lulu_10k_cache\                     ← 19 cached 10-Ks
│   ├── _lulu_10k_store_counts.json          ← extracted country×FY matrix
│   └── *.json.bak                           ← state backups before each major operation
└── _scripts\
    ├── scrape_lululemon.py                  ← Lulu NA scraper (Next.js __NEXT_DATA__)
    ├── scrape_lululemon_intl.py             ← Lulu intl scraper (Demandware SSR + Nominatim)
    ├── scrape_alo-yoga.py                   ← Alo scraper (Builder.io payload)
    ├── enrich_alo_year_opened.py            ← Wayback sweep + per-flagship CDX
    ├── enrich_alo_year_opened_combine.py    ← combiner
    ├── apply_alo_year_corrections.py        ← Alo web-search corrections
    ├── tag_alo_year_validation.py           ← Alo validation tagger
    ├── fetch_lulu_10ks.py                   ← downloads 19 10-Ks from SEC EDGAR
    ├── estimate_lulu_year_opened.py         ← Lulu year_opened estimator (idempotent; reads manual_overrides_lulu.json)
    ├── patch_lululemon.py                   ← Lulu surgical patcher
    └── probe_lulu_mx.py                     ← Mexico site probe (geo-blocked, currently failing)
```

## Per-store schema (in BOTH `alo-yoga.json` and `lululemon.json`)

Common fields on every store record:

```json
{
  "id": "<retailer-slug>-<unique-id>",
  "retailer": "Lululemon" | "Alo Yoga",
  "name": "Store name",
  "address": "Street",
  "city": "City",
  "state": "State or region",
  "country": "ISO alpha-2 country code",
  "postal_code": "...",
  "lat": 0.0,
  "lng": 0.0,
  "coord_is_estimated": false | true,
  "store_type": "regular | popup | outlet | flagship | concession | showroom | experiential | other",
  "status": "active | coming_soon | closed",   /* closed are dropped from output */
  "phone": "...",
  "hours": "...",
  "url": "...",
  "year_opened": 2023 | null,
  "year_opened_validation": "<status string>",  /* see status docs */
  "scraped_at": "<ISO timestamp>",
  "raw": {
    "_year_opened_citation": "<source description>",   /* always present once tagger has run */
    "_year_opened_signals": { ... },
    "_year_opened_correction": { ... },                 /* only if year was changed */
    "_country_correction": { ... },                     /* only if country was fixed */
    "_coord_source": "embedded | nominatim | googl-redirect | manual_override | ...",
    /* + original source data preserved */
  }
}
```

Top-level summary fields (per file): `retailer`, `slug`, `source_url`, `platform`, `scope`, `scraped_at`, `store_count`, `geocoded_count`, `store_type_counts`, `status_counts`, `year_opened_coverage`, `year_opened_histogram`, `year_opened_validation_counts`, `year_opened_note`.

## How to resume

If you're a future session: **read this file first**, then for whichever task you want to pick up, also read the matching status doc:

- Lulu Asia + Mexico expansion → start with **§"How to scrape each missing market"** above. Cached `_lulu_intl_cache/` shows the SSR pattern that worked for the 6 already-scraped regional sites; replicate for new countries.
- Map viewer → `SPEC.md` "Map viewer (planned)" section
- Per-store year refinements → status doc + `manual_overrides{,_lulu}.json` workflow

If you intend to run anything that overwrites `data/<retailer>.json`, take a backup first: `cp data/lululemon.json data/_lululemon_pre_<change>.json.bak`.

## Open conversational threads (so a fresh session has context)

These are things actively under discussion / decision when this session ends:

1. **Lulu's Asia + Mexico gap.** Lindsay asked about China specifically and confirmed she wants the dataset to match Lulu's 811 (or 856 with third-party). I proposed Phase 1 = China + Mexico (~1-2 hrs), Phase 2 = Korea + HK + smaller Asian markets, Phase 3 = reconcile. Awaiting her go/no-go.

2. **The 41 catch-all "post-10k-recent-or-excluded" Lulu stores.** Most are likely real recent (2025-2026) US mall openings; would benefit from per-store web search if precise dates matter. Default year is 2026.

3. **Lulu's 26 "Coming Soon" labeled stores** are placeholders for announced future openings (Bethesda Row, Country Club Plaza, etc.); year=2026 is appropriate.

## What is NOT done (so don't claim it is)

- Map viewer (`index.html`) doesn't exist yet
- Lulu Asia (CN, KR, HK, SG, TW, MY, TH, MO) and Mexico are not scraped — about 261 stores missing
- Lulu's franchise/third-party stores in MENA (UAE, Saudi, Israel, Kuwait, Qatar, Bahrain, Turkey, Belgium, Denmark — 45 stores per 10-K) not scraped
- No CI/CD, no automated re-scrape — everything is manual
