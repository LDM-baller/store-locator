# store-map — spec

## Goal

A local toolkit for visualizing physical retail footprints. Lindsay can scrape any retailer's store directory into a normalized JSON file, optionally enrich each store with the year it opened, and **view multiple retailers overlaid on the same interactive map** with click-to-inspect detail panels.

Used for competitive analysis. No infra — runs on Lindsay's laptop. Data lives in Google Drive (`G:\My Drive\Programs\store-map\`) so it's automatically backed up.

## User flow (end-to-end)

1. **Scrape a retailer.** Lindsay says `/scrape-retailer <name>`. The skill identifies the locator platform, fetches every store, normalizes it, and saves `data/<slug>.json`.
2. **(Optional) Enrich.** Lindsay says `/enrich-stores <slug>`. The skill fills `year_opened` for every store using Wayback Machine + targeted web search. Slow; runs once per retailer; results are cached in the same JSON.
3. **Repeat** for additional retailers as desired. Each scrape is independent and idempotent.
4. **View the map.** Lindsay opens `index.html` in a browser. A small config block at the top of the file lists which retailer JSONs to load. **The map can show two or more retailers simultaneously, with each retailer rendered as visually distinct pins (different colors) on the same map.** Filters: retailer (toggle each on/off), country, store type, year-opened range. Clicking any pin opens a side panel with the store's full info.

No login, no server, no scheduled jobs. Re-running a scrape overwrites the file in place.

## Components

| # | Component | Type | Status |
|---|---|---|---|
| 1 | `/scrape-retailer` | Slash-command skill | ✅ Built |
| 2 | `/enrich-stores` | Slash-command skill | 🔲 Planned |
| 3 | `index.html` map viewer | Static webpage (Leaflet + OpenStreetMap) | 🔲 Planned |
| 4 | `retailer-notes.md` registry | Project doc | ✅ Seeded with Lululemon |

### 1. `/scrape-retailer` (built)

- **Input:** retailer name + locator URL (+ scope: global/region)
- **Process:** detect platform (`__NEXT_DATA__` SSR / Yext / Brandify / Storerocket / Algolia / custom); fetch all stores; normalize to common schema; validate
- **Output:** `data/<slug>.json` and a row in `retailer-notes.md`
- **Side effect:** persistent scraper at `_scripts/scrape_<slug>.py` so re-runs don't reinvent
- **Skill file:** `~/.claude/commands/scrape-retailer.md`

### 2. `/enrich-stores` (partially done — Alo only, 2026-05-06)

