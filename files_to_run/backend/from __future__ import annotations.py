from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple

# ---------- Cleaning rules ----------

JUNK_PHRASES = [
    "price with membership",
    "add to cart",
    "check store",
    "browse in-store",
    "weekly sales",
    "top",
    "shopping",
    "opens in a new tab",
]

WHITESPACE_RE = re.compile(r"\s+")
MONEY_RE = re.compile(r"\$?\s*(\d+(?:\.\d{2})?)")
FOR_DEAL_RE = re.compile(r"(\d+)\s*for\s*\$?\s*(\d+(?:\.\d{2})?)", re.IGNORECASE)
RANGE_RE = re.compile(r"\$?\s*(\d+(?:\.\d{2})?)\s*to\s*\$?\s*(\d+(?:\.\d{2})?)", re.IGNORECASE)
LB_RE = re.compile(r"\$?\s*(\d+(?:\.\d{2})?)\s*/\s*lb", re.IGNORECASE)

def norm_text(s: str) -> str:
    s = (s or "").replace("\u00a0", " ").strip()
    s = WHITESPACE_RE.sub(" ", s)
    return s.strip()

def strip_junk(s: str) -> str:
    t = norm_text(s)
    low = t.lower()
    for p in JUNK_PHRASES:
        if p in low:
            # remove the phrase but keep other words
            low = low.replace(p, "")
            t = low
    return norm_text(t)

def normalize_sale_price(s: str) -> str:
    """
    Return a normalized display value for sale_price:
    - "$3.99" -> "3.99"
    - "2 for $3" -> "2 for 3.00"
    - "$4.99 to $13.79" -> "4.99 to 13.79"
    - "$1.99/lb" -> "1.99/lb"
    Otherwise return trimmed original.
    """
    t = norm_text(s)
    if not t:
        return ""

    m = LB_RE.search(t)
    if m:
        return f"{float(m.group(1)):.2f}/lb"

    m = FOR_DEAL_RE.search(t)
    if m:
        n = int(m.group(1))
        amt = float(m.group(2))
        return f"{n} for {amt:.2f}"

    m = RANGE_RE.search(t)
    if m:
        a = float(m.group(1))
        b = float(m.group(2))
        return f"{a:.2f} to {b:.2f}"

    # single $ amount anywhere
    m = MONEY_RE.search(t)
    if m and ("$" in t or t.strip().replace(".", "", 1).isdigit()):
        return f"{float(m.group(1)):.2f}"

    return t

def looks_bad_item_name(name: str) -> bool:
    if not name:
        return True
    low = name.lower()
    if len(name) < 3:
        return True
    # obvious non-items
    bad = [
        "privacy notice", "conditions of use", "site map", "corporate policies",
        "connect with us", "visit customer care", "copyright"
    ]
    return any(b in low for b in bad)

def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        rows = [dict((k, (v or "")) for k, v in row.items()) for row in r]
        return (r.fieldnames or []), rows

def write_csv(path: Path, headers: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for row in rows:
            w.writerow({h: row.get(h, "") for h in headers})

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Merged offers CSV")
    ap.add_argument("--output", required=True, help="Cleaned output CSV")
    ap.add_argument("--mode", default="supabase_flyer_items", help="Output mode")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    headers, rows = read_csv(in_path)

    # Supabase flyer_items table (your screenshot) does NOT have store/region.
    # Keep only columns that are most likely in flyer_items.
    # If later you add columns, we can expand this list.
    if args.mode == "supabase_flyer_items":
        keep = [
            "item_name",
            "week_code",
            "sale_price",
            "percent_off_prime",
            "percent_off_nonprime",
            "promo_start",
            "promo_end",
            "manual_review_reason",
            "source_file",
        ]
        # keep only ones that exist in this CSV
        keep = [h for h in keep if h in headers]
        # ensure minimum viable
        if "item_name" not in keep or "week_code" not in keep:
            raise SystemExit("Input CSV missing required columns (need at least item_name and week_code).")
        out_headers = keep
    else:
        out_headers = headers[:]  # no filtering

    cleaned: List[Dict[str, str]] = []
    seen = set()

    for row in rows:
        item = strip_junk(row.get("item_name", ""))
        if looks_bad_item_name(item):
            continue

        sale = normalize_sale_price(row.get("sale_price", ""))

        # normalize other fields we keep
        row["item_name"] = item
        if "sale_price" in row:
            row["sale_price"] = sale

        # de-dupe on key fields
        key = (
            row.get("week_code", "").strip(),
            item.lower(),
            (sale or "").strip(),
            (row.get("percent_off_prime", "") or "").strip(),
            (row.get("percent_off_nonprime", "") or "").strip(),
            (row.get("promo_start", "") or "").strip(),
            (row.get("promo_end", "") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)

        cleaned.append(row)

    # project to output headers
    final_rows = [{h: norm_text(r.get(h, "")) for h in out_headers} for r in cleaned]
    write_csv(out_path, out_headers, final_rows)

    print(f"[post_clean] Input rows : {len(rows)}")
    print(f"[post_clean] Output rows: {len(final_rows)}")
    print(f"[post_clean] Wrote -> {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
