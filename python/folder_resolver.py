import logging
import difflib
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

FOLDER_ALIASES = {
    "hannaford": "hannaford",
    "shaws": "shaws_and_star_market",
    "pricechopper": "price_chopper_market_32",
    "rochebros": "roche_bros",
    "stopandshop_mari": "stop_and_shop_mari",
    "stopandshop_ct":   "stop_and_shop_ct",
    "marketbasket": "market_basket",
    "bigy": "big_y",
}

def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

def resolve_store_dir(ROOT, store_key):
    flyers_root = ROOT / "flyers"

    alias = FOLDER_ALIASES.get(store_key)
    if alias:
        p = flyers_root / alias
        if p.exists():
            if alias != store_key:
                print(f"[alias] {store_key} -> {alias}")
            return p
        else:
            print(f"[alias-miss] {store_key} -> {alias} (not found)")

    p = flyers_root / store_key
    if p.exists():
        return p

    desired = _slug(store_key)
    folders = [d for d in flyers_root.iterdir() if d.is_dir()] if flyers_root.exists() else []
    if not folders:
        print(f"[resolve] no folders under {flyers_root}, using {flyers_root/store_key}")
        return flyers_root / store_key

    best = max(folders, key=lambda d: difflib.SequenceMatcher(None, desired, _slug(d.name)).ratio())
    ratio = difflib.SequenceMatcher(None, desired, _slug(best.name)).ratio()

    if ratio >= 0.6:
        print(f"[warn] using closest folder '{best.name}' for '{store_key}' (match {ratio:.2f})")
        return best

    print(f"[warn] no good match for '{store_key}', using {flyers_root/store_key}")
    return flyers_root / store_key
