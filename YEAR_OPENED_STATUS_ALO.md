# Alo Yoga — `year_opened` validation status

**Last updated: 2026-05-06**
**Read this to know what's validated, what's not, and how it's all logged.**

## TL;DR

- All **224 stores** in `data/alo-yoga.json` have a `year_opened` value and a `year_opened_validation` status.
- **101 stores have direct evidence** (web search confirmed/corrected, or Wayback Machine snapshot).
- **123 stores rely on Builder.io CMS `createdDate` only** — these need user confirmation if exactness matters.
- **3 stores were searched for but no specific opening-date coverage was found** in basic search.
- **Every store's citation is logged in the JSON** at `raw._year_opened_citation`.

## Where the data lives (the answer to "where is everything stored?")

Everything is in **`G:\My Drive\Programs\store-map\data\alo-yoga.json`**, on each individual store record. The relevant fields per store:

| Field path | What it holds | Always present? |
|---|---|---|
| `year_opened` | Integer year the store opened, or `null` | Yes (224/224) |
| `year_opened_validation` | One of 6 status strings (see below) | Yes (224/224) |
| `raw._year_opened_citation` | Free-text source description (URL pattern + date) | Yes (224/224) |
| `raw._year_opened_signals` | Dict of raw inputs: `{builder_created_year, builder_created_ms, wayback_earliest_year, wayback_snapshot}` | Most stores |
| `raw._year_opened_source` | Provenance label (legacy field; same info as validation) | Most stores |
| `raw._year_opened_correction` | For corrected stores only: `{previous_year, corrected_year, month, source, validated_via}` | 21 stores |
| `raw._year_opened_snapshot` | For Wayback-sourced stores: timestamp of earliest archive | 14 stores |

### The 6 validation status values

| Status | Count | What it means | Trust level |
|---|---:|---|---|
| `web-search-confirmed` | 63 | News/blog source confirmed the year matches what we have | **High** |
| `web-search-corrected` | 21 | News/blog source showed the year was wrong; we updated it | **High** (year is now right) |
| `wayback-store-page` | 13 | Earliest CDX snapshot of the dedicated `/pages/<slug>-store` URL | Medium-High |
| `wayback-stores-directory` | 1 | Earliest mention in archived directory page | Medium |
| `web-search-attempted-not-found` | 3 | Tried to validate but no specific date in basic search | Low (relies on Builder.io) |
| `builder-createddate-only` | 123 | Year is Alo's Builder.io CMS `createdDate`; **NOT** individually web-validated | Variable |

### How to read a store's citation

For any store in the JSON, look at `raw._year_opened_citation`. Examples:

```json
"name": "Kings Road",
"year_opened": 2023,
"year_opened_validation": "web-search-confirmed",
"raw": {
  "_year_opened_citation": "Retail Gazette 2023/11 — UK debut Nov 17 2023",
  ...
}
```

```json
"name": "Beverly Hills Flagship",
"year_opened": 2016,
"year_opened_validation": "web-search-corrected",
"raw": {
  "_year_opened_citation": "Wikipedia (Alo Yoga) — Beverly Hills was Alo's first retail store, opened April 20, 2016. Wayback's earliest snapshot was 2019, which was misleading.",
  "_year_opened_correction": {
    "previous_year": 2019,
    "corrected_year": 2016,
    "month": 4,
    "source": "...",
    "validated_via": "manual web search 2026-05-06"
  },
  ...
}
```

```json
"name": "CF Market Mall",
"year_opened": 2024,
"year_opened_validation": "builder-createddate-only",
"raw": {
  "_year_opened_citation": "Alo Builder.io CMS createdDate (not individually web-validated)",
  "_year_opened_signals": { "builder_created_year": 2024, ... }
}
```

## What's been completed (validation work to date)

### Round 1 — Initial population (Wayback + Builder.io combine)

- Combined Builder.io `createdDate` with Wayback Machine earliest snapshot of dedicated `/pages/<slug>-store` URLs.
- Caught 16 older flagships via Wayback (Beverly Hills, Palisades Village, The Grove, Santa Monica, La Jolla, Fashion Valley, Stanford, Aspen, Oakbrook, Boston Seaport, SOHO Flagship, Williamsburg, etc.).
- Got 100% coverage but with the migration-year ambiguity for stores at 2023.

### Round 2 — Web search validation, 2023 cohort focus

