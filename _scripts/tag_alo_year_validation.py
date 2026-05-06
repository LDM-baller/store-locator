"""Tag every Alo store with a validation status indicating how confident we are
in its year_opened. After the web-search validation pass, each store falls
into one of these buckets:

  - 'web-search-corrected'    : year was changed based on news/blog evidence (15)
  - 'web-search-confirmed'    : year was confirmed by news/blog evidence, no change (~12)
  - 'wayback-store-page'      : earliest CDX snapshot of the dedicated -store URL
  - 'builder-createddate-only': year is from Alo's Builder.io CMS createdDate but
                                 NOT individually web-search validated. Reliable
                                 for stores added after the ~2023 CMS migration;
                                 may overstate the year for older stores migrated
                                 from a previous CMS.
  - 'unverified'              : couldn't establish a year at all (rare/none)

Writes a top-level `year_opened_validation_counts` summary field.
"""
import json, pathlib, sys
from collections import Counter

DATA = pathlib.Path(r"G:\My Drive\Programs\store-map\data\alo-yoga.json")

# Stores explicitly validated against news/blog sources during the 2026-05-06 web-search pass.
# Map (name, country) -> 'web-search-corrected' (year changed) or 'web-search-confirmed' (verified, no change).
WEB_SEARCH_CONFIRMED = {
    # Year confirmed; no change
    ("Kings Road", "GB"):                          ("web-search-confirmed", "Retail Gazette 2023/11 — UK debut Nov 17 2023"),
    ("Artz Pedregal", "MX"):                       ("web-search-confirmed", "estilodf.tv — Mexico debut May 4 2023"),
    ("Antara", "MX"):                              ("web-search-confirmed", "estilodf.tv — Mexico City Sept 2023"),
    ("TLV FASHION MALL", "IL"):                    ("web-search-confirmed", "Globes — Israel debut April 2023"),
    ("DIZENGOFF SQUARE", "IL"):                    ("web-search-confirmed", "Globes — Israel debut April 2023"),
    ("Shops at Hudson Yards", "US"):               ("web-search-confirmed", "Hudson Yards official — grand opening Sept 29 2023; Alo's 59th US store"),
    ("CF - Pacific Centre", "CA"):                 ("web-search-confirmed", "retail-insider.com 2023/05 — Vancouver debut spring 2023"),
    ("Chinook Centre", "CA"):                      ("web-search-confirmed", "retail-insider.com — Calgary 2023"),
    ("West Edmonton Mall", "CA"):                  ("web-search-confirmed", "retail-insider.com — Edmonton August 2023"),
    ("Southgate Centre", "CA"):                    ("web-search-confirmed", "retail-insider.com — Edmonton September 2023"),
    ("Toronto Eaton Centre", "CA"):                ("web-search-confirmed", "retail-insider.com — Toronto 2023"),
    ("Houston Galleria", "US"):                    ("web-search-confirmed", "communityimpact.com 2023/11 — Houston Galleria November 2023"),
    ("St. Johns Town Center", "US"):               ("web-search-confirmed", "Jax Daily Record 2023/06 + 2023/08 — opened summer 2023"),
    ("Newbury Street", "US"):                      ("web-search-confirmed", "Luma Alo Boston — grand opening November 17-19"),
    ("Prudential Center", "US"):                   ("web-search-confirmed", "thebostoncalendar.com — Sip Strut + Shop event April 14 2023"),
    ("Lenox Square", "US"):                        ("web-search-confirmed", "tonetoatl.com 2022/12 — in development late 2022, opened 2023"),
    # Older flagships confirmed via Wayback per-store-URL
    ("Palisades Village", "US"):                   ("wayback-store-page", "earliest CDX snapshot 2021"),
    ("The Grove", "US"):                           ("wayback-store-page", "earliest CDX snapshot 2021"),
    ("Santa Monica", "US"):                        ("wayback-store-page", "earliest CDX snapshot 2021"),
    ("La Jolla", "US"):                            ("wayback-stores-directory", "earliest mention 2020"),
    ("Fashion Valley", "US"):                      ("wayback-store-page", "earliest CDX snapshot 2022"),
    ("Stanford", "US"):                            ("wayback-store-page", "earliest CDX snapshot 2022"),
    ("Aspen", "US"):                               ("wayback-store-page", "earliest CDX snapshot 2022"),
    ("Oakbrook", "US"):                            ("wayback-store-page", "earliest CDX snapshot 2022"),
    ("SOHO Flagship", "US"):                       ("wayback-store-page", "earliest CDX snapshot 2022"),
    ("Williamsburg", "US"):                        ("wayback-store-page", "earliest CDX snapshot 2022"),

    # Round-3 web-search confirmations (2026-05-06): 20-store spot-check of 2024-2026 cohort.
    ("Regent Street", "GB"):                       ("web-search-confirmed", "BoF + theretailbulletin.com — London Regent Street flagship August 2024"),
    ("Brompton Road", "GB"):                       ("web-search-confirmed", "fashionunited UK — opened 2024 (former Ted Baker site)"),
    ("Grafton Street", "IE"):                      ("web-search-confirmed", "fashionunited.uk 2024/12 — Ireland debut December 2024"),
    ("The Dubai Mall", "AE"):                      ("web-search-confirmed", "alshaya.com + whatson.ae — UAE debut Feb 23 2024"),
    ("The Galleria Al Maryah Island", "AE"):       ("web-search-confirmed", "alshaya.com — UAE expansion to Abu Dhabi 2024"),
    ("Doha Festival City", "QA"):                  ("web-search-confirmed", "alshaya.com + qatarprnetwork — Qatar debut June 8 2024"),
    ("Senayan City", "ID"):                        ("web-search-confirmed", "whatsnewindonesia.com — Indonesia debut March 29 2024"),
    ("Andares", "MX"):                             ("web-search-confirmed", "playersoflife.com — Guadalajara August 29 2024 (5th Mexico store)"),
    ("Antea", "MX"):                               ("web-search-confirmed", "FashionNetwork MX — Querétaro July 2024"),
    ("Punto Valle", "MX"):                         ("web-search-confirmed", "FashionNetwork MX — Monterrey 2024 (interior Mexico debut)"),
    ("Beirut Souk", "LB"):                         ("web-search-confirmed", "Wikipedia + beirut.com — Lebanon debut March 2025"),
    ("Greenbelt Mall", "PH"):                      ("web-search-confirmed", "retailnews.asia + rappler.com — Philippines debut May 2025"),
    ("Mandarin Oriental, Bodrum", "TR"):           ("web-search-confirmed", "Wikipedia + hal.news — Turkey beach club opened May/June 2025"),
    ("JK Iguatemi", "BR"):                         ("web-search-confirmed", "WWD + modaes.com — Brazil debut Q1 2025 (first South America)"),
    ("Marina Bay Sands", "SG"):                    ("web-search-confirmed", "ELLE Singapore + jingdaily — Singapore debut fall 2025"),
    ("Dosan", "KR"):                               ("web-search-confirmed", "jingdaily.com + WWD — Seoul flagship July 4 2025 (six-floor)"),
    ("Lotte Main", "KR"):                          ("web-search-confirmed", "Seoul Economy Daily — Lotte Department Store main, August 2025"),
    ("Hyundai Seoul", "KR"):                       ("web-search-confirmed", "Seoul Economy Daily — The Hyundai Seoul, September 2025"),
    ("Manchester", "GB"):                          ("web-search-confirmed", "Retail Gazette 2025/10 — Manchester opens November 21 2025"),
    ("Westfield London", "GB"):                    ("web-search-confirmed", "Retail Gazette 2025/10 — Westfield London opens November 28 2025"),
    ("Battersea Power Station", "GB"):             ("web-search-confirmed", "Retail Gazette 2025/10 — Battersea opens December 5 2025"),

    # Round-4 confirmations (2026-05-06): 2025/2026 cohort batch validation.
    ("Wolvenstraat 9 Streets", "NL"):              ("web-search-confirmed", "amsterdamnow.com + numeronetherlands.com — opened June 27 2025 on Wolvenstraat (185m²)"),
    ("PC Hooftstraat", "NL"):                      ("web-search-confirmed", "linkedin B&O Retail + numeronetherlands.com — flagship Q3 2025, 650m² on PC Hooftstraat Amsterdam"),
    ("Via Del Babuino", "IT"):                     ("web-search-confirmed", "ilmessaggero.it + glosh.it — Italy debut December 19 2025, Rome (Alo's 12th European store)"),
    ("ICONSIAM", "TH"):                            ("web-search-confirmed", "hashtaglegend.com — 2nd Bangkok store, 2025 (after EmQuartier 2023)"),
    ("Central Floresta", "TH"):                    ("web-search-confirmed", "hisopartyofficial.com + gourmetandcuisine.com — 2nd Thailand store, Phuket Floresta 2025"),
    ("Hannam", "KR"):                              ("web-search-confirmed", "Seoul Economy Daily — Hannam-dong (Yongsan-gu) flagship in 2025 Korea expansion"),
    ("Lotte Jamsil", "KR"):                        ("web-search-confirmed", "Seoul Economy Daily — Lotte Department Store, 2025 Korea expansion"),
    ("Andino Mall", "CO"):                         ("web-search-confirmed", "FashionNetwork CO + larepublica.co — Colombia debut 2025 at Centro Comercial Andino, Bogotá"),
    ("Diamond Mall", "BR"):                        ("web-search-confirmed", "modaes.com — 2025 Latam expansion (after JK Iguatemi São Paulo earlier in 2025)"),
    ("Blue Mall", "DO"):                           ("web-search-confirmed", "listindiario.com 2025/05/09 — Dominican Republic debut May 2025"),
    ("Multiplaza Mall", "PA"):                     ("web-search-confirmed", "modaes.com — 2025 Latam expansion (Brazil/Colombia/Peru/Panama batch)"),
    ("Jockey Plaza", "PE"):                        ("web-search-confirmed", "peru-retail.com — Peru debut 2025 (Bogotá opened ~1 week later)"),
    ("Marassi Galleria", "BH"):                    ("web-search-confirmed", "platinumlist.net — Bahrain debut 2025 at Marassi Galleria"),
    ("Solitaire Mall", "SA"):                      ("web-search-confirmed", "alshaya.com — Solitaire Mall Riyadh, February 2025"),
    ("Istinye Park", "TR"):                        ("web-search-confirmed", "alshaya.com — Istanbul Istinye Park, September 2025"),
    ("The Summit Birmingham", "US"):               ("web-search-confirmed", "Mitchell Royel + chainstoreage — Alabama debut Summer 2025 at The Summit"),
    ("American Dream", "US"):                      ("web-search-confirmed", "ROI-NJ 2025/12 — opened December 2025, Alo's 7th NJ store at East Rutherford"),
    ("Bridgewater Commons", "US"):                 ("web-search-confirmed", "patch.com — Bridgewater NJ store opened September 2025"),
    ("Burlingame", "US"):                          ("web-search-confirmed", "kron4.com + yahoo.com — Bay Area Burlingame 2025"),
    ("Mall of America", "US"):                     ("web-search-confirmed", "mallofamerica.com press release + chainstoreage — early Q3 2025, Alo's 2nd Minnesota store"),
    ("Westfield Century City", "US"):              ("web-search-confirmed", "linkedin.com (Allie H. 09/2024) — opened September 2024 outside Bloomingdales valet entrance"),

    ("Brickell City Centre", "US"):                ("web-search-confirmed", "luma.com — grand opening weekend May 23-25 2025 at Brickell City Centre Miami"),

    # 2026 Coming Soon — verified as planned future openings
    ("Chatswood Chase - Coming Soon", "AU"):       ("web-search-confirmed", "Inside Retail Australia 2026/02 + Ragtrader — Australia debut 2026 alongside Bondi"),
    ("Westbourne Grove - Coming Soon", "GB"):      ("web-search-confirmed", "Retail Gazette 2025/10 — part of Alo's UK 4-store expansion plan; opens 2026"),
    ("La Croisette - Coming Soon", "FR"):          ("web-search-confirmed", "FashionNetwork — 2026 French expansion (alongside Champs-Élysées Paris flagship)"),
    ("Rue Gambetta - Coming Soon", "FR"):          ("web-search-confirmed", "FashionNetwork — 2026 French expansion (Saint Tropez)"),
}

