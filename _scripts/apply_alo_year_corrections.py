"""Apply year_opened corrections to alo-yoga.json based on a web-search validation pass.

Five 2023-tagged stores actually opened earlier — confirmed via news sources.
Patches the JSON in place. Adds raw._year_opened_correction with the
correction reason and source citation for each touched store.
"""
import json, pathlib

DATA = pathlib.Path(r"G:\My Drive\Programs\store-map\data\alo-yoga.json")

CORRECTIONS = {
    # Match by (name, country). Lululemon-style ID matching too brittle here
    # because Alo IDs are long slugified strings.
    ("Kingdom Mall", "SA"): {
        "year_opened": 2021,
        "month": 12,
        "source": "whatsonsaudiarabia.com 2021/12 — 'Alo Yoga makes Saudi debut at Riyadh's Kingdom Centre'; Alo's first international store, opened December 2021",
    },
    ("Avenues 4 (Grand Plaza)", "KW"): {
        "year_opened": 2022,
        "source": "alshaya.com 'Alshaya Group introduces alo to Kuwait' — Alo Yoga debuted in Kuwait at The Avenues in 2022",
    },
    ("Bloor", "CA"): {
        "year_opened": 2022,
        "month": 9,
        "source": "curiocity.com — 'Alo Yoga's first international store is in Toronto & it opens this week'; opened September 2, 2022 at 60 Bloor St West",
    },
    ("Yorkdale", "CA"): {
        "year_opened": 2022,
        "month": 11,
        "source": "retail-insider.com — Alo Yoga's second Canadian store, opened November 1, 2022",
    },
    ("Boston Seaport", "US"): {
        "year_opened": 2022,
        "month": 7,
        "source": "thebostoncalendar.com — 'Alo Yoga: Grand Opening Party 07/15/22'; opened July 15, 2022 at 70 Pier Four Blvd. Wayback's earliest CDX snapshot of the /pages/boston-seaport-store URL was January 2023, which was misleading.",
    },

    # Round-2 corrections (2026-05-06): low-intensity web search batch.
    # Most discovered via Alo's own blog posts listing November 2022 and
    # September 2022 openings, plus Wikipedia for Beverly Hills Flagship.
    ("Beverly Hills Flagship", "US"): {
        "year_opened": 2016,
        "month": 4,
        "source": "Wikipedia (Alo Yoga) — Beverly Hills was Alo's first retail store, opened April 20, 2016. Wayback's earliest snapshot was 2019, which was misleading.",
    },
    ("Westchester", "US"): {
        "year_opened": 2022,
        "month": 5,
        "source": "aloyoga.com/blogs/alo-blog/new-alo-store-westchester-white-plains-new-york — May 2022, Alo's 14th store.",
    },
    ("NorthPark Center", "US"): {
        "year_opened": 2022,
        "month": 9,
        "source": "aloyoga.com/blogs/alo-blog/we-ve-been-busy-4-new-alo-sanctuaries-just-opened — September 2022.",
    },
    ("Rockefeller", "US"): {
        "year_opened": 2022,
        "month": 9,
        "source": "aloyoga.com/blogs/alo-blog/we-ve-been-busy-4-new-alo-sanctuaries-just-opened — September 2022.",
    },
    ("Kierland Commons", "US"): {
        "year_opened": 2022,
        "month": 11,
        "source": "aloyoga.com/blogs/alo-blog/6-new-alo-yoga-stores-november-2022 — November 2022 (one of 6 stores in that batch).",
    },
    ("Manhattan Village", "US"): {
        "year_opened": 2022,
        "month": 11,
        "source": "aloyoga.com/blogs/alo-blog/6-new-alo-yoga-stores-november-2022 — November 2022.",
    },
    ("The Gardens", "US"): {
        "year_opened": 2022,
        "month": 11,
        "source": "aloyoga.com/blogs/alo-blog/6-new-alo-yoga-stores-november-2022 — November 2022 (Palm Beach Gardens, FL).",
    },
    ("Cherry Creek", "US"): {
        "year_opened": 2022,
        "month": 11,
        "source": "aloyoga.com/blogs/alo-blog/6-new-alo-yoga-stores-november-2022 — November 2022 (Denver, CO).",
    },
    ("Park Meadows", "US"): {
        "year_opened": 2022,
        "month": 11,
        "source": "aloyoga.com/blogs/alo-blog/6-new-alo-yoga-stores-november-2022 — November 2022 (Lone Tree, CO).",
    },

    # Round-3 corrections (2026-05-06): 2024-2026 spot-check pass.
    ("Emquartier", "TH"): {
        "year_opened": 2023,
        "month": 11,
        "source": "Bangkok Post + bk.asia-city.com — Alo's FIRST store in Asia, opened November 17, 2023 at EmQuartier Bangkok. Builder.io createdDate had this as 2024 because the CMS entry was created later.",
    },
    ("Mitikah", "MX"): {
        "year_opened": 2025,
        "month": 11,
        "source": "modaenlaciudad.com 2025/12 — 'Alo Yoga ya están en Mítikah' published Dec 2025, store opened November 2025 at Mitikah Mexico City. Builder.io entry was created in 2026 but the actual store predates that.",
    },
    ("Santa Fe", "MX"): {
        "year_opened": 2025,
        "source": "via-santafe.com + centrosantafe.com.mx — Alo Yoga store at Vía Santa Fe Mexico City, operational by 2025. Among Alo's late-2025 Mexico City expansions (Mitikah/Satelite/Santa Fe/Angelopolis cluster).",
    },
    ("Satelite", "MX"): {
        "year_opened": 2025,
        "source": "FashionNetwork México — May 2025 article noted Plaza Satelite as future opening planned for summer 2025. Late-2025 Mexico City expansion.",
    },
    ("Angelopolis", "MX"): {
        "year_opened": 2025,
        "source": "FashionNetwork México 1729833 — May 2025 article: 'Alo Yoga prepara la apertura de su sexta tienda en México' at Angelópolis (Puebla), opening date pending but in 2025.",
    },
    ("Leeds", "GB"): {
        "year_opened": 2026,
        "source": "Retail Gazette 2025/10 + fashionunited.com 2025/10 — Alo's UK expansion plan: Manchester (Nov 21 2025), Westfield London (Nov 28 2025), Battersea (Dec 5 2025), Victoria Leeds opens 2026. Builder.io createdDate had Leeds as 2025 but the actual opening is 2026.",
    },

    # Round-4 correction (2026-05-06)
    ("Oakridge Park - Coming Soon", "CA"): {
        "year_opened": 2026,
        "source": "globenewswire.com 2025/10/09 + retail-insider.com 2025/10 — Oakridge Park Vancouver new tenants debut Spring 2026. Builder.io createdDate had Oakridge as 2025; actual opening is 2026.",
    },
}

