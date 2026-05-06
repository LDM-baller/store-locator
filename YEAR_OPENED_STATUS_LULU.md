# Lululemon — `year_opened` validation status

**Last updated: 2026-05-06**

## TL;DR

- All **665 stores** in `data/lululemon.json` have a `year_opened` and `year_opened_validation` value.
- Method differs from Alo: Lulu has no per-entry CMS `createdDate`, so we use **SEC 10-K company-operated store counts by country, year-by-year**, mapped to our store list via store ID rank.
- **Confidence varies by cohort.** Direct 10-K data covers FY2019-FY2025. Pre-FY2019 stores are placed via narrative totals (NA) or country debut years (international).

## Where the data lives

Same schema as Alo. Per store in `data/lululemon.json`:

| Field | What it holds |
|---|---|
| `year_opened` | Integer year |
| `year_opened_validation` | One of 7 status strings (see below) |
| `raw._year_opened_citation` | Free-text source describing how the year was derived |
| `raw._year_opened_signals` | Country rank, total in country, country's 10-K count progression |

## Validation status counts (665 / 665)

| Status | Count | Confidence | Description |
|---|---:|---|---|
| **10k-pre-fy2019-narrative-by-fy** | 351 | Medium | Pre-FY2019 NA stores. Year derived from Lulu's per-fiscal-year total store counts (FY2000=1, FY2003=7 first US, FY2007=81, FY2010=137, FY2015=254, etc.) + NA-combined store-ID rank. Smoothly distributed across fiscal years. |
| **10k-fiscal-year-bucket** | 119 | High | Stores added FY2019-FY2025. Direct mapping from the 10-K country-by-year count progression: store at country-rank N opened in the FY where the country's count first reached N. |
| **popup-10k-excludes** | 72 | N/A | Popup/temporary stores. 10-K count excludes these, so year_opened is null. |
| **country-debut-interpolated** | 68 | Medium-Low | Pre-FY2019 international stores. Linearly distributed between the country's known debut year (researched from press releases) and FY2019 by rank. |
| **post-10k-recent-or-excluded** | 44 | Low | Stores in our scrape that exceed Lulu's latest 10-K country count. Likely opened post-Feb 2026 OR are a store type 10-K excludes (e.g., concession, certain outlet categories). 3 stores in this cohort have country misclassifications (Antwerp tagged GB, Cologne tagged FR, Zurich tagged DE) — separate scrape-data issue. |
| **web-search-confirmed-override** | 6 | High | Year corrected via news/blog evidence. Stores: Battersea Power Station (Dec 2025), American Dream NJ (Dec 2025), Bridgewater Commons NJ (Sept 2025), Regent Mall Fredericton (Fall 2022), Manchester UK (Nov 2025), Westfield London (Nov 2025). |
| **post-10k-outlet** | 3 | Low | Outlet stores. 10-K's "company-operated" count excludes outlets per Lulu policy. |
| **10k-pre-fy2019-floor** | 2 | Low | Pre-FY2019 international where we don't have a confirmed debut year — used FY2019 as upper bound. |

## How `year_opened` was derived (the method)

### Source data

1. **SEC 10-K filings** for Lululemon (CIK 0001397187), fetched from EDGAR. Specifically:
   - **FY2019-FY2025** 10-Ks have a structured "Number of company-operated stores by market" table with per-country counts. Direct data.
   - **FY2007-FY2018** 10-Ks have only narrative descriptions (e.g., "There were 254 company-operated stores in operation as of February 1, 2015"). Used for total-store counts only.
2. **Country debut years from public sources** (Lulu corporate press releases, news articles, Wikipedia). Used to bound pre-FY2019 international stores.
3. **Lulu Dec 2025 press release** ("lululemon to Expand International Presence in 2026") — confirms 2025-2026 international expansion timeline.

### Algorithm

For each Lulu store in our data:

