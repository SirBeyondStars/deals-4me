from __future__ import annotations

import argparse
import re
from pathlib import Path
from collections import Counter


DIGIT_RE = re.compile(r"\d")
S_PRICE_RE = re.compile(r"\bS\s*\d{3,4}\b", re.IGNORECASE)          # S199
DOLLAR_MASH_RE = re.compile(r"\$\s*\d{3,4}\b")                      # $649
FOR_DOLLAR_RE = re.compile(r"\b\d+\s*(?:for|/)\s*\$\b", re.IGNORECASE)  # 2for$
PCT_OFF_RE = re.compile(r"%\s*off", re.IGNORECASE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug-root", required=True, help="...\\exports\\_debug_offers")
    args = ap.parse_args()

    root = Path(args.debug_root).resolve()
    if not root.exists():
        raise SystemExit(f"Not found: {root}")

    offer_files = sorted(root.rglob("page_*_offers/offer_*"))
    offer_files = [p for p in offer_files if p.is_file() and not p.name.lower().endswith((".meta", ".json"))]

    c = Counter()
    total = 0

    for p in offer_files:
        txt = p.read_text(encoding="utf-8", errors="replace").strip()
        total += 1

        if not txt:
            c["blank_file"] += 1
            continue

        has_digit = bool(DIGIT_RE.search(txt))
        has_s_price = bool(S_PRICE_RE.search(txt))
        has_dollar_mash = bool(DOLLAR_MASH_RE.search(txt))
        has_for_dollar = bool(FOR_DOLLAR_RE.search(txt))
        has_pct_off = bool(PCT_OFF_RE.search(txt))

        if has_digit:
            c["has_any_digits"] += 1
        else:
            c["no_digits_at_all"] += 1

        if has_s_price:
            c["has_S199_style"] += 1
        if has_dollar_mash:
            c["has_$649_style"] += 1
        if has_for_dollar:
            c["has_2for$_missing_total"] += 1
        if has_pct_off:
            c["has_%off"] += 1

    print(f"Offer files scanned: {total}")
    for k, v in c.most_common():
        print(f"{k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