- Validated all international debuts: Kings Road London (UK 2023), Mexico (Artz Pedregal + Antara 2023), Israel (TLV + Dizengoff 2023), Saudi Arabia (Kingdom Mall 2021 — corrected), Kuwait (2022 — corrected), Toronto Bloor + Yorkdale (2022 — corrected), all Canadian 2023 stores.
- Found Boston Seaport was 2022 not 2023 (Wayback misled us).
- Used Alo's own blog posts to validate the November 2022 + September 2022 + May 2022 cohorts (8 corrections).
- Wikipedia revealed Beverly Hills Flagship is actually 2016, not 2019.

### Round 3 — 2024-2026 spot-check (28 stores)

- Validated UK 2024 stores (Regent Street Aug 2024, Brompton Road, Grafton Street Dublin Dec 2024).
- Validated Middle East 2024 (Dubai Mall Feb 2024, Galleria Abu Dhabi, Doha Festival City June 2024).
- Validated Indonesia (Senayan City Mar 2024).
- Validated Korea expansion (Dosan flagship July 2025, Lotte Main Aug, Hyundai Sept).
- Validated UK 2025 wave (Manchester, Westfield London, Battersea — Nov-Dec 2025).
- **Found EmQuartier Bangkok was actually 2023** (Alo's first Asia store), not 2024.
- **Found 4 Mexico City stores at 2026 were actually 2025** (Mitikah, Santa Fe, Satelite, Angelopolis).
- **Found Leeds (UK) is 2026 not 2025** (delayed opening per Retail Gazette plan).

### Round 4 — 2025-2026 broader pass (~25 stores)

- Validated all 2025 international stores: Wolvenstraat + PC Hooftstraat (Amsterdam), Via del Babuino (Rome), ICONSIAM + Central Floresta (Thailand), Hannam + Lotte Jamsil (Korea), Andino (Colombia), Diamond Mall (Brazil), Blue Mall (Dominican Republic), Multiplaza (Panama), Jockey Plaza (Peru), Marassi (Bahrain), Solitaire Mall (Saudi Arabia), Istinye Park (Turkey).
- Validated 2026 Coming Soon international: Chatswood Chase (Australia), Westbourne Grove (UK), La Croisette + Rue Gambetta (France).
- Validated several major US 2024-2025: Westfield Century City (LA), Brickell City Centre (Miami), American Dream (NJ Dec 2025), Bridgewater Commons (NJ Sept 2025), Burlingame (CA), Mall of America (MN Q3 2025), The Summit Birmingham (AL Summer 2025).
- **Found Oakridge Park Vancouver is 2026 not 2025** (Spring 2026 debut).

## What still needs validation, and why

**123 stores** have not been individually web-validated. They rely on Alo's Builder.io `createdDate` — generally reliable for stores added after Alo's ~early-2023 CMS migration, but not perfect.

### At year=2023 (33 stores) — could hide 2022 stragglers

These are all US mall stores. Pattern of past errors: stores Alo added to Builder.io in 2023 that actually opened in 2022 (e.g., Kierland Commons, Cherry Creek). Sample bias suggests 3-5 more 2022 stragglers may be hidden here.

| State | Stores |
|---|---|
| California (8) | Americana at Brand, Broadway Plaza, Fashion Island, One Colorado, The Forum Carlsbad, Valley Fair, Westfield Roseville Galleria, Westfield Topanga |
| Florida (4) | Aventura, International Plaza, Miami Design District, Shops at Merrick Park |
| Texas (4) | Domain Austin, Market Street The Woodlands, Shops at Clearfork, Shops at La Cantera |
| Illinois (2) | Michigan Ave., Old Orchard |
| New Jersey (2) | Garden State Plaza, Mall at Short Hills |
| Ohio (2) | Easton Town Center, Kenwood Towne Centre |
| 1 each | Scottsdale Fashion Square (AZ), Westfarms Mall (CT), Ala Moana (HI), Plaza Frontenac (MO), Shops at Columbus Circle (NY), Southpark (NC), Forum Shops at Caesars (NV), King of Prussia (PA), City Creek Center (UT), Tysons Galleria (VA), Georgetown (DC) |

### At year=2024 (38 stores) — Builder.io CMS-era, generally reliable

Mix of US/Canadian mall stores plus a few international stragglers I didn't get to.

| Country | Stores |
|---|---|
| US (24) | Bellevue Square, Cherry Hill Mall, Fashion Mall at Keystone, Galleria Edina, Gardens on El Paseo, Harbor East, La Encantada, Mall at Green Hills, Palmer Square, Pinecrest, Roosevelt Field, Ross Park, Shops at Crystals, Somerset Collection, Sportsmen's Lodge, State Street, Town Center Boca Raton, The Mall at Millenia, The Street at Chestnut Hill, UTC Sarasota, Village at Corte Madera, Walnut Street, Washington Square, Waterside Shops |
| CA (7) | CF Carrefour Laval, CF Market Mall, CF Rideau Centre, CF Sherway Gardens, Royalmount, Square One Shopping Centre, Ste-Catherine St. |
| ID (2) | Plaza Indonesia, Beachwalk Bali |
| IL (2) | Ramat Aviv Mall, Azrieli Mall Hayam |
| MY (1) | The Exchange TRX |
| TR (1) | Emaar Square |
| GB (1) | Covent Garden |

### At year=2025 (38 stores) — all US mall stores

Mall-store openings rarely get individual news coverage of opening dates. Builder.io `createdDate` is generally reliable here.

`Abbot Kinney, Alys Beach, Biltmore Fashion Park, Brea Mall, CityPlace West Palm Beach, Corners of Brookfield, Dadeland Mall, Dallas Galleria, Del Amo Fashion Center, Downtown Summerlin, Dumbo Brooklyn, Hudson's Detroit, Lakeside Shopping Center (Metairie), Los Cerritos Center, Market Street at Lynnfield, Naperville, North Hills, Old Town Alexandria, Oxmoor Center, Penn Square Mall, Promenade at Westlake, Rice Village, Ridgedale Center, Saddle Creek, SanTan Village, Shops at La Cantera, South Coast Plaza, Southlake Town Square, Streets at Southpoint, Suburban Square, Summit at Fritz Farm, The Grove at Shrewsbury, Twenty Ninth Street, Utica Square, Vail Village, Walt Whitman, Westport, Willowbrook Mall, Woodfield Mall`

### At year=2026 (14 stores) — all US "Coming Soon"

These are pre-opening announcements. The "Coming Soon" label is in the store name itself. Year reflects Alo's announced opening year. Trust is high since they're explicitly future-dated.

`211 Columbus Ave, ABQ Uptown, Avalon, Bethesda Row, Center of Waikiki, Collins Avenue, Country Club Plaza, Fashion Place Mall, The Gate at Manhasset, Jordan Creek, King Street Charleston, One Loudoun, Stonebriar Centre, Village at Rochester Hills`

### Tagged as "tried but couldn't find" (3 stores)

| Store | Builder year | Why no evidence found |
|---|---|---|
| Glilot (IL) | 2025 | No specific opening-date coverage in basic search |
| 360 Mall, Kuwait | 2025 | Confirmed it's Alo's 2nd Kuwait store; specific opening date not in search |
| Brookfield Place NYC (Coming Soon) | 2026 | Recent job postings confirm imminent opening; no public grand-opening date yet |

## How to extend the validation (workflow if you want to dig deeper)

If you want to confirm or correct a specific store:

1. **Open `data/alo-yoga.json`** and find the store record.
2. Check `raw._year_opened_citation` — that's the current source for its year.
3. Web-search `"Alo Yoga <store name> <city> opening"` and look for news/blog evidence.
4. **If correct year:** edit `_scripts/tag_alo_year_validation.py`, add the store key + citation to `WEB_SEARCH_CONFIRMED`, then `python _scripts/tag_alo_year_validation.py`.
5. **If wrong year:** edit `_scripts/apply_alo_year_corrections.py`, add the store + correction + source. Then `python _scripts/apply_alo_year_corrections.py`, then re-tag.
6. Both scripts are idempotent — safe to re-run.

## Key scripts (for reference)

| Script | Purpose |
|---|---|
| `_scripts/scrape_alo-yoga.py` | Original scrape (creates `alo-yoga.json` from Builder.io) |
| `_scripts/enrich_alo_year_opened.py` | Wayback Machine sweep + per-flagship CDX |
| `_scripts/enrich_alo_year_opened_combine.py` | Combines Builder.io createdDate + Wayback signals |
| `_scripts/apply_alo_year_corrections.py` | Applies hand-curated corrections from web search |
| `_scripts/tag_alo_year_validation.py` | Tags every store with validation status + citation |

Run order to rebuild from scratch: scrape → enrich (Wayback) → combine → apply corrections → tag.

## What's not done elsewhere (for context)

- **Lululemon's `year_opened` is not yet populated.** Different approach needed since Lululemon doesn't have an obvious CMS-created-date analog. Wayback per-flagship-URL would be the starting point. Out of scope for now.
