"""
Michael's scraper  ->  prices/michaels.json

Michael's is a Next.js site, but every product page embeds a schema.org
ProductGroup in its raw HTML (a <script type="application/ld+json"> block) that
lists every color variant with its price and availability. So we fetch each
parent product, parse that JSON, and emit one self-describing row per color --
no browser needed.

Discovery: a small list of parent product URLs (one per line+size). Each expands
to its full color range automatically, so this isn't a hand-picked color list --
add a line by adding its parent URL. Prices are national (= your shelf price).

Run:  python scrapers/michaels_scraper.py     (stdlib only)
"""
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = "Michael's"
STORE = "4729"  # Greenly Crossings, Holland

# One parent URL per line+size. Each auto-expands to all its colors, so this is
# a list of LINES (not hand-picked colors). Add a line by adding its parent URL.
PARENTS = [
    # Gamblin 1980 (student)
    "https://www.michaels.com/product/gamblin-1980-oil-color-37ml-MMACGB198037",
    "https://www.michaels.com/product/gamblin-1980-oil-color-150ml-10577028",
    # Gamblin Artist Grade (artist)
    "https://www.michaels.com/product/gamblin-artist-grade-oil-colors-37ml--10518333",
    "https://www.michaels.com/product/gamblin-150ml-artist-grade-oil-colors-10518382",
    # Winsor & Newton Winton (student)
    "https://www.michaels.com/product/winsor-newton-winton-oil-colour-tube-37ml-MD002570S",
    # Winsor & Newton Artists' Oil (artist)
    "https://www.michaels.com/product/winsor-newton-artists%27-oil-color-37ml-M10127993",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def fetch(url):
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(f"{url}{sep}michaelsStore={STORE}",
          headers={"User-Agent": UA,
                   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def product_group(html):
    for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(blk)
        except Exception:
            continue
        for it in (data if isinstance(data, list) else [data]):
            if isinstance(it, dict) and it.get("@type") == "ProductGroup":
                return it
    return None


def detect(name, url=""):
    s = (name + " " + url).lower()
    if "gamblin" in s:
        brand = "Gamblin"
    elif "winton" in s or "winsor" in s or "newton" in s:
        brand = "Winsor & Newton"
    else:
        brand = None
    if "1980" in s:
        line, grade = "1980", "student"
    elif "winton" in s:
        line, grade = "Winton", "student"
    elif "gamblin" in s and "artist" in s:
        line, grade = "Artist's Oil", "artist"
    elif "artist" in s and ("winsor" in s or "newton" in s):
        line, grade = "Artists' Oil", "artist"
    else:
        line, grade = None, None
    m = re.search(r"(\d+)\s*ml", s)   # name OR url (Winton lists size in oz, url has ml)
    size = int(m.group(1)) if m else None
    return brand, line, grade, size


def main():
    out = []
    for url in PARENTS:
        try:
            pg = product_group(fetch(url))
        except Exception as e:
            print(f"  fetch error {url}: {e}")
            continue
        if not pg:
            print(f"  no ProductGroup: {url}")
            continue
        brand, line, grade, size = detect(pg.get("name", ""), url)
        if not brand or not line:
            print(f"  unrecognized line: {pg.get('name')!r}")
            continue
        n = 0
        for v in pg.get("hasVariant", []):
            color = (v.get("color") or "").strip()
            offers = v.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = offers.get("price")
            if not color or price is None:
                continue
            out.append({
                "brand": brand, "line": line, "grade": grade, "name": color,
                "dist": DIST, "price": float(price), "size": size, "unit": "ml",
                "url": offers.get("url") or url,
                "inStock": "InStock" in (offers.get("availability") or ""),
            })
            n += 1
        print(f"  {pg.get('name', '').strip()}: {n} colors")
        time.sleep(1)
    (ROOT / "prices").mkdir(exist_ok=True)
    (ROOT / "prices" / "michaels.json").write_text(json.dumps(out, indent=2))
    print(f"\nMichael's: wrote {len(out)} color/price rows -> prices/michaels.json")


if __name__ == "__main__":
    main()
