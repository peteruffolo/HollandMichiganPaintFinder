"""
Fris Supply Shop scraper  ->  prices/fris.json

Fris runs on RAIN POS. Open-stock oils are sold as ONE product per line+size
(e.g. "GAMBLIN 1980s OIL 37ML") with every color in a list, each row showing a
regular price and an often-discounted sale price. The product page also lists
per-color stock for each physical store. We read the "Downtown Holland" store
(your local Fris, 49423) for both price and in-stock.

Output rows are self-describing (brand/line/grade/color), so the catalog does
NOT need an entry per color -- it only enriches pigments where it has them.

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
LISTING_URLS = [
    "https://www.frissupplyshop.com/shop/Paints-and-Mediums/Oil-Paints.htm",
    "https://www.frissupplyshop.com/shop/Paints-and-Mediums.htm",
]
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
LINE_BRAND = {"1980": "Gamblin", "Winton": "Winsor & Newton", "Studio": "Blick"}
LINE_GRADE = {"1980": "student", "Winton": "student", "Studio": "student"}
TRACKED_LINES = set(LINE_BRAND)

# your local Fris store; stock + pricing read from here
STORE_MARKER = "Downtown Holland"
NEXT_LOC = ["Set as Default Location", "Godfrey", "Grand Rapids",
            "See All Locations", "available at"]
SET_WORDS = ("SET", "INTRO", "INTRODUCTORY", "TUBES", "ASSORT")


def fetch(url):
    return requests.get(url, headers=HEADERS, timeout=30)


def listing_products():
    """Return [(name, url)] of tracked open-stock products from the listing pages."""
    for base in LISTING_URLS:
        found, seen = [], set()
        try:
            html = fetch(base).text
        except Exception as e:
            print(f"  listing fetch error {base}: {e}")
            continue
        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.select('a[href*="/p/"]')
        names_seen = []
        for a in anchors:
            href = a.get("href", "")
            if "/p/" not in href:
                continue
            name = a.get_text(" ", strip=True) or (a.find("img").get("alt", "") if a.find("img") else "")
            if not name:  # Fris product links are nameless; derive from the URL slug
                m = re.search(r"/p/(.+?)-x[0-9a-z]+\.htm", href, re.I)
                if m:
                    name = m.group(1).replace("-", " ")
            if not name:
                continue
            names_seen.append(name)
            up = name.upper()
            if guess_line(name) not in TRACKED_LINES:
                continue
            if any(w in up for w in SET_WORDS):
                continue
            url = href if href.startswith("http") else SITE + href
            if url in seen:
                continue
            seen.add(url)
            found.append((name, url))
        print(f"  listing: {base}")
        print(f"           {len(anchors)} product links, {len(names_seen)} named, {len(found)} tracked")
        if not found and names_seen:
            print(f"           sample names: {names_seen[:12]}")
        if found:
            print(f"           tracked: {[n for n, _ in found]}")
            return found
    return []


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
                     "price": sale if sale is not None else regular,
                     "regular": regular, "sale": sale})
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
    block = rest[:end]
    stock = {}
    for m in re.finditer(r"([A-Z][A-Z0-9 /\-]+?):\s*(\d+)\b", block):
        stock[norm(m.group(1))] = int(m.group(2))
    return stock


def scrape_product(name, url):
    try:
        html = fetch(url).text
    except Exception as e:
        print(f"  product fetch error {url}: {e}")
        return []
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else name
    line = guess_line(title) or guess_line(name)
    brand, grade = LINE_BRAND.get(line), LINE_GRADE.get(line)
    if not line or not brand:
        return []
    size, unit = extract_size(title)
    text = soup.get_text(" ")
    colors = parse_color_rows(text)
    stock = parse_store_stock(text)
    rows = []
    if colors:
        for c in colors:
            in_stock = stock.get(norm(c["color"]), 0) > 0 if stock else True
            rows.append({
                "brand": brand, "line": line, "grade": grade,
                "name": c["color"].title(), "dist": DIST,
                "price": c["price"], "size": size, "unit": unit or "ml",
                "url": url, "inStock": in_stock,
            })
    else:
        prices = re.findall(r"\$\s*([\d]+(?:\.\d+)?)", text)
        if prices:
            rows.append({
                "brand": brand, "line": line, "grade": grade,
                "name": title.title(), "dist": DIST,
                "price": float(prices[0]), "size": size, "unit": unit or "ml",
                "url": url, "inStock": True,
            })
    print(f"  {title}: COLOR-markers={text.count('COLOR:')} "
          f"dollar-amounts={len(re.findall(r'[$]\\s*[0-9]', text))} "
          f"colors-parsed={len(colors)} rows={len(rows)}")
    return rows


def main():
    out = []
    for name, url in listing_products():
        out.extend(scrape_product(name, url))
        time.sleep(1)
    (ROOT / "prices").mkdir(exist_ok=True)
    (ROOT / "prices" / "fris.json").write_text(json.dumps(out, indent=2))
    print(f"\nFris: wrote {len(out)} color/price rows -> prices/fris.json")


if __name__ == "__main__":
    main()
