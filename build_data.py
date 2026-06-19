"""
build_data.py  ->  data.json

Joins the canonical catalog with every prices/*.json file into the single flat
list the web page renders. Pigments/hex/grade come from the catalog; price/stock
come from each distributor file. Run after the scrapers, or any time you edit a
manual price.

  python build_data.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
catalog = {c["id"]: c for c in json.loads((ROOT / "catalog.json").read_text())}

rows = []
for pf in sorted((ROOT / "prices").glob("*.json")):
    data = json.loads(pf.read_text())
    for r in data:
        c = catalog.get(r.get("product_id"))
        if not c:
            print(f"  WARNING: {pf.name} references unknown product_id {r.get('product_id')!r}")
            continue
        if r.get("price") is None:
            continue
        rows.append({
            "brand": c["brand"], "line": c["line"], "grade": c["grade"],
            "name": c["name"], "pigments": c["pigments"], "hex": c.get("hex", "#888888"),
            "size": r.get("size"), "unit": r.get("unit", "ml"),
            "price": r["price"], "dist": r["dist"], "url": r.get("url", ""),
            "inStock": r.get("inStock", True),
            "manual": r.get("manual", False), "verified": r.get("verified"),
        })

(ROOT / "data.json").write_text(json.dumps(rows, indent=2))
print(f"build_data: wrote {len(rows)} priced rows -> data.json")
