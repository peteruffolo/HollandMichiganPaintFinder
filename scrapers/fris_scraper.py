"""
Fris Supply Shop scraper  ->  prices/fris.json

Fris runs on the RAIN POS platform with server-rendered listing pages. This
version uses a browser-like User-Agent (some store sites serve an empty page to
non-browser clients), tries the oil-paint page first and falls back to the main
paints page, and prints diagnostics so a zero-result run is easy to debug.

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
from common import load_catalog, match_product, extract_size, guess_line, ROOT

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
TRACKED_LINES = {"1980", "Winton"}


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    return r


def parse_cards(html):
    """Return list of {name, price, url, in_stock} for product cards on a page."""
    soup = BeautifulSoup(html, "html.parser")
    cards, seen = [], set()
    anchors = soup.select('a[href*="/p/"]')
    for a in anchors:
        href = a.get("href", "")
        if "/p/" not in href:
            continue
        name = a.get_text(" ", strip=True)
        if not name:
            img = a.find("img")
            name = img.get("alt", "").strip() if img else ""
        if not name:  # derive from the URL slug as a last resort
            m = re.search(r"/p/(.+?)-x[0-9a-z]+\.htm", href, re.I)
            if m:
                name = m.group(1).replace("-", " ")
        if not name:
            continue
        url = href if href.startswith("http") else SITE + href
        if url in seen:
            continue
        seen.add(url)
        # find this card's price: climb to the smallest ancestor holding a $ price
        price, sold_out, node = None, False, a
        for _ in range(3):
            node = node.parent
            if node is None:
                break
            txt = node.get_text(" ", strip=True)
            if "sold out" in txt.lower():
                sold_out = True
            prices = re.findall(r"\$(\d+(?:\.\d+)?)", txt)
            if 1 <= len(prices) <= 2:
                price = float(prices[0])
                break
            if len(prices) > 2:  # climbed past the card into the whole grid
                break
        cards.append({"name": name, "price": price, "url": url, "in_stock": not sold_out})
    return cards, len(anchors)


def harvest():
    """Try each listing URL (with pagination) until one yields product cards."""
    for base in LISTING_URLS:
        all_cards, seen_urls = [], set()
        for n in range(1, 21):
            url = base if n == 1 else f"{base}?pageNum={n}"
            try:
                r = fetch(url)
            except Exception as e:
                print(f"  fetch error {url}: {e}")
                break
            html = r.text
            cards, n_anchors = parse_cards(html)
            if n == 1:
                print(f"  [diag] {url}")
                print(f"         status={r.status_code} bytes={len(html)} "
                      f"raw '/p/' count={html.count('/p/')} parsed anchors={n_anchors}")
                up = html.upper()
                print(f"         contains 1980={'1980' in up} WINTON={'WINTON' in up}")
                if not cards:
                    snippet = re.sub(r"\s+", " ", html[:400])
                    print(f"         (no cards) first 400 chars: {snippet}")
            fresh = [c for c in cards if c["url"] not in seen_urls]
            for c in fresh:
                seen_urls.add(c["url"])
            all_cards.extend(fresh)
            if not fresh:
                break
            time.sleep(1)
        if all_cards:
            print(f"  -> {len(all_cards)} cards from {base}")
            return all_cards
    return []


def main():
    catalog = load_catalog()
    cards = harvest()
    out, matched, skipped = [], 0, 0
    for c in cards:
        line = guess_line(c["name"])
        if line not in TRACKED_LINES:
            skipped += 1
            continue
        entry, score = match_product(c["name"], catalog, restrict_line=line)
        if not entry or score < 0.6:
            skipped += 1
            print(f"  no catalog match: {c['name']!r}")
            continue
        size, unit = extract_size(c["name"])
        out.append({
            "product_id": entry["id"], "dist": DIST,
            "price": c["price"], "size": size, "unit": unit or "ml",
            "url": c["url"], "inStock": c["in_stock"],
        })
        matched += 1

    (ROOT / "prices").mkdir(exist_ok=True)
    (ROOT / "prices" / "fris.json").write_text(json.dumps(out, indent=2))
    print(f"\nFris: matched {matched}, skipped {skipped} -> prices/fris.json")


if __name__ == "__main__":
    main()
