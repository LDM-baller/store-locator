# LDM Locate

Interactive temporal map of retail fleets. Currently loads Lululemon (972 stores) and Alo Yoga (224 stores) and lets you scrub the year slider 2000 → 2026 to watch the fleet bloom over time.

## Run locally

```
python -m http.server 8765
```

Open `http://localhost:8765/`.

(Browsers block `fetch` on `file://`, so a local server is required.)

## Data

`data/<retailer>.json` — one file per retailer, normalized schema.

| Field | Used for |
|---|---|
| `id`, `name`, `lat`, `lng` | rendering |
| `year_opened` | temporal simulation; required for a marker to ever appear |
| `year_opened_validation`, `raw._year_opened_estimated` | shown in the detail panel as provenance |
| `store_type` | visual differentiation (`flagship`, `regular`, `popup`, `outlet`, `concession`, `experiential`, `showroom`, `other`) |
| `status` | `active` / `coming_soon` shown; `closed` hides the marker |
| `coord_is_estimated` | reduces marker fill opacity |
| `address`, `city`, `state`, `country`, `postal_code`, `phone`, `hours`, `url` | detail panel |

## Adding a retailer

1. Drop a normalized JSON at `data/<slug>.json`.
2. Add an entry to the `RETAILERS` array at the top of `app.js`:
   ```js
   { slug: 'new-brand', name: 'New Brand', file: 'data/new-brand.json', color: '#hex' }
   ```

## Files

- `index.html` / `app.js` / `styles.css` — viewer (vanilla JS, Leaflet, no build step)
- `data/*.json` — retailer datasets
- `_scripts/` — Python helpers used to scrape, validate, and enrich the data
