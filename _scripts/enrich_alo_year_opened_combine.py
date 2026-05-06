"""Combine year_opened signals for Alo Yoga stores.

We have two signals:
  1. Builder.io `createdDate` (224/226 stores) — when the entry was added to Alo's CMS.
     Earliest in the data is 2023 (Alo migrated CMSes around then). For any
     store opened after 2023, this is essentially the opening year. For stores
     that pre-existed Alo's Builder.io migration, this is the migration year, NOT
     the true opening year — those stores would need Wayback data to correct.
  2. Wayback Machine earliest snapshot (16 stores from prior run) — earliest
     evidence of the store existing on Alo's website. For older flagships this
     is more accurate than Builder.io.

Combined rule: year_opened = min(builder_year, wayback_year) when both exist.
The minimum represents the earliest known evidence of the store's existence,
which is the closest proxy to actual opening year we have.

The raw field records both signals separately so the source is auditable.
"""
import json, pathlib, datetime, sys
from collections import Counter

DATA = pathlib.Path(r"G:\My Drive\Programs\store-map\data\alo-yoga.json")
BUILDER = pathlib.Path(r"G:\My Drive\Programs\store-map\data\_alo-yoga_builder.json")


def main():
    file = json.loads(DATA.read_text(encoding="utf-8"))
    builder = json.loads(BUILDER.read_text(encoding="utf-8"))
    groups = builder["web-component-page"][0]["data"]["state"]["storeDataByLocation"]["results"]

    # Build a map: builder demandware-store-id -> createdDate year
    # We use Demandware ID via raw._demandware_store_id... wait, Alo doesn't have one.
    # Alo's store ID was constructed from country + name slug. We need to match
    # the Builder.io entries to alo-yoga.json stores by name+city.
    builder_by_namecity = {}
    for g in groups:
        for item in g["data"].get("storeList", []):
            sval = (item.get("store") or {}).get("value") or {}
            sd = sval.get("data") or {}
            cd_ms = sval.get("createdDate")
            if not cd_ms: continue
            year = datetime.datetime.fromtimestamp(cd_ms/1000).year
            name = (sd.get("name") or "").strip()
            city = (sd.get("city") or "").strip()
            key = (name.lower(), city.lower())
            # Keep earliest createdDate if the same name+city appears more than once
            existing = builder_by_namecity.get(key)
            if not existing or year < existing[0]:
                builder_by_namecity[key] = (year, cd_ms)

    print(f"Builder.io entries indexed: {len(builder_by_namecity)}")

    # Iterate stores in alo-yoga.json, look up each
    matched = 0; unmatched = []
    updated_combine = 0; updated_only_builder = 0; updated_only_wayback = 0
    for s in file["stores"]:
        name = (s.get("name") or "").strip()
        city = (s.get("city") or "").strip()
        # Try a few key shapes since alo-yoga.json's city may be the parsed-from-fullAddress city
        # while Builder.io's city was sometimes "Chatswood, AU" or "Bahrain "
        candidates = [
            (name.lower(), city.lower()),
            (name.lower(), (s.get("raw") or {}).get("city","").lower() if isinstance((s.get("raw") or {}).get("city"), str) else ""),
            (name.lower(), ""),
        ]
        builder_year = None; builder_cd_ms = None
        for k in candidates:
            hit = builder_by_namecity.get(k)
            if hit:
                builder_year, builder_cd_ms = hit
                break
        # also try matching by name only (last resort)
        if not builder_year:
            for (n, c), (y, cd) in builder_by_namecity.items():
                if n == name.lower():
                    builder_year = y; builder_cd_ms = cd
                    break
        if builder_year:
            matched += 1
        else:
            unmatched.append((s["id"], name, city))

        existing_year = s.get("year_opened")
        existing_source = (s.get("raw") or {}).get("_year_opened_source")

        signals = {}
        if builder_year:
            signals["builder_created_year"] = builder_year
            signals["builder_created_ms"]   = builder_cd_ms
        if existing_year and existing_source in ("wayback-store-page","wayback-stores-directory"):
            signals["wayback_earliest_year"] = existing_year
            signals["wayback_snapshot"] = (s.get("raw") or {}).get("_year_opened_snapshot")

        # Combine: earliest of available signals
        years_known = [v for k, v in signals.items() if k.endswith("_year") and v]
        if years_known:
            new_year = min(years_known)
        else:
            new_year = None

        # Determine source label
        if "builder_created_year" in signals and "wayback_earliest_year" in signals:
            if signals["wayback_earliest_year"] < signals["builder_created_year"]:
                source = "wayback-earlier-than-builder-migration"
                updated_only_wayback += 1
            else:
                source = "builder-createddate"
                updated_combine += 1
        elif "builder_created_year" in signals:
            source = "builder-createddate"
            updated_only_builder += 1
        elif "wayback_earliest_year" in signals:
            source = "wayback-only"
            updated_only_wayback += 1
        else:
            source = None

        s["year_opened"] = new_year
        s.setdefault("raw", {})
        s["raw"]["_year_opened_source"] = source
        s["raw"]["_year_opened_signals"] = signals

    print(f"\nMatched to Builder.io: {matched} / {len(file['stores'])}")
    if unmatched:
        print(f"Unmatched: {len(unmatched)}")
        for sid, n, c in unmatched[:10]:
            print(f"  {sid}  name={n!r}  city={c!r}")

    print(f"\nSource breakdown:")
    print(f"  builder-createddate (>= 2023): {updated_only_builder + updated_combine}")
    print(f"  wayback-earlier-than-builder:  {updated_only_wayback}")

    # Coverage + histogram
    known = sum(1 for s in file["stores"] if s.get("year_opened"))
    histogram = dict(sorted(Counter(s.get("year_opened") for s in file["stores"] if s.get("year_opened")).items()))
    file["year_opened_coverage"] = {"known": known, "unknown": len(file["stores"]) - known}
    file["year_opened_histogram"] = histogram
    file["year_opened_note"] = (
        "year_opened combines two signals: Builder.io `createdDate` (when Alo's "
        "CMS entry was created) and Wayback Machine earliest snapshot. The minimum "
        "of the two is taken — earliest evidence of existence is the closest proxy "
        "to the real opening year. Caveats: stores that pre-existed Alo's Builder.io "
        "migration (~2023) without a Wayback record have year_opened=2023, which is "
        "the migration year, not the true opening year. raw._year_opened_signals "
        "preserves both raw signals for auditing."
    )

    DATA.write_text(json.dumps(file, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSaved.")
    print(f"  Coverage: {known}/{len(file['stores'])} ({100*known/len(file['stores']):.0f}%)")
    print(f"  Histogram:")
    for y, n in histogram.items():
        bar = "#" * n
        print(f"    {y}: {n:3} {bar}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
