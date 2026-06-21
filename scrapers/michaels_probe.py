"""
Michael's probe v3 -- dump the ProductGroup JSON-LD structure (diagnostics only).
Confirms exact field names for color / price / availability so the real scraper
can parse it correctly. No browser needed.
"""
import json
import re
import urllib.request

URLS = [
    "https://www.michaels.com/product/gamblin-1980-oil-color-37ml-MMACGB198037",
    "https://www.michaels.com/product/gamblin-artist-grade-oil-colors-37ml--10518333",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def raw_fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def find_product_group(html):
    for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(blk)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict) and it.get("@type") == "ProductGroup":
                return it
    return None


for url in URLS:
    print("\n" + "=" * 70)
    print("URL:", url)
    try:
        html = raw_fetch(url)
    except Exception as e:
        print("  fetch error:", e)
        continue
    pg = find_product_group(html)
    if not pg:
        print("  no ProductGroup JSON-LD found")
        continue
    print("  ProductGroup top-level keys:", list(pg.keys()))
    variants = pg.get("hasVariant") or pg.get("hasVariants") or []
    print("  variant count:", len(variants))
    if variants:
        print("\n  --- FULL first variant ---")
        print(json.dumps(variants[0], indent=2)[:1600])
        print("\n  --- summary of up to 8 variants ---")
        for v in variants[:8]:
            offers = v.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            print(f"    name={v.get('name')!r}")
            print(f"        color={v.get('color')!r} sku={v.get('sku')!r} "
                  f"price={offers.get('price')!r} avail={offers.get('availability')!r}")
print("\nProbe v3 complete.")
