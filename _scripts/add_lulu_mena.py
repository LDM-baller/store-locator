"""Add Lulu MENA franchise stores (Qatar 3, KSA 6, UAE 11) to lululemon.json.

Source: Lindsay's manual list 2026-05-06 from Alshaya Group / Lulu MENA franchise.
These are 'third-party operated' stores per Lulu 10-K but real Lulu retail.

Coords: known mall locations (these are all famous shopping centers — coords
are city-block accurate from public records).
"""
import json, pathlib, re, datetime

DATA = pathlib.Path(r"G:\My Drive\Programs\store-map\data\lululemon.json")

# (country, city, mall_name, lat, lng, source_note)
STORES = [
    # Qatar — all in Doha metro
    ("QA", "Doha",     "The Gate Mall",            25.3300, 51.5260, "West Bay, Doha"),
    ("QA", "Lusail",   "Place Vendôme",            25.4135, 51.4990, "Lusail, north of Doha"),
    ("QA", "Doha",     "Mall of Qatar",            25.3380, 51.4202, "Al Rayyan, west Doha"),

    # KSA — Saudi Arabia
    ("SA", "Jeddah",   "Red Sea Mall",             21.6210, 39.1180, "Jeddah Corniche"),
    ("SA", "Jeddah",   "U Walk Jeddah",            21.5631, 39.1457, "Jeddah Tahlia District"),
    ("SA", "Riyadh",   "The Village Mall",         24.7800, 46.7280, "Riyadh"),
    ("SA", "Riyadh",   "Riyadh Park Mall",         24.7920, 46.6170, "King Fahd Rd, Riyadh"),
    ("SA", "Riyadh",   "Mode Al Faisaliah",        24.6914, 46.6857, "Mode Mall (Mode Al Faisaliah), Riyadh"),
    ("SA", "Riyadh",   "Panorama Mall",            24.6920, 46.6850, "King Fahd Rd, Riyadh"),

    # UAE
    ("AE", "Dubai",     "Mall of the Emirates",          25.1180, 55.2002, "Sheikh Zayed Rd, Dubai"),
    ("AE", "Dubai",     "The Dubai Mall",                25.1972, 55.2790, "Downtown Dubai"),
    ("AE", "Dubai",     "Dubai Marina Mall",             25.0803, 55.1404, "Dubai Marina"),
    ("AE", "Dubai",     "City Centre Mirdif",            25.2200, 55.4120, "Mirdif, Dubai"),
    ("AE", "Dubai",     "City Walk",                     25.2048, 55.2622, "Al Wasl, Dubai"),
    ("AE", "Dubai",     "Dubai Hills Mall",              25.1066, 55.2548, "Dubai Hills Estate"),
    ("AE", "Abu Dhabi", "The Galleria Al Maryah Island", 24.5034, 54.3850, "Abu Dhabi"),
    ("AE", "Abu Dhabi", "Yas Mall",                      24.4881, 54.6035, "Yas Island, Abu Dhabi"),
    ("AE", "Dubai",     "Nakheel Mall (Palm Jumeirah)",  25.1130, 55.1390, "Palm Jumeirah, Dubai"),
    ("AE", "Al Ain",    "Al Jimi Mall",                  24.2207, 55.7528, "Al Ain"),
    ("AE", "Sharjah",   "City Centre Al Zahia",          25.3210, 55.4690, "Sharjah"),
]


def slugify(s):
    s = re.sub(r'[^\w\s-]', '', s.lower())
    s = re.sub(r'[\s-]+', '-', s).strip('-')
    return s or "x"


def main():
    file = json.loads(DATA.read_text(encoding="utf-8"))
    print(f"Existing stores: {len(file['stores'])}")

    scraped_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    new_records = []
    for cc, city, name, lat, lng, note in STORES:
        sid = f"lululemon-{cc.lower()}-{slugify(name)}"[:80]
        new_records.append({
            "id": sid,
            "retailer": "Lululemon",
            "name": name,
            "address": None,
            "city": city,
            "state": None,
            "country": cc,
            "postal_code": None,
            "lat": lat, "lng": lng,
            "coord_is_estimated": True,
            "store_type": "regular",
            "status": "active",
            "phone": None,
            "hours": None,
            "url": None,
            "year_opened": None,  # estimator will fill
            "year_opened_validation": "pending",
            "scraped_at": scraped_at,
            "raw": {
                "_coord_source": "manual-known-mall-coords",
                "_data_source": "Lindsay manual list 2026-05-06; Lulu MENA franchise (Alshaya Group operated; counted as 'third-party operated' in Lulu 10-K)",
                "_note": note,
            },
        })

    print(f"Adding {len(new_records)} MENA stores")
    file["stores"].extend(new_records)
    file["store_count"] = len(file["stores"])
    DATA.write_text(json.dumps(file, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {file['store_count']} stores -> {DATA}")

    from collections import Counter
    cc_counts = Counter(r["country"] for r in new_records)
    print(f"\nNew by country: {dict(cc_counts)}")


if __name__ == "__main__":
    main()