def main():
    file = json.loads(DATA.read_text(encoding="utf-8"))
    applied = 0; not_found = []
    for s in file["stores"]:
        key = (s.get("name"), s.get("country"))
        if key not in CORRECTIONS: continue
        correction = CORRECTIONS[key]
        old_year = s.get("year_opened")
        new_year = correction["year_opened"]
        s["year_opened"] = new_year
        s.setdefault("raw", {})
        s["raw"]["_year_opened_correction"] = {
            "previous_year": old_year,
            "corrected_year": new_year,
            "month": correction.get("month"),
            "source": correction["source"],
            "validated_via": "manual web search 2026-05-06",
        }
        s["raw"]["_year_opened_source"] = "web-search-correction"
        print(f"  {key[1]:<3} {s['name']:<35} {old_year} -> {new_year}")
        applied += 1

    # Track which keys weren't found
    found_keys = {(s["name"], s["country"]) for s in file["stores"]
                  if (s["name"], s["country"]) in CORRECTIONS}
    not_found = [k for k in CORRECTIONS if k not in found_keys]
    if not_found:
        print(f"\nNOT APPLIED ({len(not_found)} keys had no matching store):")
        for k in not_found: print(f"  {k}")

    # Recompute coverage + histogram
    from collections import Counter
    histogram = dict(sorted(Counter(s.get("year_opened") for s in file["stores"]
                                    if s.get("year_opened")).items()))
    file["year_opened_histogram"] = histogram
    file["year_opened_coverage"] = {
        "known": sum(1 for s in file["stores"] if s.get("year_opened")),
        "unknown": sum(1 for s in file["stores"] if not s.get("year_opened")),
    }

    DATA.write_text(json.dumps(file, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nApplied {applied} corrections. Saved.")
    print(f"  New histogram:")
    for y, n in histogram.items():
        bar = "#" * n
        print(f"    {y}: {n:3} {bar}")


if __name__ == "__main__":
    main()
