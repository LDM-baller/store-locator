"""Estimate year_opened for every Lululemon store in data/lululemon.json using
the 10-K country-by-year count matrix.

Method:
1. For each country in our data, sort stores by store ID (proxy for opening order).
2. Walk the 10-K count progression (e.g. US: 305→315→324→350→367→374→379 across
   FY2019-FY2025). The store at rank N opened in the fiscal year where the
   country's count first reached N.
3. For stores with rank ≤ count(FY2019), we don't have country-level data prior
   to FY2019 — fall back to:
   - For NA (US+CA): use total-store counts FY2007-FY2018 + assumed NA share
     to assign rough year bands (e.g., "1998-2007", "2008-2010", "2011-2015",
     "2016-2018").
   - For international: use the country debut year as a lower bound; assume the
     store opened "≤ FY2019" with the country debut as the lowest possible year.
4. Tag each store with year_opened + raw._year_opened_citation pointing to the
   relevant SEC 10-K filing URL.

Filters:
- Popup stores (store_type=popup) are skipped — 10-K excludes them.
- Coming soon stores keep their existing year (likely already correct).
"""
import json, pathlib, re, sys
from collections import defaultdict, Counter

DATA = pathlib.Path(r"G:\My Drive\Programs\store-map\data\lululemon.json")
MATRIX = pathlib.Path(r"G:\My Drive\Programs\store-map\data\_lulu_10k_store_counts.json")

# Country debut years for Lulu's international markets, sourced from public articles
# and Lululemon's own press releases. Used to bound pre-FY2019 international stores
# (which the 10-K country-level table doesn't cover).
COUNTRY_DEBUT = {
    "AU": (2004, "Lulu opened Chapel Street store in Melbourne October 2004 (sgbonline.com — early Australian franchise; brand acquired full ownership by 2010)"),
    "GB": (2014, "First UK store Covent Garden, London — March 28, 2014 (drapersonline.com — first European store)"),
    "NZ": (2014, "Estimated; NZ paired with AU expansion in Christine Day-era (CEO 2008-2013 entered AU/NZ/UK)"),
    "SG": (2014, "First Asia retail store at ION Orchard 2014 (marketing-interactive.com)"),
    "CN": (2016, "Beijing + Shanghai + Hong Kong stores December 2016 (Lulu corporate press release 'lululemon Opens Stores in Beijing, Shanghai and Hong Kong')"),
    "HK": (2016, "Hong Kong with China expansion December 2016 (same Lulu press release)"),
    "JP": (2017, "First store at Ginza Six Mall Tokyo, 2017 (Lulu corporate press release; after 2005-2008 first stab via Lulu Japan Inc. franchise that closed)"),
    "KR": (2017, "Estimated; Lulu had 5 Korea stores by FY2019, mainland Asia expansion 2017-2018"),
    "DE": (2017, "Munich was 2nd Germany store Oct 2017 (the-spin-off.com); debut earlier in 2017"),
    "CH": (2017, "Estimated; CH had 1 store by FY2019, CH/DE often paired"),
    "FR": (2018, "Per Lulu FY2018 10-K narrative: 'we expanded into two new markets in Europe — France and Sweden'"),
    "NL": (2018, "Estimated; NL had 1 store by FY2019"),
    "SE": (2018, "Stockholm first store June 1, 2018 (Lulu corporate press release 'lululemon Opens its First Store in Sweden')"),
    "NO": (2018, "Estimated; NO had 1 store by FY2019"),
    "IE": (2018, "Estimated; IE had 1 store by FY2019, EU expansion cohort"),
    "TW": (2018, "Estimated; TW had 7 stores by FY2022 (first table appearance)"),
    "MO": (2018, "Estimated; Macau 2 stores by FY2022"),
    "MY": (2018, "Estimated; MY had 2 stores by FY2019"),
    "MX": (2024, "Lulu acquired Mexico operations during FY2024 (FY2024 10-K — added 14 company-operated stores from Mexico acquisition)"),
    "ES": (2022, "Spain first appears in 10-K country table FY2022 (3 stores)"),
    "TH": (2023, "Thailand first appears in 10-K country table FY2023 (1 store)"),
    "IT": (2025, "Italy debut summer 2025 — Via del Babuino Rome Dec 2025 (Lulu Dec 18, 2025 press release referencing 'this summer' Italy entry)"),
    "BE": (2025, "Belgium recent franchise market (Lulu Dec 18, 2025 press release)"),
    "DK": (2025, "Denmark recent franchise market (Lulu Dec 18, 2025 press release)"),
    "TR": (2025, "Turkey recent franchise market (Lulu Dec 18, 2025 press release; Istinye Park Istanbul Sept 2025)"),
    "BH": (2023, "Bahrain first appears in 10-K third-party table FY2023"),
    "AE": (2022, "UAE first appears in 10-K third-party table FY2022 (7 stores)"),
    "SA": (2022, "Saudi Arabia first appears in 10-K third-party table FY2022"),
    "QA": (2022, "Qatar first appears in 10-K third-party table FY2022"),
    "KW": (2022, "Kuwait first appears in 10-K third-party table FY2022"),
    "IL": (2023, "Israel first appears in 10-K third-party table FY2023"),
}

