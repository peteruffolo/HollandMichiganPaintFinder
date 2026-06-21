"""
build_data.py  ->  data.json

Joins price rows from every prices/*.json with the catalog and writes the flat
list the web page reads. Two kinds of price rows are supported:

  * self-describing (from scrapers): has brand/line/grade/name. The catalog is
    used only to ENRICH it with pigment codes + swatch hex when a match exists.
  * catalog-referencing (hand-entered): has product_id pointing at catalog.json.

So the catalog no longer needs an entry per color -- scrapers supply the full
color range, and the catalog adds pigment intelligence where it matters.

  python build_data.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scrapers"))
from common import match_product

ROOT = Path(__file__).resolve().parent
catalog = json.loads((ROOT / "catalog.json").read_text())
cat_by_id = {c["id"]: c for c in catalog}


def enrich(row):
    """Resolve a price row to full display fields, pulling pigments/hex from catalog."""
    if row.get("product_id"):
        c = cat_by_id.get(row["product_id"])
        if not c:
            print(f"  WARNING: unknown product_id {row.get('product_id')!r}")
            return None
        base = dict(brand=c["brand"], line=c["line"], grade=c["grade"], name=c["name"],
                    pigments=c["pigments"], hex=c.get("hex", "#888888"))
    else:
        pigments, hexv = [], "#888888"
        entry, score = match_product(row["name"], catalog,
                                     restrict_line=row.get("line"),
                                     restrict_brand=row.get("brand"))
        if entry and score >= 0.6:
            pigments, hexv = entry["pigments"], entry.get("hex", "#888888")
        base = dict(brand=row["brand"], line=row["line"], grade=row.get("grade", "student"),
                    name=row["name"], pigments=pigments, hex=hexv)
    base.update(size=row.get("size"), unit=row.get("unit", "ml"), price=row.get("price"),
                sizeLabel=row.get("sizeLabel"),
                dist=row["dist"], url=row.get("url", ""), inStock=row.get("inStock", True),
                manual=row.get("manual", False), verified=row.get("verified"))
    return base


rows = []
for pf in sorted((ROOT / "prices").glob("*.json")):
    for r in json.loads(pf.read_text()):
        if r.get("price") is None:
            continue
        out = enrich(r)
        if out:
            rows.append(out)

(ROOT / "data.json").write_text(json.dumps(rows, indent=2))
enriched = sum(1 for r in rows if r["pigments"])
print(f"build_data: {len(rows)} rows -> data.json ({enriched} enriched with pigments)")
