"""
Michael's scraper  ->  prices/michaels.json     STATUS: scaffold, needs a tuning run

Why Playwright: michaels.com renders price + store availability with JavaScript,
so a plain HTML fetch won't see them. Playwright drives a real headless browser.

Your store: Holland #4729 (3571 West Shore Dr, Greenly Crossings).
You confirmed: online price == shelf price, and "available for pickup today"
== in stock at that store. So we pin the store to 4729 and read both.

One-time setup:
  - Fill michaels_products.json with {product_id, url} for the colors you buy.
    (Find each color on michaels.com and paste its URL.)
  - pip install playwright && playwright install chromium

Run:  python scrapers/michaels_scraper.py

FIRST RUN: open one product page in your own browser with the Holland store
selected, right-click the price -> Inspect, and copy the real CSS selector into
PRICE_SEL / PICKUP_SEL below. They're best-guess placeholders until then.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, extract_size

DIST = "Michael's"
STORE_ID = "4729"            # Holland / Greenly Crossings
STORE_ZIP = "49423"

# --- selectors to confirm on first run (Inspect element) ---
PRICE_SEL = '[data-test="product-price"], .product-price, [itemprop="price"]'
PICKUP_SEL = '[data-test="fulfillment-pickup"], .pickup-availability'
PICKUP_OK_TEXT = "pickup today"   # phrase that means in-stock locally


def load_products():
    f = ROOT / "michaels_products.json"
    if not f.exists():
        print("Create michaels_products.json: [{\"product_id\":..., \"url\":...}, ...]")
        return []
    return json.loads(f.read_text())


def scrape():
    from playwright.sync_api import sync_playwright
    products = load_products()
    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        # pin the store: Michael's stores the selection in a cookie. Setting it
        # up front avoids the location prompt. Confirm the cookie name on run 1.
        ctx.add_cookies([{
            "name": "preferredStoreId", "value": STORE_ID,
            "domain": ".michaels.com", "path": "/",
        }])
        page = ctx.new_page()
        for prod in products:
            try:
                page.goto(prod["url"], timeout=45000, wait_until="networkidle")
                price_txt = page.locator(PRICE_SEL).first.inner_text(timeout=10000)
                price = float(price_txt.replace("$", "").split()[0])
                try:
                    pickup_txt = page.locator(PICKUP_SEL).first.inner_text(timeout=5000)
                except Exception:
                    pickup_txt = ""
                in_stock = PICKUP_OK_TEXT in pickup_txt.lower()
                size, unit = extract_size(prod["url"]) if False else (prod.get("size"), prod.get("unit", "ml"))
                out.append({
                    "product_id": prod["product_id"], "dist": DIST,
                    "price": price, "size": size, "unit": unit,
                    "url": prod["url"], "inStock": in_stock,
                })
                print(f"  ok {prod['product_id']}: ${price} pickup={in_stock}")
            except Exception as e:
                print(f"  FAILED {prod.get('product_id')}: {e}")
        browser.close()
    return out


if __name__ == "__main__":
    rows = scrape()
    (ROOT / "prices").mkdir(exist_ok=True)
    (ROOT / "prices" / "michaels.json").write_text(json.dumps(rows, indent=2))
    print(f"Michael's: wrote {len(rows)} rows -> prices/michaels.json")