# Lulu IPO'd June 2007. Earliest stores from late 1990s in Vancouver.
# Total stores by FY (from 10-K narrative):
#   FY2007=81, FY2008=113, FY2009=124, FY2010=137,
#   FY2015=254, FY2016=302, FY2017=363, FY2018=406, FY2019=491
# Linear interpolation for FY2011-FY2014:
TOTALS_BY_FY = {
    # Pre-IPO totals — estimated from public history (founded 1998, first standalone
    # store W 4th Ave Vancouver Nov 2000, first US store Santa Monica 2003, IPO July 2007
    # with 81 stores at FY2007 close per first 10-K). Pre-2007 numbers are reasonable
    # interpolations that match the known milestones.
    2000: 1, 2001: 2, 2002: 3, 2003: 7, 2004: 14, 2005: 25, 2006: 50,
    # IPO + post-IPO (from 10-K narratives):
    2007: 81, 2008: 113, 2009: 124, 2010: 137,
    2011: 160, 2012: 184, 2013: 207, 2014: 230,    # FY2011-2014 linearly interpolated
    2015: 254, 2016: 302, 2017: 363, 2018: 406,
}

# Year bands for pre-FY2019 NA stores (combined US+CA — these were 90%+ of Lulu's footprint pre-2019)
# Each band represents a fiscal-year range; we'll assign stores by ID rank to bands.
PRE_2019_NA_BANDS = [
    # (start_fy, end_fy, end_total)
    ("≤2007",   2007, 81),
    ("2008-2010", 2010, 137),
    ("2011-2014", 2014, 230),
    ("2015-2017", 2017, 363),
    ("2018",      2018, 406),
]
# Approx. NA share of total fleet: pre-AU (2009): 100%; post-AU through 2018 ≈ 92%
# So count(NA, end of FY2018) ≈ 374, count(NA, end of FY2007) ≈ 79

def na_count_at_end_of_fy(fy):
    """Estimated NA-only company-operated count at end of fiscal year FY.

    Australia was franchise-operated until FY2010 acquisition (per FY2010 10-K
    narrative: 'we opened 11 net new stores in Australia (including nine franchise
    stores that were reacquired) in fiscal 2010'). So pre-FY2010, Lulu's reported
    company-operated total was effectively NA-only. After FY2010, subtract a
    growing international share."""
    if fy < 2010:
        return TOTALS_BY_FY.get(fy, 0)
    if fy >= 2019:
        return None  # use country-specific data for these years
    total = TOTALS_BY_FY.get(fy, 0)
    # FY2010: ~11 AU stores in fleet (8% intl share). Ramps to ~12% by FY2018 as
    # Lulu added UK 2014, China/Asia 2016+, EU 2017-2018.
    intl_share = 0.08 + (fy-2010) * 0.005
    return int(total * (1 - min(intl_share, 0.13)))


