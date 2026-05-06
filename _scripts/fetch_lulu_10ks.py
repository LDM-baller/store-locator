"""Fetch all Lululemon 10-K filings from SEC EDGAR and extract the store count
tables (company-operated by market + retail locations operated by third parties).

Builds a year-by-year matrix: country × fiscal_year → store_count.
"""
import json, pathlib, re, time, urllib.request, urllib.parse
from collections import defaultdict

OUT_DIR = pathlib.Path(r"G:\My Drive\Programs\store-map\data\_lulu_10k_cache")
OUT_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "store-map-scraper/1.0 (private use; ldm@oddity.com)"}

# Filing accession -> approx fiscal year
FILINGS = [
    # accession, fiscal_year
    ("000139718726000020", 2025),  # filed 2026, FY ending Feb 1 2026
    ("000139718725000013", 2024),  # filed 2025, FY ending Feb 2 2025
    ("000139718724000010", 2023),  # filed 2024, FY ending Jan 28 2024
    ("000139718723000012", 2022),  # filed 2023, FY ending Jan 29 2023
    ("000139718722000014", 2021),  # filed 2022, FY ending Jan 30 2022
    ("000139718721000009", 2020),
    ("000139718720000012", 2019),
    ("000139718719000011", 2018),
    ("000139718718000013", 2017),
    ("000139718717000008", 2016),
    ("000139718716000089", 2015),
    ("000139718715000016", 2014),
    ("000139718714000021", 2013),
    ("000119312513118393", 2012),
    ("000119312512126444", 2011),
    ("000095012311026220", 2010),
    ("000095012310028033", 2009),
    ("000090956709000292", 2008),
    ("000090956708000415", 2007),
]


