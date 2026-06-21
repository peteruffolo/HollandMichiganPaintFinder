"""
Michael's scraper  ->  prices/michaels.json

Each parent product embeds a schema.org ProductGroup. Its hasVariant array is
capped at 25, but its isRelatedTo.url array lists EVERY color's page. So:
  1. fetch the parent, read all variant URLs (isRelatedTo + hasVariant)
  2. for the (<=25) colors already detailed in hasVariant, take color+price directly
  3. for the rest, fetch each color page and read the color (og:title) and price
     (<meta name="og:price:amount">)
No browser needed. Prices are national (= your in-store shelf price).

Run:  python scrapers/michaels_scraper.py     (stdlib only)
"""
import html as htmllib
import json
import re
import time
import urllib.request
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import write_prices_safely

ROOT = Path(__file__).resolve().parent.parent
DIST = "Michael's"
STORE = "4729"  # Greenly Crossings, Holland

# One parent URL per IN-STORE line+size (W&N Artists' Oil omitted: online-only).
PARENTS = [
    "https://www.michaels.com/product/gamblin-1980-oil-color-37ml-MMACGB198037",
    "https://www.michaels.com/product/gamblin-1980-oil-color-150ml-10577028",
    "https://www.michaels.com/product/gamblin-artist-grade-oil-colors-37ml--10518333",
    "https://www.michaels.com/product/gamblin-150ml-artist-grade-oil-colors-10518382",
    "https://www.michaels.com/product/winsor-newton-winton-oil-colour-tube-37ml-MD002570S",
    "https://www.michaels.com/product/winsor-newton-winton-675oz-oil-colour-paint-10019710",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def fetch(url):
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(f"{url}{sep}michaelsStore={STORE}",
          headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8",
                   "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def product_group(page):
    for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
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
    brand = "Gamblin" if "gamblin" in s else ("Winsor & Newton" if ("winton" in s or "winsor" in s) else None)
    if "1980" in s:
        line, grade = "1980", "student"
    elif "winton" in s:
        line, grade = "Winton", "student"
    elif "gamblin" in s and "artist" in s:
        line, grade = "Artist's Oil", "artist"
    else:
        line, grade = None, None
    m = re.search(r"(\d+)\s*ml", s)
    if m:
        size = int(m.group(1))
    else:
        oz = re.search(r"(\d+\.\d+)\s*oz", s)   # name uses "1.25oz"/"6.75oz" (slug drops the dot)
        size = round(float(oz.group(1)) * 29.5735) if oz else None
    return brand, line, grade, size


def sku_of(url):
    return url.rstrip("/").split("-")[-1]


def variant_urls(pg, parent_url):
    urls = {parent_url}
    for v in pg.get("hasVariant", []):
        u = (v.get("offers") or {}).get("url")
        if u:
            urls.add(u)
    rel = pg.get("isRelatedTo")
    if isinstance(rel, dict):
        r = rel.get("url") or []
        urls.update([r] if isinstance(r, str) else r)
    return urls


def color_from_title(page):
    m = re.search(r'property="og:title"\s+content="([^"]*)"', page) \
        or re.search(r'name="og:title"\s+content="([^"]*)"', page)
    if not m:
        return None
    t = htmllib.unescape(m.group(1))
    cm = re.search(r"Color:\s*(.+?)\s*\|", t)
    return cm.group(1).strip() if cm else None


def price_from_meta(page):
    m = re.search(r'name="og:price:amount"\s+content="([\d.]+)"', page) \
        or re.search(r'property="(?:product:)?price:amount"\s+content="([\d.]+)"', page)
    return float(m.group(1)) if m else None


def main():
    out = []
    for parent in PARENTS:
        try:
            page = fetch(parent)
        except Exception as e:
            print(f"  fetch error {parent}: {e}")
            continue
        pg = product_group(page)
        if not pg:
            print(f"  no ProductGroup: {parent}")
            continue
        brand, line, grade, size = detect(pg.get("name", ""), parent)
        if not brand or not line:
            print(f"  unrecognized line: {pg.get('name')!r}")
            continue

        # colors already detailed in hasVariant (no extra fetch needed)
        known = {}
        for v in pg.get("hasVariant", []):
            offers = v.get("offers") or {}
            u = offers.get("url")
            if u and v.get("color") and offers.get("price") is not None:
                known[sku_of(u)] = (v["color"].strip(), float(offers["price"]),
                                    "InStock" in (offers.get("availability") or "InStock"))

        n = 0
        for url in variant_urls(pg, parent):
            sku = sku_of(url)
            if sku in known:
                color, price, in_stock = known[sku]
            else:
                try:
                    vp = fetch(url)
                except Exception as e:
                    print(f"    variant fetch error {url}: {e}")
                    continue
                color = color_from_title(vp)
                price = price_from_meta(vp)
                in_stock = True  # national availability; UI flags "verify in store"
                time.sleep(0.4)  # be polite
            if not color or price is None:
                continue
            out.append({"brand": brand, "line": line, "grade": grade, "name": color,
                        "dist": DIST, "price": price, "size": size, "unit": "ml",
                        "url": url if url.startswith("http") else "https://www.michaels.com" + url,
                        "inStock": in_stock})
            n += 1
        print(f"  {pg.get('name', '').strip()}: {n} colors")
    print(f"\nMichael's: parsed {len(out)} color/price rows")
    write_prices_safely(ROOT / "prices" / "michaels.json", out)


if __name__ == "__main__":
    main()
