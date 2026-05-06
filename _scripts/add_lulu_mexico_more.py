"""Add 3 more Mexico stores from Lindsay's manual research 2026-05-06."""
import json, pathlib, re, datetime

DATA = pathlib.Path(r"G:\My Drive\Programs\store-map\data\lululemon.json")

STORES = [
    # (city, state, name, address, lat, lng, status, hours, postal_code, source_note)
    ("Cancún", "Quintana Roo", "Cancun Island",
     "La Isla, Hotel Zone Cancun Quintana Roo 32107",
     21.0833, -86.7821, "active",
     "Mon-Sun: 10:00-21:00",
     "32107",
     "La Isla Shopping Village, Cancun Hotel Zone"),

    ("Cancún", "Quintana Roo", "Puerto Cancun",
     "Blvd. Kukulcan 1 Cancun Quintana Roo 77500",
     21.1413, -86.8262, "coming_soon",
     "Closed (all days listed Closed in source — likely not yet open)",
     "77500",
     "Puerto Cancun development, Blvd. Kukulcan 1. Source listed all 7 days as Closed; assuming pre-opening status."),

    ("Mérida", "Yucatán", "Merida Island",
     "Calle 24 608, Santa Gertrudis Copo Mérida Yucatán 97305",
     21.0285, -89.6116, "active",
     "Mon-Sun: 11:00-21:00",
     "97305",
     "Santa Gertrudis Copo, north Mérida"),
]


def slugify(s):
    s = re.sub(r'[^\w\s-]', '', s.lower())
    s = re.sub(r'[\s-]+', '-', s).strip('-')
    return s or "x"


def main():
    file = json.loads(DATA.read_text(encoding="utf-8"))
    print(f"Existing stores: {len(file['stores'])}")
    scraped_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Idempotency: skip if already present
    existing_ids = {s["id"] for s in file["stores"]}
    new_records = []
    for city, state, name, address, lat, lng, status, hours, postal, note in STORES:
        sid = f"lululemon-mx-{slugify(name)}"[:80]
        if sid in existing_ids:
            print(f"  [skip] {sid} already in data")
            continue
        new_records.append({
            "id": sid,
            "retailer": "Lululemon",
            "name": name,
            "address": address,
            "city": city,
            "state": state,
            "country": "MX",
            "postal_code": postal,
            "lat": lat, "lng": lng,
            "coord_is_estimated": True,
            "store_type": "regular",
            "status": status,
            "phone": None,
            "hours": hours,
            "url": f"https://shop.lululemon.com/stores/mx/{slugify(city)}/{slugify(name)}",
            "year_opened": None,
            "year_opened_validation": "pending",
            "scraped_at": scraped_at,
            "raw": {
                "_coord_source": "manual-known-mall-coords",
                "_data_source": "Lindsay manual list 2026-05-06 — Cancún + Mérida cluster",
                "_note": note,
            },
        })

    print(f"Adding {len(new_records)} stores")
    file["stores"].extend(new_records)
    file["store_count"] = len(file["stores"])
    DATA.write_text(json.dumps(file, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {file['store_count']} stores")


if __name__ == "__main__":
    main()
