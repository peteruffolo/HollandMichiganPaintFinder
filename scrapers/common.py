"""
Shared helpers for matching a distributor's product name to a catalog entry.

The catalog (catalog.json) holds the canonical truth: brand, line, color name,
aliases, pigment codes. Each distributor scraper only has to figure out which
catalog product a listing corresponds to, then record price/size/stock/url.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# words that carry no identifying signal for color matching
NOISE = {
    "oil", "oils", "color", "colour", "colours", "colors", "artist", "artists",
    "professional", "series", "tube", "paint", "hue", "ml", "oz",
}

# how to recognize each product LINE from a distributor's free-text name.
# key = canonical line, value = lowercase substrings that imply that line.
LINE_HINTS = {
    "1980": ["1980"],
    "Winton": ["winton"],
    "Studio": ["blick studio", "studio oil"],
    "Artist's Oil": ["gamblin artist", "artist's oil", "artists oil"],
    "Artists' Oil": ["winsor", "artists' oil"],
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def tokens(s: str):
    return [t for t in norm(s).split(" ") if t]


def core_tokens(s: str):
    return [t for t in tokens(s) if t not in NOISE and not re.fullmatch(r"p[a-z]{1,3}\d{1,3}", t)]


def extract_size(name: str):
    """Return (size_number, unit) e.g. (37, 'ml') from a product name, or (None, None)."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ml|oz)\b", name.lower())
    if m:
        return float(m.group(1)), m.group(2)
    return None, None


def _lev1(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    i = j = edits = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1; j += 1; continue
        edits += 1
        if edits > 1:
            return False
        if len(a) > len(b): i += 1
        elif len(a) < len(b): j += 1
        else: i += 1; j += 1
    if i < len(a) or j < len(b):
        edits += 1
    return edits <= 1


def _token_in(tok: str, name_set) -> bool:
    if tok in name_set:
        return True
    if len(tok) < 4:
        return False
    return any(len(x) >= 4 and _lev1(tok, x) for x in name_set)


def guess_line(raw_name: str):
    low = raw_name.lower()
    for line, hints in LINE_HINTS.items():
        if any(h in low for h in hints):
            return line
    return None


def match_product(raw_name: str, catalog, restrict_line=None, restrict_brand=None):
    """
    Find the best catalog entry for a distributor's product string.
    Returns (catalog_entry, score) or (None, 0).
    """
    line = restrict_line or guess_line(raw_name)
    name_set = set(core_tokens(raw_name))
    best, best_score = None, 0.0
    for c in catalog:
        if restrict_brand and c["brand"].lower() != restrict_brand.lower():
            continue
        if line and c["line"].lower() != line.lower():
            continue
        # match the candidate's color name + aliases against the raw listing tokens
        candidates = [c["name"]] + c.get("aliases", [])
        local_best = 0.0
        for cand in candidates:
            ct = core_tokens(cand)
            if not ct:
                continue
            found = sum(1 for t in ct if _token_in(t, name_set))
            cov = found / len(ct)
            # require the candidate's words to be essentially present
            need = len(ct) if len(ct) <= 2 else len(ct) - 1
            if found >= need:
                local_best = max(local_best, cov)
        if local_best > best_score:
            best, best_score = c, local_best
    return best, best_score


def load_catalog():
    return json.loads((ROOT / "catalog.json").read_text())
