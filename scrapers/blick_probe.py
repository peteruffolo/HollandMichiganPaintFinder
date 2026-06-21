"""Blick probe v3: dump the ProductGroup.hasVariant structure (color/size/price)."""
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


html = fetch(PRODUCTS)
for blk in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
    try:
        data = json.loads(blk)
    except Exception:
        continue
    items = data if isinstance(data, list) else [data]
    for it in items:
        if isinstance(it, dict) and it.get("@type") == "ProductGroup":
            hv = it.get("hasVariant", [])
            print("ProductGroup name:", it.get("name"))
            print("variesBy:", it.get("variesBy"))
            print("hasVariant count:", len(hv))
            for v in hv[:3]:
                print("\n--- variant ---")
                print(json.dumps(v, indent=2)[:900])
print("\nBlick probe v3 complete.")
