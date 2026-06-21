"""
Blick feasibility probe (diagnostics only -- writes nothing).
Checks whether price / colors live in the RAW HTML (JSON-LD, meta, or embedded
JSON) for an item page and a products(listing) page, and whether the listing
page exposes item URLs for discovery.
"""
import json
import re
import urllib.request

ITEM = "https://www.dickblick.com/items/gamblin-1980-oils-phthalo-blue-37-ml-tube/"
PRODUCTS = "https://www.dickblick.com/products/gamblin-1980-oil-colors/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
EMBEDS = ["__NEXT_DATA__", "__next_f", "__INITIAL_STATE__", "__APOLLO_STATE__",
          "application/ld+json", "og:price", "product:price", "gtmDataLayer", "dataLayer"]
PRICEKEYS = ["price", "listPrice", "salePrice", "offers", "lowPrice", "sku", "color", "variant"]


def raw_fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
          "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return getattr(r, "status", 200), r.read().decode("utf-8", "replace")


def analyze(url, is_listing):
    print("\n" + "=" * 70)
    print("URL:", url)
    try:
        status, html = raw_fetch(url)
    except Exception as e:
        print("  fetch error:", e)
        return
    print(f"  status={status} bytes={len(html)}")
    for e in EMBEDS:
        if e in html:
            print(f"  present: {e}")
    # JSON-LD
    lds = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    print(f"  JSON-LD blocks: {len(lds)}")
    for blk in lds:
        try:
            data = json.loads(blk)
        except Exception:
            print("     (one block failed to parse)")
            continue
        for it in (data if isinstance(data, list) else [data]):
            if not isinstance(it, dict):
                continue
            t = it.get("@type")
            print(f"     @type={t} keys={list(it.keys())[:10]}")
            if t in ("Product", "ProductGroup"):
                offers = it.get("offers")
                print(f"        offers={json.dumps(offers)[:200] if offers else None}")
                hv = it.get("hasVariant")
                if hv:
                    print(f"        hasVariant count={len(hv)}; first={json.dumps(hv[0])[:240]}")
    # price hints in raw text
    for kw in ['"price"', 'product:price:amount', 'og:price']:
        i = html.find(kw)
        if i >= 0:
            print(f"  sample @ {kw}: ...{html[i:i+120]}...")
    if is_listing:
        items = sorted(set(re.findall(r'/items/[a-z0-9\-]+/', html)))
        print(f"  /items/ links in raw HTML: {len(items)}")
        for u in items[:8]:
            print("    ", u)


analyze(ITEM, is_listing=False)
analyze(PRODUCTS, is_listing=True)
print("\nBlick probe complete.")