# Corrections applied via web search — already in raw._year_opened_correction.
# Listed here so they get tagged 'web-search-corrected'.
WEB_SEARCH_CORRECTIONS = {
    # Rounds 1-2 (2023-cohort cleanup)
    ("Kingdom Mall", "SA"),       ("Avenues 4 (Grand Plaza)", "KW"),
    ("Bloor", "CA"),              ("Yorkdale", "CA"),
    ("Boston Seaport", "US"),     ("Beverly Hills Flagship", "US"),
    ("Westchester", "US"),        ("NorthPark Center", "US"),
    ("Rockefeller", "US"),        ("Kierland Commons", "US"),
    ("Manhattan Village", "US"),  ("The Gardens", "US"),
    ("Cherry Creek", "US"),       ("Park Meadows", "US"),
    # Round-3 (2024-2026 spot-check)
    ("Emquartier", "TH"),         ("Mitikah", "MX"),
    ("Santa Fe", "MX"),           ("Satelite", "MX"),
    ("Angelopolis", "MX"),        ("Leeds", "GB"),
    # Round-4 (2025-2026 full pass)
    ("Oakridge Park - Coming Soon", "CA"),
}

# Stores I attempted to validate via web search but couldn't find a definitive
# year — recorded so the report can flag them as "tried, no evidence".
WEB_SEARCH_NOT_FOUND = {
    ("Glilot", "IL"):           "No specific opening-date coverage found in basic search. Builder.io createdDate=2025; not contradicted but not corroborated.",
    ("360 Mall", "KW"):         "Luma event listing confirms it as Alo's 2nd Kuwait store; specific opening date not in basic search. Builder.io createdDate=2025; consistent with Kuwait expansion timeline.",
    ("Brookfield Place - Coming Soon", "US"): "Job postings confirm imminent opening. No public grand-opening date in basic search. Builder.io createdDate=2026; consistent with active 'coming soon' status.",
}

