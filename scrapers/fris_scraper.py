"""
Fris Supply Shop scraper  ->  prices/fris.json

Fris runs on RAIN POS. Open-stock oils are sold as ONE product per line+size
(e.g. "GAMBLIN 1980s OIL 37ML") whose page lists every color with a regular and
an often-discounted sale price, plus per-store stock. Some colors are also sold
as standalone products (e.g. "1980 TITANIUM WHITE 150ML"); for those we use the
price shown on the listing card.

We read the "Downtown Holland" store (your local Fris, 49423) for price + stock.
Output rows are self-describing (brand/line/grade/color); the catalog only
enriches pigments where it has them.

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
from common import guess_line, extract_size, norm, ROOT

DIST = "Fris Supply Shop"
SITE = "https://www.frissupplyshop.com"
LISTING_URLS = ["https://www.frissupplyshop.com/shop/Paints-and-Mediums/Oil-Paints.htm"]
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
LINES = {
    "1980":           {"line": "1980",         "brand": "Gamblin",         "grade": "student", "tokens": ["1980"]},
    "gamblin_artist": {"line": "Artist's Oil", "brand": "Gamblin",         "grade": "artist",  "tokens": ["gamblin", "artist", "oils", "oil"]},
    "winton":         {"line": "Winton",       "brand": "Winsor & Newton", "grade": "student", "tokens": ["winton"]},
    "studio":         {"line": "Studio",       "brand": "Blick",           "grade": "student", "tokens": ["studio", "blick"]},
}


def detect_line(name):
    """Map a Fris product name to one of our tracked line keys, or None."""
    up = name.upper()
    if "1980" in up:
        return "1980"
    if "WINTON" in up:
        return "winton"
    if "GAMBLIN" in up and "ARTIST" in up:
        return "gamblin_artist"
    if "STUDIO" in up:
        return "studio"
    return None


def line_of(name):
    """Brand-aware line detection for Fris product names."""
    n = (name or "").lower()
    if "winton" in n:
        return "Winton"
    if "1980" in n:
        return "1980"
    if "blick" in n and "studio" in n:
        return "Studio"
    if "gamblin" in n and "artist" in n:
        return "Artist's Oil"
    return None

STORE_MARKER = "Downtown Holland"          # your local Fris (49423)
NEXT_LOC = ["Set as Default Location", "Godfrey", "Grand Rapids",
            "See All Locations", "available at"]
SET_WORDS = ("SET", "INTRO", "INTRODUCTORY", "TUBES", "ASSORT")


def fetch(url):
    return requests.get(url, headers=HEADERS, timeout=30)


def product_id(url):
    m = re.search(r"-x([0-9a-z]+)\.htm", url, re.I)
    return m.group(1) if m else url


def name_from_anchor(a, href):
    name = a.get_text(" ", strip=True) or (a.find("img").get("alt", "") if a.find("img") else "")
    if not name:
        m = re.search(r"/p/(.+?)-x[0-9a-z]+\.htm", href, re.I)
        if m:
            name = m.group(1).replace("-", " ")
    return name


def price_near(a):
    node = a
    for _ in range(4):
        node = node.parent
        if node is None:
            break
        m = re.search(r"\$\s*([\d]+(?:\.\d+)?)", node.get_text(" ", strip=True))
        if m:
            return float(m.group(1))
    return None


def clean_single_name(title, tokens):
    s = re.sub(r"\b\d+(?:\.\d+)?\s*ml\b", "", title, flags=re.I)
    for hint in tokens:
        s = re.sub(r"\b" + re.escape(hint) + r"\b", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip().title()


def crawl():
    """BFS the oil-paint listing + its sub-category pages. Return {id: {name,url,price}}."""
    queue, visited, products, pages = list(LISTING_URLS), set(), {}, 0
    while queue and pages < 25:
        page = queue.pop(0)
        if page in visited:
            continue
        visited.add(page)
        try:
            html = fetch(page).text
        except Exception as e:
            print(f"  crawl fetch error {page}: {e}")
            continue
        pages += 1
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select('a[href*="/p/"]'):
            href = a.get("href", "")
            if "/p/" not in href:
                continue
            url = href if href.startswith("http") else SITE + href
            pid = product_id(url)
            name = name_from_anchor(a, href)
            if not name:
                continue
            if pid not in products:                       # dedupe by stable product id
                products[pid] = {"name": name, "url": url, "price": price_near(a)}
            elif products[pid]["price"] is None:
                products[pid]["price"] = price_near(a)
        for a in soup.select('a[href*="/Oil-Paints/"]'):
            href = a.get("href", "")
            if "/p/" in href or not href.endswith(".htm"):
                continue
            url = href if href.startswith("http") else SITE + href
            if url not in visited and url not in queue:
                queue.append(url)
        time.sleep(1)
    print(f"  crawl: visited {pages} pages, {len(products)} unique products")
    return products


def parse_color_rows(text):
    rows = []
    for part in text.split("COLOR:")[1:]:
        m = re.match(r"\s*(.+?)\s*Price:\s*\$?\s*([\d]+(?:\.\d+)?)"
                     r"(?:\s*\$?\s*([\d]+(?:\.\d+)?))?", part)
        if not m:
            continue
        regular = float(m.group(2))
        sale = float(m.group(3)) if m.group(3) else None
        rows.append({"color": m.group(1).strip(),
                     "price": sale if sale is not None else regular})
    return rows


def parse_store_stock(text, marker=STORE_MARKER):
    i = text.find(marker)
    if i < 0:
        return {}
    rest = text[i + len(marker):]
    end = len(rest)
    for nm in NEXT_LOC:
        j = rest.find(nm)
        if 0 <= j < end:
            end = j
    stock = {}
    for m in re.finditer(r"([A-Z][A-Z0-9 /\-]+?):\s*(\d+)\b", rest[:end]):
        stock[norm(m.group(1))] = int(m.group(2))
    return stock


def scrape_product(name, url, listing_price):
    try:
        html = fetch(url).text
    except Exception as e:
        print(f"  product fetch error {url}: {e}")
        return []
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else name
    kind = detect_line(title) or detect_line(name)
    if not kind:
        return []
    cfg = LINES[kind]
    line, brand, grade = cfg["line"], cfg["brand"], cfg["grade"]
    size, unit = extract_size(title)
    text = soup.get_text(" ")
    colors = parse_color_rows(text)
    stock = parse_store_stock(text)
    rows = []
    if colors:
        for c in colors:
            in_stock = stock.get(norm(c["color"]), 0) > 0 if stock else True
            rows.append({"brand": brand, "line": line, "grade": grade,
                         "name": c["color"].title(), "dist": DIST, "price": c["price"],
                         "size": size, "unit": unit or "ml", "url": url, "inStock": in_stock})
    elif listing_price is not None:                       # standalone single-color product
        rows.append({"brand": brand, "line": line, "grade": grade,
                     "name": clean_single_name(title, cfg["tokens"]), "dist": DIST, "price": listing_price,
                     "size": size, "unit": unit or "ml", "url": url, "inStock": True})
    print(f"  {title}: colors={len(colors)} rows={len(rows)}")
    return rows


def main():
    products = crawl()
    tracked = {pid: p for pid, p in products.items()
               if detect_line(p["name"])
               and not any(w in p["name"].upper() for w in SET_WORDS)}
    print(f"  tracked: {[p['name'] for p in tracked.values()]}")
    out = []
    for p in tracked.values():
        out.extend(scrape_product(p["name"], p["url"], p["price"]))
        time.sleep(1)
    (ROOT / "prices").mkdir(exist_ok=True)
    (ROOT / "prices" / "fris.json").write_text(json.dumps(out, indent=2))
    print(f"\nFris: wrote {len(out)} color/price rows -> prices/fris.json")


if __name__ == "__main__":
    main()
