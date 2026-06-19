"""
Fris Supply Shop scraper  ->  prices/fris.json

Fris runs on the RAIN POS platform. Listing pages are plain server-rendered HTML
with the price right in the markup, so no headless browser is needed.

Oil paints live under:
  https://www.frissupplyshop.com/shop/Paints-and-Mediums/Oil-Paints.htm
with pagination via ?pageNum=N.

Run:  python scrapers/fris_scraper.py
Deps: pip install requests beautifulsoup4
"""
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_catalog, match_product, extract_size, ROOT

DIST = "Fris Supply Shop"
BASE = "https://www.frissupplyshop.com/shop/Paints-and-Mediums/Oil-Paints.htm"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; pigment-price-checker/1.0)"}
# only record listings whose line we actually track
TRACKED_LINES = {"1980", "Winton"}  # Fris carries Gamblin 1980 + W&N Winton


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def parse_listing_page(html):
    """Yield dicts {name, price, url, in_stock} for each product card on a page."""
    soup = BeautifulSoup(html, "html.parser")
    # RAIN product cards link to /p/...-x<id>.htm ; grab those anchors and their context
    for a in soup.select('a[href*="/p/"]'):
        url = a.get("href", "")
        if "/p/" not in url:
            continue
        block = a.find_parent()
        text = block.get_text(" ", strip=True) if block else a.get_text(" ", strip=True)
        # name is the anchor/alt text; fall back to the image alt
        name = a.get_text(" ", strip=True)
        if not name:
            img = a.find("img")
            name = img.get("alt", "").strip() if img else ""
        if not name:
            continue
        sold_out = "sold out" in text.lower()
        # price like $14.25 or a range $27.05 - $42.95  -> take the first (lowest) number
        prices = re.findall(r"\$(\d+(?:\.\d+)?)", text)
        price = float(prices[0]) if prices else None
        if not url.startswith("http"):
            url = "https://www.frissupplyshop.com" + url
        yield {"name": name, "price": price, "url": url, "in_stock": not sold_out}


def all_pages(max_pages=20):
    seen = set()
    for n in range(1, max_pages + 1):
        url = BASE if n == 1 else f"{BASE}?pageNum={n}"
        html = fetch(url)
        rows = list(parse_listing_page(html))
        if not rows:
            break
        new = 0
        for row in rows:
            key = row["url"]
            if key in seen:
                continue
            seen.add(key)
            new += 1
            yield row
        if new == 0:
            break
        time.sleep(1)  # be polite to a small shop's server


def main():
    catalog = load_catalog()
    out = []
    matched, skipped = 0, 0
    for row in all_pages():
        line = None
        from common import guess_line
        line = guess_line(row["name"])
        if line not in TRACKED_LINES:
            skipped += 1
            continue
        entry, score = match_product(row["name"], catalog, restrict_line=line)
        if not entry or score < 0.6:
            skipped += 1
            print(f"  no match: {row['name']!r}")
            continue
        size, unit = extract_size(row["name"])
        out.append({
            "product_id": entry["id"],
            "dist": DIST,
            "price": row["price"],
            "size": size, "unit": unit or "ml",
            "url": row["url"],
            "inStock": row["in_stock"],
        })
        matched += 1

    (ROOT / "prices").mkdir(exist_ok=True)
    (ROOT / "prices" / "fris.json").write_text(json.dumps(out, indent=2))
    print(f"\nFris: matched {matched}, skipped {skipped} -> prices/fris.json")


if __name__ == "__main__":
    main()