1. **Determine the country.**
2. **Sort stores within that country by store ID** (Lulu's IDs roughly track opening order — earliest IDs are 1990s Vancouver flagships, latest are 2024+ stores).
3. **For ranks ≤ FY2019 country count** (no per-country pre-FY2019 data):
   - **NA stores (US/CA combined, 491 stores):** map combined rank to Lulu's narrative total-store fleet (FY2007=81, FY2010=137, FY2015=254, etc.) → place in year band.
   - **International stores:** linearly distribute between known country debut year and FY2019 by rank within country.
4. **For ranks > FY2019 country count:** walk the country's FY-by-FY count progression. The first FY where the count >= rank = the fiscal year the store opened.
5. **For ranks > FY2025 count** (overflow): mark as post-10K (recent opening or 10-K-excluded type).

### Example: Banff (CA store, ID `00351`, NA-combined rank #59)

```
year_opened: 2007
validation: 10k-pre-fy2019-narrative-band
citation: "Lulu 10-K country-count progression for Canada (CA): this store ranks 
#59 among our 78 CA stores (sorted by store ID, which roughly tracks opening 
order). Source: SEC EDGAR filings for Lululemon (CIK 0001397187), 10-K for 
FY2007. Pre-FY2019 NA store. Combined US+CA rank #59 placed in band ≤2007 
(NA fleet was ~81 at end of FY2007)."
```

### Example: Australian flagship at AU-rank #15 of 31

```
year_opened: ~2011 (linearly interpolated: 2004 + 14 × (2019-2004)/30)
validation: country-debut-interpolated
citation: "Pre-FY2019 international store. AU had 31 stores at end of FY2019; 
this store ranks #15. Linearly distributed between known debut year (2004) and 
FY2019. Debut source: Lulu opened Chapel Street store in Melbourne October 2004 
(sgbonline.com)."
```

## Country debut years used

Sourced from public articles + Lulu press releases + 10-K narrative. Encoded in `_scripts/estimate_lulu_year_opened.py` as `COUNTRY_DEBUT`.

| Country | Debut Year | Source |
|---|---|---|
| Australia | 2004 | sgbonline.com — Chapel Street Melbourne Oct 2004 |
| UK | 2014 | drapersonline.com — Covent Garden March 28, 2014 (first European store) |
| New Zealand | 2014 | Estimate; Christine Day-era expansion to AU/NZ/UK |
| Singapore | 2014 | marketing-interactive.com — ION Orchard 2014 (first Asia retail) |
| China + HK | 2016 | Lulu corporate press release "lululemon Opens Stores in Beijing, Shanghai and Hong Kong" Dec 2016 |
| Japan | 2017 | Lulu corporate press release "lululemon Opens First Store in Japan at Ginza Six Mall" 2017 (after 2008 exit of first Lulu-Japan venture) |
| Germany | 2017 | the-spin-off.com — Munich was 2nd Germany store Oct 2017 |
| Korea, Switzerland | 2017 | Estimate based on FY2019 count + Asia expansion timeline |
| France, Sweden, Netherlands, Norway, Ireland | 2018 | Lulu FY2018 10-K narrative + Lulu corporate press release for Sweden Stockholm June 2018 |
| Taiwan, Macau, Malaysia | 2018 | Estimate based on FY2022 first appearance in 10-K table |
| Spain | 2022 | 10-K country table FY2022 first appearance |
| Thailand | 2023 | 10-K country table FY2023 first appearance |
| Italy, Belgium, Denmark, Turkey | 2025 | Lulu Dec 18, 2025 press release |
| Mexico | 2024 | FY2024 10-K — Lulu acquired Mexico operations during FY2024 |
| UAE, Saudi Arabia, Qatar, Kuwait | 2022 | 10-K third-party operated table FY2022 first appearance |
| Israel, Bahrain | 2023 | 10-K third-party table FY2023 first appearance |

## Histogram (final)

```
2000:   1   #                W 4th Ave Vancouver — Lulu's first standalone store
2001:   1
2002:   1
2003:   4   ####             First US store (Santa Monica)
2004:   9   #########        Australia debut + early NA growth
2005:  12
2006:  28   ############
2007:  17                    IPO year (FY2007 closed at 81 stores)
2008:  35   ###############  Post-IPO expansion
2009:  12
2010:   5                    AU franchise reacquisition (11 of 13 net new were AU; only 2 net new NA)
2011:  21
2012:  24
2013:  21
2014:  26                    UK debut (Covent Garden Mar 28)
2015:  24                    Singapore (ION Orchard) — first Asia retail
2016:  48   ##############   China + Hong Kong debuts (Dec 2016)
2017:  63   ################ Japan re-entry, Germany, Korea, Switzerland debuts
2018:  51   #############    France, Sweden, Netherlands, Norway, Ireland debuts
2019:  34                    FY2019 baseline (first per-country 10-K data)
2020:  13
2021:  14
2022:  40                    Spain, HK, Taiwan, Macau, Mexico first 10-K appearance
2023:  23                    Thailand debut
2024:  10                    Cologne (DE) confirmed; Mexico operations acquired
2025:  15                    Italy debut + UK 2025 wave (Manchester, Westfield London, Battersea)
2026:  41   #############    Catch-all (post-FY2025 calendar 2026 openings + 10-K-excluded types)
```

(Total: 593 assigned + 72 popups = 665 ✓; opening activity every fiscal year post-IPO)

## Specific corrections applied via `manual_overrides_lulu.json`

**Year corrections (6):**
- Manchester UK: estimator said 2018 → corrected to **2025** (Retail Gazette: opens Nov 21, 2025)
- Westfield London: 2016 → **2025** (Retail Gazette: Nov 28, 2025)
- Battersea Power Station: 2026 → **2025** (Retail Gazette: Dec 5, 2025)
- American Dream NJ: 2026 → **2025** (ROI-NJ: Dec 2025)
- Bridgewater Commons NJ: 2026 → **2025** (patch.com: Sept 2025)
- Regent Mall Fredericton CA: 2026 → **2022** (regentmall.ca: "lululemon-opening-fall-2022")

**Country corrections (3) — geocoding errors in original scrape:**
- Antwerp: was country=GB (geocoded to "Antwerp Way" street in London) → **BE**, year **2025** (Belgium franchise per Lulu Dec 2025 PR)
- Cologne: was country=FR (geocoded to a building in Rungis, France) → **DE**, year **2024** (Cologne is Köln, Germany)
- Zurich: was country=DE (geocoded to "Zürich Strasse" in Frankfurt) → **CH**, year **2017** (Zurich is in Switzerland; Lulu CH had 1 store throughout FY2019-FY2025)

## Known limitations & sources of imprecision

1. **Pre-FY2019 NA banding is coarse** — stores are placed in 3-4 year bands, not specific years. The 67 at "2007" really means "≤2007" (could be 1998-2007).

2. **Pre-FY2019 international is linearly interpolated** — actual openings may be lumpier (e.g., Australia might have grown 3 stores/year early then 5/year later, but we assumed linear). Probably ±2 years off for most stores.

3. **Store ID = opening order is approximate** — Lulu's IDs are mostly sequential within a country/region but they reissue numbers and skip ranges. Within-country ranking is roughly right; the absolute rank-to-year mapping has small errors.

4. **The 48-store "catch-all" cohort is genuinely uncertain** — these are stores in our scrape that exceed Lulu's latest 10-K count. Could be:
   - Opened after Feb 2026 (Lulu's FY2025 close)
   - Outlets / specials 10-K excludes
   - Country mis-tagging in our scrape (e.g., I noticed "Antwerp" was tagged GB and "Cologne" was tagged FR — both wrong, separate from year_opened issue)

5. **Mexico is in the 10-K (26 stores FY2025) but not in our scrape** — our intl scrape pulled from regional Demandware sites and didn't include Mexico. Adding Mexico stores would require a separate scrape pass.

## How to extend / refine

If you want more precision for a specific store or cohort:

1. **Look up the store's `_year_opened_citation`** to see what method was used.
2. **For specific stores**: web-search the store name + "opening" / "first store" / "grand opening" — major flagships often have news coverage.
3. **For older country debuts**: pull the older 10-Ks (`_lulu_10k_cache/`) and read the narrative for explicit dates ("we opened seven new stores in China" type language).
4. To **override** a year manually, edit `_scripts/estimate_lulu_year_opened.py` and add an override dict similar to Alo's `manual_overrides.json` mechanism.

## Related scripts

| Script | Purpose |
|---|---|
| `_scripts/scrape_lululemon.py` | NA scrape (Next.js SSR `__NEXT_DATA__`) |
| `_scripts/scrape_lululemon_intl.py` | International scrape (Demandware SSR + Nominatim) |
| `_scripts/fetch_lulu_10ks.py` | Downloads 19 10-Ks from SEC EDGAR + extracts country tables |
| `_scripts/estimate_lulu_year_opened.py` | This estimator (10-K rank → year_opened) |
| `data/_lulu_10k_store_counts.json` | Extracted country × year matrix from 10-Ks |
| `data/_lulu_10k_cache/` | Cached 10-K HTML files (don't delete; makes re-runs fast) |
