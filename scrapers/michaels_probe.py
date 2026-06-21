"""
Michael's probe v6: (1) get full variant list from JSON-LD isRelatedTo.url,
(2) find exactly where a variant page lists its price.
"""
import json
import re
import urllib.request

PARENTS = {
    "Gamblin 1980 37mL": "https://www.michaels.com/product/gamblin-1980-oil-color-37ml-MMACGB198037",
    "Winton 37mL": "https://www.michaels.com/product/winsor-newton-winton-oil-colour-tube-37ml-MD002570S",
}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
          "Accept": "text/html,*/*;q=0.8", "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=45) as r:
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


for label, parent in PARENTS.items():
    print("\n" + "=" * 70)
    print(label)
    html = fetch(parent)
    pg = product_group(html)
    related = []
    if pg:
        rel = pg.get("isRelatedTo")
        if isinstance(rel, dict):
            related = rel.get("url") or []
            if isinstance(related, str):
                related = [related]
    print(f"  JSON-LD isRelatedTo url count: {len(related)}")
    # also regex the whole HTML for any /product/...same-line... urls
    allurls = sorted(set(re.findall(r'https://www\.michaels\.com/product/[A-Za-z0-9%\-]+', html)))
    print(f"  total distinct /product/ urls in HTML: {len(allurls)}")

    test = related[-1] if related else (allurls[-1] if allurls else None)
    if not test:
        print("  no variant url to test"); continue
    vh = fetch(test)
    title = re.search(r'property="og:title"\s+content="([^"]+)"', vh)
    price_metas = [m for m in re.findall(r"<meta[^>]+>", vh) if "price" in m.lower()]
    print(f"  test variant: {test}")
    print(f"  og:title: {title.group(1) if title else None}")
    print(f"  meta tags containing 'price': {price_metas[:6]}")
    pvg = product_group(vh)
    print(f"  variant page has ProductGroup JSON-LD: {bool(pvg)}")
    for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', vh, re.S):
        try:
            d = json.loads(blk)
        except Exception:
            continue
        for it in (d if isinstance(d, list) else [d]):
            if isinstance(it, dict) and it.get("@type") == "Product":
                print(f"  single Product JSON-LD offers: {json.dumps(it.get('offers'))[:200]}")
print("\nProbe v6 complete.")