- **Input:** a slug (e.g., `alo-yoga`) — operates on an already-scraped JSON
- **Sources, in priority order:**
  1. **CMS-internal timestamps** — when available (e.g., Alo's Builder.io `createdDate` per store entry). Highest coverage for stores added after the CMS was deployed. Implemented for Alo via `_scripts/enrich_alo_year_opened_combine.py`.
  2. **Wayback Machine — per-store page** — earliest CDX snapshot of the retailer's individual store URL. Catches stores that pre-date the CMS migration. Implemented for Alo via `_scripts/enrich_alo_year_opened.py`.
  3. **Wayback Machine — stores directory sweep** — earliest snapshot of the main locator/directory page that mentions the store's name. Limited reliability when the directory is JS-rendered (the snapshot HTML may not include store data). Implemented in the same script.
  4. **Web search fallback** (planned, not yet built) — search `"<retailer> <city> opening"` and extract year from press-release / news results. Paid API.
- **Output:** in-place update of `data/<slug>.json`. Sets `year_opened`, `raw._year_opened_source`, `raw._year_opened_signals`. Top-level adds `year_opened_coverage`, `year_opened_histogram`, `year_opened_note`.
- **Status:** Alo done at 100% coverage. Lululemon not yet enriched — would need a similar combiner since Lulu's NA `raw.storeStatus`/`raw.storeType` don't have a created date, but Wayback per-store sweep + their internal storeId numbering could give signal.

### 3. Map viewer (planned)

- **One file:** `index.html` at project root. Plain HTML + Leaflet + OpenStreetMap tiles. No build step, no API key, no server.
- **Config:** small JS block listing which retailer JSON files to load and what color to use for each
- **Multi-retailer overlay is a first-class requirement.** The viewer must:
  - Load 2+ retailer JSONs at once and render them on the same map
  - Render each retailer's pins in a distinct color (driven by a per-retailer color in the config or registry)
  - Show a legend mapping retailer → color
  - Allow each retailer's layer to be toggled independently on/off
- **Estimated-coord pins are visually distinct.** Pins where `coord_is_estimated: true` render with an outline ring or hatched fill (configurable) so users can tell at a glance which pins are exact (from the retailer's data) vs approximate (geocoded from address). Tooltip exposes `coord_source`.
- **`store_type` and `status` drive pin styling and filters.** Renderers should:
  - Color or shape pins by `store_type` (e.g., flagship = larger pin, concession = different icon, outlet = different color)
  - Treat `status: coming_soon` distinctly (e.g., dotted outline, lighter opacity)
  - Expose both as filter toggles in the legend
- **Other features:**
  - Cluster pins when zoomed out (Leaflet.markercluster)
  - Click a pin → side panel with name, address, hours, year_opened, status, type, store URL
  - Top-bar filters: country, store type, year-opened range (apply across all loaded retailers)
- **Out of scope (v1):** drawing trade-area circles, density heatmaps, demographics overlay, nearest-competitor analysis

## Data model

### Per-retailer JSON file (`data/<slug>.json`)

```json
{
  "retailer": "Lululemon",
  "slug": "lululemon",
  "source_url": "https://shop.lululemon.com/stores/all-lululemon-stores",
  "platform": "custom-nextjs-ssr",
  "scope": "North America (US + CA)",
  "scraped_at": "2026-05-05T...",
  "store_count": 562,
  "stores": [ ... ]
}
```

### Per-store record

```json
{
  "id": "lululemon-00351",
  "retailer": "Lululemon",
  "name": "Banff",
  "address": "125 Banff Avenue",
  "city": "Banff",
  "state": "AB",
  "country": "CA",
  "postal_code": "T1L 0A1",
  "lat": 51.1758,
  "lng": -115.5713,
  "coord_is_estimated": false,
  "store_type": "regular",
  "status": "active",
  "phone": null,
  "hours": [ ... ],
  "url": "https://shop.lululemon.com/stores/ca/banff/banff",
  "year_opened": null,
  "scraped_at": "2026-05-05T...",
  "raw": { /* original API response. Includes _coord_source ("embedded" / "googl-redirect" / "nominatim" / "manual_override") so coord provenance is auditable. May also include _manual_override pointing at the entry from manual_overrides.json. */ }
}
```

### `year_opened` field

**For the current state of year_opened validation per retailer:**
- Alo Yoga: see `YEAR_OPENED_STATUS_ALO.md`
- Lululemon: see `YEAR_OPENED_STATUS_LULU.md`

The year the store opened (best estimate, integer or null). Sourcing strategy:

1. **Combine multiple signals when available.** For Alo Yoga we combine (a) Builder.io's per-store-entry `createdDate` (when Alo's CMS entry was created — strong proxy for stores added to the CMS after the platform migrated to Builder.io ~2023) and (b) Wayback Machine's earliest snapshot of the retailer's stores directory or per-store page (catches stores that existed before the CMS migration). `year_opened = min(builder_year, wayback_year)` — the earliest evidence of existence is the closest proxy to true opening year.

2. **Caveat: CMS-migration year ambiguity.** If a retailer migrated their CMS in year X and an entry's `createdDate=X` with no other evidence, the store may actually have opened earlier than X. This is unavoidable without Wayback or other corroborating data. We don't try to second-guess; the `_year_opened_signals` field on each store records both raw signals so the source is auditable.

3. **For "Coming Soon" stores**, year_opened reflects the planned/announced opening year (or the year the entry was added, which is usually the same).

Per-store record gets:
- `year_opened: 2024` (int) or `null`
- `year_opened_validation`: one of `web-search-confirmed` / `web-search-corrected` / `wayback-store-page` / `wayback-stores-directory` / `web-search-attempted-not-found` / `builder-createddate-only`
- `raw._year_opened_citation`: free-text source description (always present once tagger has run)
- `raw._year_opened_source`: provenance label (legacy)
- `raw._year_opened_signals`: `{ "builder_created_year": 2023, "wayback_earliest_year": 2021, ... }` — both signals preserved
- `raw._year_opened_correction`: present only for stores where the year was changed via web search; contains `{previous_year, corrected_year, month, source, validated_via}`

Top-level adds:
- `year_opened_coverage: { known: 224, unknown: 0 }`
- `year_opened_histogram: { "2019": 2, "2020": 2, ..., "2026": 23 }`
- `year_opened_validation_counts: { "web-search-confirmed": 63, "web-search-corrected": 21, ... }`
- `year_opened_note`: explanation

### `store_type` and `status` fields

Every store record carries:

- **`store_type`** — one of `regular` (default) | `popup` | `outlet` | `flagship` | `concession` | `showroom` | `experiential` | `other`
- **`status`** — one of `active` (default) | `coming_soon` | `closed`

Stores with `status: "closed"` are **dropped from the output entirely** (the value exists in the schema for clarity but never appears in the saved file).

Sources for these fields:
- If the retailer's source data exposes them directly (e.g., Lululemon NA's `raw.storeStatus` / `raw.storeType`, Alo's `raw.storeStatus`/`raw.storeType`) — promote them. Map `"active_soon"` → `"coming_soon"`.
- Otherwise auto-classify from the store name: names containing `"Pop-up"`/`"Popup"` → popup; `"Outlet"`/`"Factory Outlet"` → outlet; known dept-store substrings (`"Fenwick"`, `"Selfridges"`, `"Harrods"`, `"Daimaru"`, `"Brown Thomas"`) → concession; `"(coming soon)"`/`"Coming Soon"` → status=coming_soon; `"CLOSED"`/`"Permanently Closed"` → status=closed (dropped).
- Manual overrides (see below) always win over auto-classification.

### Manual overrides

`G:\My Drive\Programs\store-map\manual_overrides.json` is a project-root file that lets us pin per-store decisions across re-runs. Each entry is keyed by the full store ID and may contain:

- `geocode_query` — replaces the auto-generated Nominatim query (useful when a store name doesn't geocode well, e.g., `"Bullring (coming soon)"` becomes `"Bullring shopping centre, Birmingham, UK"`)
- `lat` / `lng` — skip geocoding entirely and use these coordinates directly
- `store_type` / `status` — stamp these onto the store, overriding auto-classification
- `_note` — human-readable explanation

Scrapers and patch scripts read this file and apply overrides during the geocoding step. Edit by hand to fix edge cases.

### Per-retailer JSON top-level summary fields

In addition to `retailer`, `slug`, `source_url`, `platform`, `scope`, `scraped_at`, `store_count`, the file includes:

- `geocoded_count` — how many stores have `coord_is_estimated: true`
- `store_type_counts` — `{ "regular": 532, "popup": 72, "outlet": 46, "concession": 7, ... }`
- `status_counts` — `{ "active": 653, "coming_soon": 12 }`
- `geocoded_note` — free-text explanation of why estimates exist for this retailer

### Coordinate sourcing rules

For every store, we want a `lat`/`lng`. We try sources in this order:

1. **Source-provided coords** (preferred). Pulled directly from the retailer's API/CMS payload — `coord_is_estimated: false`, `raw._coord_source`: `"embedded"`.
2. **Resolved from short URLs in the source** — `goo.gl/maps/...`, `maps.app.goo.gl/...`, or fetching long `/maps/place/...` URLs to extract coords from the redirect chain. Still `coord_is_estimated: false` (the retailer pinned this exact spot in Maps).
3. **Geocoded via OSM Nominatim** — only as a fallback when the retailer's source has a complete address (street + city + state/region + country) but no Maps URL. `coord_is_estimated: true`, `raw._coord_source: "nominatim"`, `raw._geocode_query` records the exact query used. Use a progressive query strategy (mall name + city + country, then cleaned street, then city + country as a last resort coarse pin). Respect Nominatim ToS: 1 req/sec, real User-Agent.

The `coord_is_estimated` flag flows to the map viewer, which renders estimated pins in a visually distinct style (e.g., outline ring instead of filled, or hatched fill) so the user can tell at a glance which pins are exact vs approximate.

The output JSON includes a top-level `geocoded_count` so you can see at a glance what fraction of pins are estimates. Add a `geocoded_note` explaining why estimates exist for that retailer.

### Registry (`retailer-notes.md`)

One row per retailer: name, slug, source URL, platform, scope, store count, script path, and *gotchas* (bot protection, regional splits, address quirks, missing fields). Read before scraping a known retailer; updated after every scrape.

## File map

```
G:\My Drive\Programs\store-map\
├── SPEC.md                          ← this file
├── retailer-notes.md                ← registry [✅ created]
├── manual_overrides.json            ← per-store-ID overrides [✅ created]
├── NEXT_STEPS.md                    ← handoff doc; remove when no work pending
├── index.html                       ← map viewer [🔲 planned]
├── data\
│   ├── lululemon.json               ← 665 stores global (562 NA exact + 103 intl estimated)
│   ├── alo-yoga.json                ← 224 stores, 46 geocoded
│   ├── _alo-yoga_builder.json       ← cached Builder.io payload (regenerated on re-run)
│   ├── _lulu_intl_cache\            ← cached SSR responses for the international scrape
│   └── _lululemon_pre_overrides.json.bak  ← pre-patch backup
├── _scripts\
│   ├── scrape_lululemon.py          ← NA-only Lululemon scraper
│   ├── scrape_lululemon_intl.py     ← international Lululemon scraper (SSR + Nominatim)
│   ├── patch_lululemon.py           ← surgical patch for lululemon.json (overrides + classification)
│   └── scrape_alo-yoga.py           ← Alo scraper w/ Nominatim fallback
└── (future: data\<slug>.json + _scripts\scrape_<slug>.py per retailer)

C:\Users\lindsay.druckermann\.claude\commands\
├── scrape-retailer.md               ← skill [✅ built]
└── enrich-stores.md                 ← skill [🔲 planned]
```

## Open decisions

- **Color palette** for retailers in the map — pick a fixed palette up front, or assign per-load? *(Suggest: fixed palette in `retailer-notes.md`, one column.)*
- **`year_opened` confidence** — should the side panel show source (Wayback / news / manual) or just the year? *(Suggest: show source on hover.)*
- **International coverage** — for retailers with regional splits (e.g., Lululemon EU/UK/AU/JP), scrape now or treat as a known gap? *(Suggest: skip until there's an analytical reason; document the gap in the registry.)*
- **`raw` field bloat** — Lululemon's JSON is 3.5 MB partly because `raw` duplicates a lot. Strip `raw` before the map loads it? *(Suggest: keep `data/<slug>.json` as-is, generate a slimmed `data/<slug>.viewer.json` at view-build time if needed.)*

## Out of scope (explicit)

- No database (SQLite, Postgres, etc.) — JSON files are sufficient at this scale
- No automatic re-scraping schedule — Lindsay re-runs `/scrape-retailer` manually when she wants fresh data
- No authentication, sharing links, or hosted deployment — viewer is local-only
- ~~No geocoding from addresses — if a retailer's API doesn't return coordinates, that store is flagged and skipped (not synthesized)~~ **REVISED 2026-05-05:** Geocoding *is* allowed as a fallback when the source provides a complete address but no Maps URL. Such stores are tagged `coord_is_estimated: true` and rendered visually distinct on the map. See "Coordinate sourcing rules" above.
- No demographic / sales / traffic overlay data — pure store-presence map