def main():
    file = json.loads(DATA.read_text(encoding="utf-8"))
    counts = Counter()
    unverified_2023 = []

    for s in file["stores"]:
        key = (s.get("name"), s.get("country"))
        raw = s.setdefault("raw", {})

        citation = None
        if key in WEB_SEARCH_CORRECTIONS or raw.get("_year_opened_source") == "web-search-correction":
            status = "web-search-corrected"
            # citation already lives in raw._year_opened_correction.source for these
            citation = (raw.get("_year_opened_correction") or {}).get("source")
        elif key in WEB_SEARCH_CONFIRMED:
            status, citation = WEB_SEARCH_CONFIRMED[key]
        elif raw.get("_year_opened_source") == "wayback-earlier-than-builder-migration":
            status = "wayback-store-page"
            citation = f"Wayback Machine — earliest snapshot {raw.get('_year_opened_snapshot') or ''}"
        elif raw.get("_year_opened_source") in ("wayback-store-page", "wayback-stores-directory"):
            status = "wayback-store-page"
            citation = f"Wayback Machine — earliest snapshot {raw.get('_year_opened_snapshot') or ''}"
        elif key in WEB_SEARCH_NOT_FOUND:
            status = "web-search-attempted-not-found"
            citation = WEB_SEARCH_NOT_FOUND[key]
        elif s.get("year_opened"):
            status = "builder-createddate-only"
            citation = "Alo Builder.io CMS createdDate (not individually web-validated)"
            if s.get("year_opened") == 2023:
                unverified_2023.append(s)
        else:
            status = "unverified"

        s["year_opened_validation"] = status
        if citation:
            raw["_year_opened_citation"] = citation
        counts[status] += 1

    file["year_opened_validation_counts"] = dict(counts)
    DATA.write_text(json.dumps(file, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== Validation status counts ===")
    for k, v in counts.most_common():
        print(f"  {k:<35} {v:>3}")

    print(f"\n=== {len(unverified_2023)} stores at year_opened=2023 not individually web-validated ===")
    print("(Builder.io createdDate only. Could still hide a few 2022 stragglers.)\n")
    by_state = {}
    for s in unverified_2023:
        by_state.setdefault(s.get("state") or s.get("country"), []).append(s["name"])
    for st in sorted(by_state, key=lambda k: -len(by_state[k])):
        print(f"  {st} ({len(by_state[st])}): {', '.join(sorted(by_state[st]))}")

    # Also list unvalidated 2024-2026 stores by year
    for year in (2024, 2025, 2026):
        unverified = [s for s in file["stores"]
                      if s.get("year_opened") == year
                      and s.get("year_opened_validation") == "builder-createddate-only"]
        if not unverified: continue
        print(f"\n=== {len(unverified)} stores at year_opened={year} not individually web-validated ===")
        by_country = {}
        for s in unverified:
            by_country.setdefault(s.get("country") or "?", []).append(s["name"])
        for cc in sorted(by_country, key=lambda k: -len(by_country[k])):
            names = sorted(by_country[cc])
            n = len(names)
            sample = ', '.join(names[:6]) + (f" ... +{n-6} more" if n > 6 else "")
            print(f"  {cc} ({n}): {sample}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
