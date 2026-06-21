"""
Michael's FULL-VARIANT probe (diagnostics only).
The JSON-LD ProductGroup is capped at 25 variants, but the complete color list
is embedded in the Next.js __next_f data chunks. This probe tries to recover ALL
colors + prices from the raw HTML and reports the structure so we can parse it.
"""
import re
import urllib.request

URLS = {
    "Gamblin 1980 37mL": "https://www.michaels.com/product/gamblin-1980-oil-color-37ml-MMACGB198037",
    "Winton 37mL": "https://www.michaels.com/product/winsor-newton-winton-oil-colour-tube-37ml-MD002570S",
}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def raw_fetch(url):
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
    print(label, url)
    try:
        html = raw_fetch(url)
    except Exception as e:
        print("  fetch error:", e)
        continue
    print(f"  bytes={len(html)}  has __next_f={'__next_f' in html}")

    # how many key occurrences (escaped form used inside __next_f JS strings)
    for kw in [r'\"color\"', r'"color"', r'\"price\"', r'"price"', r'\"listPrice\"',
               r'\"salePrice\"', r'\"orderable\"', r'\"variationValues\"',
               r'\"sku\"', r'\"productId\"', r'\"name\"']:
        print(f"    count {kw!r}: {len(re.findall(re.escape(kw), html))}")

    # recover color names (both escaped and plain)
    colors = uniq(re.findall(r'\\"color\\":\\"([^"\\]+)\\"', html)
                  + re.findall(r'"color":"([^"\\]+)"', html))
    print(f"\n  COLORS recovered: {len(colors)}")
    print("   ", colors)

    # recover prices
    prices = re.findall(r'\\"price\\":\s*([\d.]+)', html) + re.findall(r'"price":\s*([\d.]+)', html)
    print(f"  PRICE values found: {len(prices)} (sample: {prices[:12]})")

    # context window around first escaped color -> shows how price relates to color
    m = re.search(r'\\"color\\":\\"[^"\\]+\\"', html)
    if m:
        s = max(0, m.start() - 250)
        print("\n  --- context around first variant ---")
        print("  " + html[s:m.end() + 250].replace("\\", ""))
print("\nProbe complete.")
