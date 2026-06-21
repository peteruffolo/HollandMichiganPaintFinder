"""
Blick scraper  ->  prices/blick.json

Each Blick products page embeds a schema.org ProductGroup whose hasVariant array
lists EVERY color in EVERY size (uncapped), with color, size, price (already the
sale price), availability, and url. So one fetch per line gets the whole range.

The variant `color` field drops qualifiers ("Alizarin Crimson" when the real name
is "Alizarin Crimson Permanent"), so we derive the display name from the full
`name` field to preserve qualifiers the pigment matcher needs. Sets are skipped.

Run:  python scrapers/blick_scraper.py     (stdlib only)
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, write_prices_safely

DIST = "Blick"

# one products page per line; each expands to all colors+sizes via hasVariant
LINES = [
    {"url": "https://www.dickblick.com/products/gamblin-1980-oil-colors/",
     "brand": "Gamblin", "line": "1980", "grade": "student"},
    {"url": "https://www.dickblick.com/products/gamblin-artists-oil-colors/",
     "brand": "Gamblin", "line": "Artist's Oil", "grade": "artist"},
    {"url": "https://www.dickblick.com/products/winsor-newton-winton-oil-colors/",
     "brand": "Winsor & Newton", "line": "Winton", "grade": "student"},
    {"url": "https://www.dickblick.com/products/blick-studio-oil-colors/",
     "brand": "Blick", "line": "Studio", "grade": "student"},
    {"url": "https://www.dickblick.com/products/blick-artists-oil-color/",
     "brand": "Blick", "line": "Artists' Oil", "grade": "artist"},
    {"url": "https://www.dickblick.com/products/winsor-newton-artists-oil-colors/",
     "brand": "Winsor & Newton", "line": "Artists' Oil", "grade": "artist"},
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
          "Accept": "text/html,*/*;q=0.8", "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def product_group(page):
    for blk in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(blk)
        except Exception:
            continue
        for it in (data if isinstance(data, list) else [data]):
            if isinstance(it, dict) and it.get("@type") == "ProductGroup":
                return it
    return None


def display_name(name, color):
    """Preserve qualifiers: take from where `color` begins in the full name,
    through the end, after stripping the trailing size/format."""
    clean = re.sub(r"\s+\d+\s*ml.*$", "", name or "", flags=re.I).strip()
    clean = re.sub(r"\s+", " ", clean)
    if color:
        idx = clean.find(color)
        if idx >= 0:
            return clean[idx:].strip()
    return color or clean


def parse_size(size_str):
    m = re.search(r"(\d+)\s*ml", (size_str or "").lower())
    return int(m.group(1)) if m else None


def scrape_line(cfg):
    pg = product_group(fetch(cfg["url"]))
    if not pg:
        print(f"  no ProductGroup: {cfg['url']}")
        return []
    rows = []
    for v in pg.get("hasVariant", []):
        if "set" in (v.get("description") or "").lower():
            continue  # skip sets/assortments
        color = (v.get("color") or "").strip()
        name = display_name(v.get("name", ""), color)
        offers = v.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        if not name or price is None:
            continue
        rows.append({"brand": cfg["brand"], "line": cfg["line"], "grade": cfg["grade"],
                     "name": name, "dist": DIST, "price": float(price),
                     "size": parse_size(v.get("size")), "unit": "ml",
                     "url": offers.get("url") or cfg["url"],
                     "inStock": "InStock" in (offers.get("availability") or "")})
    print(f"  {cfg['brand']} {cfg['line']}: {len(rows)} colors")
    return rows


def main():
    out = []
    for cfg in LINES:
        try:
            out.extend(scrape_line(cfg))
        except Exception as e:
            print(f"  error {cfg['url']}: {e}")
        time.sleep(1)
    print(f"\nBlick: parsed {len(out)} color/price rows")
    write_prices_safely(ROOT / "prices" / "blick.json", out)


if __name__ == "__main__":
    main()