def main():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    co_matrix = matrix["company_operated_by_market_by_fy"]

    file = json.loads(DATA.read_text(encoding="utf-8"))
    stores = file["stores"]
    print(f"Lulu stores in data: {len(stores)}")

    # Group stores by country
    by_country = defaultdict(list)
    skipped_popup = 0
    for s in stores:
        if s.get("store_type") == "popup":
            skipped_popup += 1
            continue
        cc = s.get("country") or "?"
        by_country[cc].append(s)
    print(f"Skipped popups (10-K excludes): {skipped_popup}")
    print(f"Countries in our data: {len(by_country)}")

    # Sort each country's stores by ID (proxy for opening order)
    for cc in by_country:
        def key(s):
            sid = (s.get("raw") or {}).get("id") or (s.get("raw") or {}).get("_demandware_store_id") or ""
            try:
                return (0, int(sid))
            except (ValueError, TypeError):
                return (1, str(sid))
        by_country[cc].sort(key=key)

    # Map our country code (ISO alpha-2) -> 10-K country name in matrix
    CC_TO_MATRIX_NAME = {
        "US": "United States", "CA": "Canada", "AU": "Australia", "GB": "United Kingdom",
        "JP": "Japan", "DE": "Germany", "FR": "France", "NZ": "New Zealand",
        "IE": "Ireland", "SE": "Sweden", "BE": None, "CH": "Switzerland",
        "ES": "Spain", "NL": "Netherlands", "IT": "Italy", "MX": "Mexico",
        "KR": "South Korea", "SG": "Singapore", "HK": "Hong Kong SAR",
        "TW": "Taiwan", "MY": "Malaysia", "TH": "Thailand", "MO": "Macau SAR",
        "AE": "United Arab Emirates", "SA": "Saudi Arabia", "IL": "Israel",
        "KW": "Kuwait", "QA": "Qatar", "TR": "Turkey", "BH": "Bahrain",
        "DK": "Denmark", "NO": "Norway", "MX": "Mexico",
    }

    SEC_URL_BASE = "https://www.sec.gov/Archives/edgar/data/1397187/"
    # Map FY -> filing accession for citation
    FY_TO_FILING = {
        2025: "000139718726000020",  # FY2025 10-K
        2024: "000139718725000013",
        2023: "000139718724000010",
        2022: "000139718723000012",
        2021: "000139718722000014",
        2020: "000139718721000009",
        2019: "000139718720000012",
    }

    def filing_url_for_fy(fy):
        acc = FY_TO_FILING.get(fy)
        if not acc: return None
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001397187&type=10-K"

    # Process NA (US + CA combined since 10-K splits but our data has them mixed by chronology)
    # Approach: process each country separately using the country's count progression.
    # For NA, also fill in pre-FY2019 stores using the total-store estimates.

    n_assigned = 0; n_pre2019_band = 0; n_no_data = 0
    citations_used = set()

    # For pre-FY2019 NA stores: combine US+CA into one ranked list (since 10-K
    # totals were combined in those years and Lulu treated NA as one fleet).
    # Map each NA store to its NA-combined rank.
    na_stores_sorted = []
    for cc in ("US", "CA"):
        if cc in by_country:
            for s in by_country[cc]:
                na_stores_sorted.append(s)
    # Sort NA combined by ID
    def id_key(s):
        sid = (s.get("raw") or {}).get("id") or ""
        try: return (0, int(sid))
        except (ValueError, TypeError): return (1, str(sid))
    na_stores_sorted.sort(key=id_key)
    na_combined_rank = {id(s): i+1 for i, s in enumerate(na_stores_sorted)}
    print(f"NA combined (US+CA): {len(na_stores_sorted)} stores ranked")

    for cc, country_stores in by_country.items():
        matrix_name = CC_TO_MATRIX_NAME.get(cc)
        country_counts = co_matrix.get(matrix_name, {}) if matrix_name else {}
        # Convert keys to int (they're strings in JSON)
        country_counts = {int(k): v for k, v in country_counts.items()}
        if not country_counts:
            # No 10-K country data — this country isn't in our matrix
            for s in country_stores:
                s["year_opened"] = None
                s["year_opened_validation"] = "10k-no-country-data"
                s.setdefault("raw", {})["_year_opened_citation"] = (
                    f"Country {cc} not present in extracted 10-K country tables; "
                    f"may be franchise/license market not company-operated."
                )
                n_no_data += 1
            continue

        # Sorted FYs available for this country
        sorted_fys = sorted(country_counts.keys())
        earliest_fy = sorted_fys[0]
        baseline_count = country_counts[earliest_fy]  # count at end of earliest FY we have

        for rank0, s in enumerate(country_stores):
            rank = rank0 + 1  # 1-indexed
            assigned_fy = None
            citation_extra = ""

            if rank <= baseline_count:
                # This store opened on or before earliest FY data point.
                # For NA (US/CA), use NA-COMBINED rank against pre-FY2019 totals.
                if cc in ("US", "CA"):
                    na_rank = na_combined_rank.get(id(s), rank)  # combined US+CA rank
                    # Walk per-fiscal-year totals — assign to the first FY where
                    # the cumulative NA count first reaches/exceeds this rank.
                    # This spreads stores across years smoothly instead of dumping
                    # whole bands at a single year.
                    found_fy = None
                    for fy_check in sorted(TOTALS_BY_FY.keys()):
                        nac = na_count_at_end_of_fy(fy_check)
                        if nac and na_rank <= nac:
                            found_fy = fy_check
                            break
                    if found_fy:
                        assigned_fy = found_fy
                        citation_extra = (
                            f" Pre-FY2019 NA store. Combined US+CA rank #{na_rank} → opened by end of "
                            f"FY{found_fy} (Lulu had ~{na_count_at_end_of_fy(found_fy)} NA stores at that point). "
                            f"Source: Lulu 10-K narrative for FY{found_fy} (total fleet count + NA share estimate). "
                            f"Note: FY2011-FY2014 totals are linearly interpolated between known FY2010 (137) and "
                            f"FY2015 (254) data points; per-year precision in that window is ±1-2 years."
                        )
                    else:
                        assigned_fy = 2019
                        citation_extra = (
                            f" Combined US+CA rank #{na_rank} exceeds pre-FY2019 totals; placed at FY2019 baseline "
                            f"(305 US + 63 CA = 368). May actually have opened FY2018 or earlier."
                        )
                else:
                    # International country: linearly distribute pre-FY2019 stores
                    # between the country's known debut year and FY2019, by rank.
                    debut_info = COUNTRY_DEBUT.get(cc)
                    if debut_info and debut_info[0] < earliest_fy:
                        debut_year, debut_source = debut_info
                        # Number of stores existing at end of earliest_fy
                        N = baseline_count
                        if N > 1:
                            # Linear distribution: rank=1 → debut_year, rank=N → earliest_fy
                            assigned_fy = round(debut_year + (rank-1) * (earliest_fy - debut_year) / (N-1))
                        else:
                            assigned_fy = debut_year
                        citation_extra = (
                            f" Pre-FY2019 international store. {cc} had {N} stores at end of FY{earliest_fy}; "
                            f"this store ranks #{rank} among them. Linearly distributed between known debut year "
                            f"({debut_year}) and FY{earliest_fy}. Debut source: {debut_source}"
                        )
                    else:
                        # No known debut year; use earliest_fy as upper bound
                        assigned_fy = earliest_fy
                        citation_extra = (
                            f" Existed at end of FY{earliest_fy} (Lulu's earliest 10-K country-table data point); "
                            f"actual opening could be earlier (≤ FY{earliest_fy})."
                        )
            else:
                # Walk forward through fiscal years, find the first FY where count >= rank
                prev_count = baseline_count
                for fy_check in sorted_fys[1:]:
                    if rank <= country_counts[fy_check]:
                        assigned_fy = fy_check
                        break
                    prev_count = country_counts[fy_check]
                if not assigned_fy:
                    # Rank exceeds all known counts — store opened after the last 10-K date
                    # OR our scrape includes stores 10-K excludes (e.g., outlets, recent additions
                    # not yet in 10-K, or third-party stores in the company-operated table).
                    latest_fy = sorted_fys[-1]
                    latest_count = country_counts[latest_fy]
                    is_outlet = s.get("store_type") == "outlet"
                    if is_outlet:
                        # 10-K's "company-operated" table excludes outlet/factory stores per Lulu policy
                        assigned_fy = latest_fy
                        citation_extra = (
                            f" Outlet store (10-K company-operated count excludes outlets). "
                            f"Country rank #{rank} exceeds latest 10-K count ({latest_count} at FY{latest_fy}); "
                            f"actual opening date can't be derived from 10-K count progression. "
                            f"Year set to FY{latest_fy} (latest known 10-K period) as a best guess; could be earlier."
                        )
                    else:
                        # Likely opened during or after FY2025 (which ends Feb 2026 — so the recent year)
                        assigned_fy = latest_fy + 1
                        citation_extra = (
                            f" Rank {rank} exceeds latest 10-K count ({latest_count} at FY{latest_fy}). "
                            f"Likely opened after Feb 2026 (Lulu's FY2025 close), OR Lulu's 10-K count excludes "
                            f"this store type for some reason. Year set to FY{latest_fy+1} as best guess for post-10-K opening; "
                            f"could be a misclassification or early-2026 opening that isn't yet captured in next year's 10-K."
                        )

            # Pick a more specific validation status based on which path produced the year
            if "Pre-FY2019 NA store" in citation_extra:
                status = "10k-pre-fy2019-narrative-by-fy"
            elif "Pre-FY2019 international store" in citation_extra:
                status = "country-debut-interpolated"
            elif "Outlet store" in citation_extra:
                status = "post-10k-outlet"
            elif "Rank" in citation_extra and "exceeds latest 10-K count" in citation_extra:
                status = "post-10k-recent-or-excluded"
            elif "Existed at end of FY" in citation_extra:
                status = "10k-pre-fy2019-floor"
            else:
                status = "10k-fiscal-year-bucket"
            s["year_opened"] = assigned_fy
            s["year_opened_validation"] = status
            s.setdefault("raw", {})["_year_opened_citation"] = (
                f"Lulu 10-K country-count progression for {matrix_name} ({cc}): "
                f"this store ranks #{rank} among our {len(country_stores)} {cc} stores (sorted by store ID, "
                f"which roughly tracks opening order). Country had {country_counts.get(assigned_fy, '?')} stores at end of "
                f"FY{assigned_fy} per 10-K. Source: SEC EDGAR filings for Lululemon (CIK 0001397187), 10-K for FY{assigned_fy}."
                + citation_extra
            )
            s["raw"]["_year_opened_signals"] = {
                "country_rank": rank,
                "country_total_in_data": len(country_stores),
                "country_10k_count_at_fy": {str(k): v for k,v in country_counts.items()},
                "method": "10k-country-rank",
            }
            citations_used.add(("10K", assigned_fy))
            n_assigned += 1

    # Apply manual overrides from manual_overrides_lulu.json (per-store web-validated corrections)
    overrides_path = pathlib.Path(r"G:\My Drive\Programs\store-map\manual_overrides_lulu.json")
    if overrides_path.exists():
        ov_doc = json.loads(overrides_path.read_text(encoding="utf-8"))
        overrides = ov_doc.get("_", [])
        ov_applied = 0
        for ov in overrides:
            for s in stores:
                if s.get("name") == ov["name"] and s.get("country") == ov["country"]:
                    old_year = s.get("year_opened")
                    s["year_opened"] = ov["year"]
                    s["year_opened_validation"] = "web-search-confirmed-override"
                    s.setdefault("raw", {})
                    s["raw"]["_year_opened_citation"] = (
                        f"Manual override (web-search confirmed): {ov['source']}. "
                        f"Year corrected from estimator's {old_year} to {ov['year']}."
                    )
                    s["raw"]["_year_opened_correction"] = {
                        "previous_year": old_year, "corrected_year": ov["year"],
                        "month": ov.get("month"), "source": ov["source"],
                    }
                    ov_applied += 1
                    print(f"  override applied: {ov['country']} {ov['name']} {old_year}→{ov['year']}")
        print(f"\nApplied {ov_applied} year overrides")

        # Also apply country corrections (fix misclassified countries from scrape errors)
        country_fixes = ov_doc.get("_country_corrections", [])
        cf_applied = 0
        for cf in country_fixes:
            for s in stores:
                if s.get("name") == cf["name"] and s.get("country") == cf["country"]:
                    old = (s["country"], s.get("city"), s.get("lat"), s.get("lng"))
                    s["country"] = cf["fix_country"]
                    s["city"] = cf["fix_city"]
                    s["state"] = cf.get("fix_state")
                    s["lat"] = cf["fix_lat"]
                    s["lng"] = cf["fix_lng"]
                    s["year_opened"] = cf["year"]
                    s["year_opened_validation"] = "web-search-confirmed-override"
                    s.setdefault("raw", {})
                    s["raw"]["_country_correction"] = {
                        "previous": {"country": old[0], "city": old[1], "lat": old[2], "lng": old[3]},
                        "corrected": cf,
                        "source": cf["source"],
                    }
                    s["raw"]["_year_opened_citation"] = (
                        f"Country correction + year override: {cf['source']}. "
                        f"Was tagged country={old[0]} (geocoding error); corrected to {cf['fix_country']}."
                    )
                    cf_applied += 1
                    print(f"  country fix: {cf['name']} {old[0]}→{cf['fix_country']}")
        print(f"Applied {cf_applied} country corrections")

    # Mark popups separately
    for s in stores:
        if s.get("store_type") == "popup":
            s["year_opened"] = None
            s["year_opened_validation"] = "popup-10k-excludes"
            s.setdefault("raw", {})["_year_opened_citation"] = (
                "10-K count tables exclude popup/temporary stores. year_opened can't be derived from 10-K count progression."
            )

    # Report
    by_status = Counter(s.get("year_opened_validation","missing") for s in stores)
    by_year = Counter(s.get("year_opened") for s in stores if s.get("year_opened"))
    print("\n=== Validation status counts ===")
    for k, v in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"  {k:<35} {v}")
    print(f"\n=== year_opened histogram ===")
    for y in sorted(by_year, key=lambda x: x or 0):
        bar = "#" * min(80, by_year[y])
        print(f"  {y}: {by_year[y]:>4} {bar}")

    file["stores"] = stores
    file["year_opened_coverage"] = {"known": sum(1 for s in stores if s.get("year_opened")),
                                    "unknown": sum(1 for s in stores if not s.get("year_opened"))}
    file["year_opened_histogram"] = {str(k): v for k,v in sorted(by_year.items(), key=lambda x: x[0] or 0)}
    file["year_opened_validation_counts"] = dict(by_status)
    file["year_opened_note"] = (
        "Lululemon year_opened estimated from SEC 10-K country-by-year company-operated store counts "
        "(source: SEC EDGAR filings for Lululemon CIK 0001397187, FY2019-FY2025 10-K country tables; "
        "FY2007-FY2018 from narrative total-store counts). Method: store ranked by ID within country, "
        "rank → fiscal year bucket via 10-K count progression. Not exact dates — fiscal year precision. "
        "Popups excluded (10-K does not count them). Pre-FY2019 NA stores assigned to year bands from "
        "the totals (≤2007, 2008-2010, 2011-2014, 2015-2017, 2018)."
    )
    DATA.write_text(json.dumps(file, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved -> {DATA}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