def http_text(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def find_10k_doc_url(accession):
    """Fetch the index page, return the URL of the main 10-K document."""
    cache = OUT_DIR / f"{accession}_index.htm"
    if cache.exists():
        html = cache.read_text(encoding="utf-8")
    else:
        index_url = f"https://www.sec.gov/Archives/edgar/data/1397187/{accession}/"
        try:
            html = http_text(index_url)
        except Exception as e:
            print(f"  index fetch failed: {e}")
            return None
        cache.write_text(html, encoding="utf-8")
        time.sleep(0.5)
    # Find the main 10-K HTM document — usually 'lulu-YYYYMMDD.htm' or 'o\d+e10vk.htm'
    candidates = re.findall(r'(?:href|HREF)="([^"]+\.(?:htm|html))"', html)
    candidates = [c for c in candidates if 'index' not in c.lower() and 'ex' not in c.lower()
                  and 'sig' not in c.lower() and 'cover' not in c.lower()]
    # Prefer ones with 10k or 'lulu-' or '10vk' in the name
    for kw in ('10k', '10vk', 'lulu-', '10-k'):
        prefer = [c for c in candidates if kw in c.lower()]
        if prefer:
            url = prefer[0]
            return url if url.startswith('http') else f"https://www.sec.gov{url}"
    if candidates:
        url = candidates[0]
        return url if url.startswith('http') else f"https://www.sec.gov{url}"
    return None


def fetch_10k(accession, fy):
    """Fetch the 10-K document HTML for a given accession, cached on disk."""
    cache = OUT_DIR / f"FY{fy}_{accession}.htm"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    url = find_10k_doc_url(accession)
    if not url:
        print(f"  could not find 10-K doc URL for {accession}")
        return None
    print(f"    -> {url}")
    try:
        html = http_text(url)
    except Exception as e:
        print(f"  fetch failed: {e}")
        return None
    cache.write_text(html, encoding="utf-8")
    time.sleep(0.6)
    return html


def normalize(html):
    """Strip tags, normalize whitespace."""
    text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&#160;', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# Country names we'll match in the tables (broad superset)
COUNTRIES = [
    "United States", "Canada", "Mexico", "Mainland China", "China", "Australia",
    "South Korea", "Korea", "Hong Kong SAR", "Hong Kong", "Japan", "Singapore",
    "New Zealand", "Taiwan", "Malaysia", "Thailand", "Macau SAR", "Macau",
    "United Kingdom", "Germany", "France", "Ireland", "Spain", "Netherlands",
    "Sweden", "Italy", "Norway", "Switzerland",
    "United Arab Emirates", "Saudi Arabia", "Israel", "Kuwait", "Qatar", "Turkey",
    "Belgium", "Bahrain", "Denmark", "Puerto Rico",
]


def extract_country_counts(text, country_set):
    """Find each country's count in the text. Returns {country: (curr, prev)}.
    Handles em-dashes (--) which mean "no stores that year"."""
    found = {}
    # Em-dash variants used in 10-Ks: — — — (literal) and may render as `—` in text
    # We'll allow either a digit or em-dash as the value
    for c in country_set:
        # Pattern: "Country <val1> [<val2>]" where val is digit or em-dash
        # Limit search to first 800 chars after country mention to stay within table row
        for m in re.finditer(rf'\b{re.escape(c)}\b\s*(\d+|—|–|-)\s*(\d+|—|–|-)?\b', text):
            v1 = m.group(1); v2 = m.group(2)
            n1 = int(v1) if v1.isdigit() else 0  # em-dash treated as 0
            n2 = int(v2) if (v2 and v2.isdigit()) else (0 if v2 in ('—','–','-') else None)
            if 0 <= n1 < 2000:
                if c in found: continue  # keep first match
                found[c] = (n1 if v1.isdigit() else None, n2 if (v2 and v2.isdigit()) else (0 if v2 in ('—','–','-') else None))
                break
    return found


def main():
    matrix = defaultdict(dict)  # country -> {fy: count}
    third_party_matrix = defaultdict(dict)

    for accession, fy in FILINGS:
        print(f"\n=== FY{fy} ({accession}) ===")
        html = fetch_10k(accession, fy)
        if not html:
            print("  SKIP")
            continue
        text = normalize(html)

        # Locate the company-operated section
        # In recent 10-Ks: "Number of company-operated stores by market" (table)
        # In older ones (FY2007-2017): typically narrative — total stores + per-region notes.
        # Try the structured-table header first, fall back to "stores in operation" narrative.
        # Try several header patterns:
        m_co = (re.search(r'(Number of company-operated stores by market[\s\S]{0,3000})', text, re.I)
                or re.search(r'(Number of company-operated stores[\s\S]{0,3000})', text, re.I)
                or re.search(r'(Number of stores by[\s\S]{0,3000})', text, re.I))
        # If still nothing (older filings), the table is in narrative form — capture totals separately
        narrative_total = None
        if not m_co:
            tm = re.search(r'(\d{2,4})\s*(?:&#32;)?\s*(?:company-operated\s+)?stores in operation', text, re.I)
            if tm:
                narrative_total = int(tm.group(1))
        # Third-party section
        m_3p = re.search(r'(Number of retail locations operated by third parties[\s\S]{0,2000})', text, re.I)
        if not m_3p:
            m_3p = re.search(r'(retail locations operated by third part[\s\S]{0,2000})', text, re.I)

        if m_co:
            section = m_co.group(1)
            counts = extract_country_counts(section, COUNTRIES)
            print(f"  company-operated section: {len(counts)} countries")
            for c, (n_curr, n_prev) in counts.items():
                matrix[c][fy] = n_curr
                if n_prev is not None and (fy-1) not in matrix[c]:
                    matrix[c][fy-1] = n_prev
                print(f"    {c}: {n_curr} ({n_prev or '-'})")
        else:
            print("  (no 'Number of company-operated' section found)")
            if narrative_total:
                matrix["__TOTAL__"][fy] = narrative_total
                print(f"  narrative total: {narrative_total} stores")

        if m_3p:
            section = m_3p.group(1)
            counts = extract_country_counts(section, COUNTRIES)
            print(f"  third-party section: {len(counts)} countries")
            for c, (n_curr, n_prev) in counts.items():
                third_party_matrix[c][fy] = n_curr
                if n_prev is not None and (fy-1) not in third_party_matrix[c]:
                    third_party_matrix[c][fy-1] = n_prev

    # Save the matrix
    out = {
        "company_operated_by_market_by_fy": dict(matrix),
        "third_party_operated_by_market_by_fy": dict(third_party_matrix),
    }
    out_path = pathlib.Path(r"G:\My Drive\Programs\store-map\data\_lulu_10k_store_counts.json")
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved store-count matrix to {out_path}")

    # Summary
    print("\n=== Summary: company-operated stores by market by fiscal year ===")
    countries_sorted = sorted(matrix.keys())
    fys = sorted({fy for c in matrix for fy in matrix[c]})
    print(f"{'Country':<25} " + " ".join(f"{fy:>5}" for fy in fys))
    for c in countries_sorted:
        row = [str(matrix[c].get(fy, "-")) for fy in fys]
        print(f"  {c:<23} " + " ".join(f"{x:>5}" for x in row))


if __name__ == "__main__":
    main()
