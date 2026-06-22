"""
Blick enrichment pass  ->  enrichment.json   (occasional manual job)

Pigments and true paint colors don't live in the price feeds, but Blick's item
pages have both: a "Pigment Information" section listing Colour Index codes, and
a swatch image of the actual paint. This visits each UNIQUE color once, extracts
its pigment codes, and samples a representative hex from its swatch image.

The result (a big catalog-like list) is merged by build_data.py via the same
fuzzy matcher used for the hand catalog, so EVERY distributor's rows for that
brand+line+color gain pigments + swatch -- not just Blick's.

Run (manual workflow). Env ENRICH_LIMIT:
    >0  -> dry run: sample that many colors, print details, write nothing
     0  -> full run: sample all colors, write enrichment.json
"""
import io
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT
from blick_scraper import LINES, fetch, product_group, display_name, UA

PIG_RE = re.compile(r"\bP(?:Bk|Br|B|G|M|O|R|V|W|Y)\d{1,3}(?::\d+)?\b", re.IGNORECASE)
SWATCH_RE = re.compile(r"https://cld-assets\.dick-blick\.com/image/upload/[^\"'\s)]*?-s-4ww[^\"'\s)]*")
SITE = "https://www.dickblick.com"


def _norm_pig(c):
    c = c.upper().replace("PBR", "PBr").replace("PBK", "PBk")
    return c


def next_data(page):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', page, re.S)
    try:
        return json.loads(m.group(1)) if m else None
    except Exception:
        return None


def sku_to_itemurl(page):
    """Map itemSku -> /items/ URL from __NEXT_DATA__ pageProps.product.skUs."""
    nd = next_data(page) or {}
    out = {}
    try:
        for s in nd["props"]["pageProps"]["product"]["skUs"]:
            skuobj = s.get("sku")
            sku = skuobj.get("itemSku") if isinstance(skuobj, dict) else skuobj
            if sku and s.get("url"):
                out[sku] = s["url"]
    except Exception:
        pass
    return out


def pigments_from_item(html):
    """Codes listed under 'contains the following pigments', before the detail block."""
    low = html.lower()
    i = low.find("contains the following pigments")
    if i < 0:
        return []
    region = html[i:i + 700]
    for stop in ["Pigment Name", "Pigment Type", "Chemical Name", "SDS"]:
        j = region.find(stop)
        if j > 0:
            region = region[:j]
            break
    codes = []
    for c in PIG_RE.findall(region):
        c = _norm_pig(c)
        if c not in codes:
            codes.append(c)
    return codes


def swatch_url(html):
    m = SWATCH_RE.search(html)
    return m.group(0) if m else None


def sample_hex(url):
    try:
        from PIL import Image
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        im = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = im.size
        box = im.crop((int(w * 0.3), int(h * 0.3), int(w * 0.7), int(h * 0.7)))
        r_, g_, b_ = box.resize((1, 1)).getpixel((0, 0))   # average color of swatch center
        return "#%02x%02x%02x" % (r_, g_, b_)
    except Exception:
        return None


def main():
    limit = int(os.environ.get("ENRICH_LIMIT", "0") or "0")
    seen = set()
    entries = []
    n = 0
    for cfg in LINES:
        try:
            page = fetch(cfg["url"])
        except Exception as e:
            print(f"  line fetch error {cfg['url']}: {e}")
            continue
        pg = product_group(page)
        if not pg:
            print(f"  no ProductGroup: {cfg['url']}")
            continue
        items = sku_to_itemurl(page)
        for v in pg.get("hasVariant", []):
            if "set" in (v.get("description") or "").lower():
                continue
            color = (v.get("color") or "").strip()
            name = display_name(v.get("name", ""), color)
            key = (cfg["brand"], cfg["line"], name.lower())
            if not name or key in seen:
                continue
            seen.add(key)
            url = items.get(v.get("sku")) or (v.get("offers") or {}).get("url")
            if url and url.startswith("/"):
                url = SITE + url
            if not url:
                continue
            try:
                ih = fetch(url)
            except Exception as e:
                print(f"    item fetch error {url}: {e}")
                continue
            pigs = pigments_from_item(ih)
            sw = swatch_url(ih)
            hx = sample_hex(sw) if sw else None
            entries.append({"brand": cfg["brand"], "line": cfg["line"], "grade": cfg["grade"],
                            "name": name, "pigments": pigs, "hex": hx or "#888888", "swatch": sw})
            n += 1
            if limit:
                print(f"  [{cfg['line']}] {name!r}: pigments={pigs} hex={hx} swatch={'yes' if sw else 'no'}")
                if n >= limit:
                    print(f"\nDRY RUN ({limit} colors) — nothing written. "
                          f"Re-run with limit 0 for the full pass.")
                    return
            time.sleep(0.3)
        time.sleep(1)
    (ROOT / "enrichment.json").write_text(json.dumps(entries, indent=2))
    withpig = sum(1 for e in entries if e["pigments"])
    withhex = sum(1 for e in entries if e["hex"] != "#888888")
    print(f"\nBlick enrich: {len(entries)} colors -> enrichment.json "
          f"(with pigments: {withpig}, with swatch-hex: {withhex})")


if __name__ == "__main__":
    main()
