"""
Michael's feasibility probe  (diagnostics only -- writes nothing)

Renders one Michael's product page in a real headless browser and reports:
  * whether we were blocked (bot wall / captcha)
  * whether the PRICE is present in the rendered DOM
  * whether the COLOR list is present (and how many)
  * whether any STORE AVAILABILITY UI is present
  * which candidate CSS selectors actually match (to inform the real scraper)

Run via the "Michaels probe" workflow (manual dispatch).
Deps: pip install playwright ; playwright install --with-deps chromium
"""
import re

from playwright.sync_api import sync_playwright

# Two parents: a 1980 (student) and an Artist grade, both 37 mL.
TEST_URLS = [
    "https://www.michaels.com/product/gamblin-1980-oil-color-37ml-MMACGB198037",
    "https://www.michaels.com/product/gamblin-artist-grade-oil-colors-37ml--D021532S",
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

BLOCK_HINTS = ["pardon our interruption", "access denied", "are you a human",
               "unusual traffic", "captcha", "request blocked", "bot detection"]

PRICE_SELECTORS = ['[data-testid*="price" i]', '[class*="price" i]', '[itemprop="price"]',
                   '[data-test*="price" i]']
COLOR_SELECTORS = ['[aria-label*="Color" i]', '[data-testid*="swatch" i]', '[class*="swatch" i]',
                   'button[role="radio"]', '[data-testid*="variant" i]', 'select option']
AVAIL_SELECTORS = ['[data-testid*="fulfillment" i]', '[data-testid*="pickup" i]',
                   '[class*="availability" i]', '[class*="pickup" i]', '[class*="instock" i]']
AVAIL_WORDS = ["pickup", "in stock", "out of stock", "available", "aisle", "find in store"]


def probe(page, url):
    print("\n" + "=" * 70)
    print("URL:", url)
    resp = None
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print("  goto error:", e)
        return
    try:
        page.wait_for_timeout(6000)  # let client-side render
    except Exception:
        pass

    status = resp.status if resp else "?"
    title = ""
    try:
        title = page.title()
    except Exception:
        pass
    body = ""
    try:
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
    except Exception:
        pass
    low = body.lower()

    print(f"  status={status}  final_url={page.url}")
    print(f"  title={title!r}")
    print(f"  body_text_length={len(body)}")
    blocked = [h for h in BLOCK_HINTS if h in low]
    print(f"  BLOCK hints found: {blocked if blocked else 'none'}")

    dollar = re.findall(r"\$\s*\d+(?:\.\d+)?", body)
    print(f"  $-amounts in rendered text: {dollar[:8]}")

    def count(sels):
        out = []
        for s in sels:
            try:
                n = page.locator(s).count()
            except Exception:
                n = -1
            if n:
                out.append((s, n))
        return out

    print("  price selectors that matched:", count(PRICE_SELECTORS) or "none")
    color_hits = count(COLOR_SELECTORS)
    print("  color selectors that matched:", color_hits or "none")
    print("  availability selectors that matched:", count(AVAIL_SELECTORS) or "none")
    avail_words = [w for w in AVAIL_WORDS if w in low]
    print("  availability words in text:", avail_words or "none")

    # quick verdict
    ok_price = bool(dollar)
    ok_colors = any(n >= 3 for _, n in color_hits)
    verdict = "LOOKS USABLE" if (not blocked and ok_price) else "PROBLEM"
    print(f"  >>> {verdict}  (price={'Y' if ok_price else 'N'}, "
          f"colors={'Y' if ok_colors else '?'}, blocked={'Y' if blocked else 'N'})")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 900},
                                  locale="en-US")
        page = ctx.new_page()
        for url in TEST_URLS:
            probe(page, url)
        browser.close()
    print("\nProbe complete.")


if __name__ == "__main__":
    main()
