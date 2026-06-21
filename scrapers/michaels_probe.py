"""
Michael's feasibility probe v2  (diagnostics only -- writes nothing)

Determines the most efficient extraction path:
  PART A: does the RAW HTML (no browser) already embed the product data
          (__NEXT_DATA__ / __next_f / JSON-LD / og:price)?  -> lightweight path
  PART B: rendered page -- inspect window.__NEXT_DATA__ for all-variant data,
          and render the category page to confirm product discovery.

Run via the "Michaels probe" workflow.
"""
import re
import urllib.request

from playwright.sync_api import sync_playwright

PRODUCT = "https://www.michaels.com/product/gamblin-1980-oil-color-37ml-MMACGB198037"
CATEGORY = ("https://www.michaels.com/shop/art-supplies/paint-painting-supplies/"
            "fine-art-paint/oil-paint/open-stock-oil-paint")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
KEYWORDS = ["colorVariations", "variants", "variationValues", "skus", "listPrice",
            "salePrice", "onlinePrice", "price", "inventory", "availability",
            "inStock", "pickup", "color"]


def report_blob(blob, label):
    print(f"  [{label}] length={len(blob)}")
    present = [k for k in KEYWORDS if k in blob]
    print(f"  [{label}] keywords present: {present}")
    i = blob.find('"price"')
    if i < 0:
        i = blob.lower().find("price")
    if i >= 0:
        print(f"  [{label}] sample near 'price': ...{blob[max(0,i-40):i+180]}...")


def raw_fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return getattr(r, "status", 200), r.read().decode("utf-8", "replace")


print("=== PART A: RAW HTML (no browser) ===")
try:
    status, html = raw_fetch(PRODUCT)
    print(f"  status={status} bytes={len(html)}")
    print(f"  has __NEXT_DATA__ : {'__NEXT_DATA__' in html}")
    print(f"  has __next_f      : {'__next_f' in html}")
    print(f"  has og:price      : {'og:price' in html}")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        report_blob(m.group(1), "raw __NEXT_DATA__")
    ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    print(f"  JSON-LD blocks: {len(ld)}")
    for j, blk in enumerate(ld[:2]):
        print(f"  JSON-LD[{j}] (first 400): {blk.strip()[:400]}")
except Exception as e:
    print("  raw fetch error:", e)

print("\n=== PART B: RENDERED (browser) ===")
with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 900}, locale="en-US")
    page = ctx.new_page()
    try:
        page.goto(PRODUCT, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        nd = page.evaluate("() => window.__NEXT_DATA__ ? JSON.stringify(window.__NEXT_DATA__) : null")
        if nd:
            report_blob(nd, "rendered __NEXT_DATA__")
        else:
            print("  window.__NEXT_DATA__ not present (likely App Router / __next_f)")
            full = page.content()
            print(f"  rendered HTML has __next_f: {'__next_f' in full}  length={len(full)}")
    except Exception as e:
        print("  product render error:", e)

    try:
        page.goto(CATEGORY, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(7000)
        links = page.evaluate(
            "() => Array.from(document.querySelectorAll('a[href*=\"/product/\"]'))"
            ".map(a => a.getAttribute('href'))")
        uniq = sorted(set(l for l in links if l))
        print(f"\n  CATEGORY rendered: {len(uniq)} unique /product/ links")
        for u in uniq[:15]:
            print("    ", u)
    except Exception as e:
        print("  category render error:", e)
    browser.close()
print("\nProbe v2 complete.")
