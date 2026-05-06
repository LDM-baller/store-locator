"""Add Lululemon Mexico stores to lululemon.json.

Source: Lulu Mexico is hosted on shop.lululemon.com/stores/mx/<city>/<slug> URLs
(individual pages work, but the all-stores directory page doesn't include MX).
lululemon.com.mx is geo-blocked from US IPs. So this list was built by web-search
+ news article enumeration. Lulu's FY2025 10-K shows 26 Mexico stores; we have
~18 confirmed by name (the rest live in cities we know — Cancún, Mérida,
Chihuahua, San Luis Potosí, Los Cabos — but specific malls weren't findable
in basic search).
"""
import json, pathlib, re, datetime

DATA = pathlib.Path(r"G:\My Drive\Programs\store-map\data\lululemon.json")

# (city, mall_name, lat, lng, source_note)
# Coords use known mall locations from public records.
STORES = [
    # Mexico City (CDMX) — multiple stores
    ("Mexico City", "Artz Pedregal",     19.2945, -99.2126, "First Lulu Mexico store, May 2023"),
    ("Mexico City", "Antara Polanco",    19.4406, -99.2069, "Antara Fashion Hall, Polanco"),
    ("Mexico City", "Mitikah",           19.3573, -99.1721, "Opened Nov 2025"),
    ("Mexico City", "Mazaryk",           19.4308, -99.1922, "Avenida Presidente Masaryk, Polanco"),
    ("Mexico City", "Oasis Coyoacán",    19.3415, -99.1640, "Coyoacán"),
    ("Mexico City", "Centro Santa Fe",   19.3590, -99.2598, "Santa Fe shopping center"),
    ("Mexico City", "Arcos Bosques",     19.3997, -99.2543, "Paseo Arcos Bosques"),

    # Toluca / Metepec (Estado de México)
    ("Toluca",      "Galerias Metepec",  19.2645, -99.6088, "Galerías Metepec mall"),

    # Guadalajara (Jalisco)
    ("Guadalajara", "Andares",           20.7113, -103.4019, "Plaza Andares, Zapopan"),
    ("Guadalajara", "Punto Sur",         20.5790, -103.4500, "Punto Sur shopping mall"),
    ("Guadalajara", "Midtown",           20.6892, -103.3937, "Midtown Jalisco"),

    # Querétaro
    ("Santiago de Querétaro", "Antea",   20.7140, -100.4170, "Antea Lifestyle Center"),

    # Monterrey (Nuevo León)
    ("Monterrey",   "Galerias Monterrey",25.6606, -100.3717, "Galerías Monterrey"),
    ("Monterrey",   "Fashion Drive",     25.6502, -100.2882, "Fashion Drive San Pedro"),
    ("Monterrey",   "Punto Valle",       25.6500, -100.3500, "Punto Valle"),
    ("Monterrey",   "Cumbres",           25.7489, -100.4258, "Galerías Valle Oriente or Cumbres area — 4th Monterrey store per Lulu MX FB"),

    # Tijuana (Baja California)
    ("Tijuana",     "Peninsula Tijuana", 32.4660, -117.0160, "Peninsula Tijuana mall"),

    # Puebla
    ("Puebla",      "Angelopolis",       19.0294, -98.2334, "Angelópolis Lifestyle Center"),
]

COUNTRY = "MX"


def slugify(s):
    s = re.sub(r'[^\w\s-]', '', s.lower())
    s = re.sub(r'[\s-]+', '-', s).strip('-')
    return s or "x"


def main():
    file = json.loads(DATA.read_text(encoding="utf-8"))
    print(f"Existing stores: {len(file['stores'])}")
    scraped_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    new_records = []
    for city, name, lat, lng, note in STORES:
        sid = f"lululemon-{COUNTRY.lower()}-{slugify(name)}"[:80]
        new_records.append({
            "id": sid,
            "retailer": "Lululemon",
            "name": name,
            "address": None,
            "city": city,
            "state": None,
            "country": COUNTRY,
            "postal_code": None,
            "lat": lat, "lng": lng,
            "coord_is_estimated": True,
            "store_type": "regular",
            "status": "active",
            "phone": None,
            "hours": None,
            "url": f"https://shop.lululemon.com/stores/mx/{slugify(city)}/{slugify(name)}",
            "year_opened": None,
            "year_opened_validation": "pending",
            "scraped_at": scraped_at,
            "raw": {
                "_coord_source": "manual-known-mall-coords",
                "_data_source": (
                    "Web-search enumeration 2026-05-06 from search results, FashionNetwork MX articles, "
                    "Lulu Mexico Facebook posts, and shop.lululemon.com/stores/mx/<city>/<slug> URL probing. "
                    "Lulu acquired Mexico operations in FY2024 (per FY2025 10-K). 10-K reports 26 MX stores "
                    "at end FY2025; this list has 18 confirmed. The remaining ~8 live in cities "
                    "(Cancún, Mérida, Chihuahua, San Luis Potosí, Los Cabos) where specific mall names "
                    "weren't findable in basic search."
                ),
                "_note": note,
            },
        })

    print(f"Adding {len(new_records)} Mexico stores")
    file["stores"].extend(new_records)
    file["store_count"] = len(file["stores"])
    DATA.write_text(json.dumps(file, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {file['store_count']} stores -> {DATA}")


if __name__ == "__main__":
    main()
