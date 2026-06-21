"""
Blick probe v2: read the embedded product data on a products(listing) page.
Checks JSON-LD (loose match) and __NEXT_DATA__, and reports the array of products
with their fields so we can parse all colors+sizes+prices from one fetch.
"""
import json
import re
import urllib.request

PRODUCTS = "https://www.dickblick.com/products/gamblin-1980-oil-colors/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
          "Accept": "text/html,*/*;q=0.8", "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def find_product_arrays(obj, path="", out=None, depth=0):
    if out is None:
        out = []
    if depth > 8:
        return out
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and any(k in obj[0] for k in ("price", "sku", "offers")):
            out.append((path, len(obj), obj[0]))
        for i, v in enumerate(obj[:4]):
            find_product_arrays(v, f"{path}[{i}]", out, depth + 1)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            find_product_arrays(v, f"{path}.{k}", out, depth + 1)
    return out


html = fetch(PRODUCTS)
print(f"bytes={len(html)}")

print("\n=== JSON-LD (loose match) ===")
lds = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
print(f"blocks: {len(lds)}")
for blk in lds[:4]:
    try:
        data = json.loads(blk)
    except Exception as e:
        print("  parse fail:", e); continue
    items = data if isinstance(data, list) else [data]
    for it in items[:1]:
        if isinstance(it, dict):
            print("  @type:", it.get("@type"), "| keys:", list(it.keys())[:12])
            if "@graph" in it:
                g = it["@graph"]
                print("   @graph len:", len(g), "first @type:", g[0].get("@type") if g else None)
            if it.get("@type") in ("ItemList", "Product") or "itemListElement" in it:
                print("   sample:", json.dumps(it)[:400])

print("\n=== __NEXT_DATA__ ===")
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
if m:
    try:
        nd = json.loads(m.group(1))
        arrays = find_product_arrays(nd.get("props", {}))
        arrays.sort(key=lambda a: -a[1])
        print(f"  product-like arrays found: {len(arrays)}")
        for path, n, sample in arrays[:3]:
            print(f"\n  path={path}  count={n}")
            print(f"  sample keys: {list(sample.keys())}")
            for k in ("name", "title", "color", "size", "sku", "price", "salePrice",
                      "listPrice", "url", "slug", "offers"):
                if k in sample:
                    print(f"     {k} = {json.dumps(sample[k])[:160]}")
    except Exception as e:
        print("  parse error:", e)
else:
    print("  __NEXT_DATA__ not found")
print("\nBlick probe v2 complete.")
