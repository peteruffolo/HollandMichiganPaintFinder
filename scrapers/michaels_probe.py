"""
Michael's probe v5: confirm the FULL variant-URL list is in the parent page, and
that each variant page exposes price + color in meta tags (no browser).
"""
import re
import urllib.request

URLS = {
    "Gamblin 1980 37mL": "https://www.michaels.com/product/gamblin-1980-oil-color-37ml-MMACGB198037",
    "Winton 37mL": "https://www.michaels.com/product/winsor-newton-winton-oil-colour-tube-37ml-MD002570S",
}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
          "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def uniq(seq):
    out = []
    for x in seq:
        if x not in out:
            out.append(x)
    return out


for label, url in URLS.items():
    print("\n" + "=" * 70)
    print(label)
    html = fetch(url)
    slug = url.split("/product/")[1]
    m = re.search(r"(.*?\d+ml)", slug)        # prefix up to the size token
    prefix = m.group(1) if m else slug
    variants = uniq(re.findall(r"/product/" + re.escape(prefix) + r"-{1,2}[A-Za-z0-9]+", html))
    print(f"  prefix={prefix!r}")
    print(f"  unique variant URLs found: {len(variants)}")
    for v in variants[:6]:
        print("    ", v)

    if variants:
        v0 = "https://www.michaels.com" + variants[0]
        vh = fetch(v0)
        price = re.search(r'property="(?:product:)?price:amount"\s+content="([\d.]+)"', vh) \
            or re.search(r'property="og:price:amount"\s+content="([\d.]+)"', vh)
        title = re.search(r'property="og:title"\s+content="([^"]+)"', vh)
        avail = re.search(r'property="product:availability"\s+content="([^"]+)"', vh)
        print(f"  sample variant: {variants[0]}")
        print(f"     price meta: {price.group(1) if price else None}")
        print(f"     title meta: {title.group(1) if title else None}")
        print(f"     avail meta: {avail.group(1) if avail else None}")
print("\nProbe v5 complete.")
