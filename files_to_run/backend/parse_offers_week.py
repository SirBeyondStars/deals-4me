from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from price_select import parse_offer_blob_with_reason, ParsedDeal


def iter_page_offer_dirs(debug_root: Path) -> List[Path]:
    # folders like page_01_offers, page_06_offers, etc.
    dirs = [p for p in debug_root.glob("page_*_offers") if p.is_dir()]
    return sorted(dirs, key=lambda p: p.name)


def iter_offer_txt_files(page_dir: Path) -> List[Path]:
    return sorted(page_dir.glob("offer_*.txt"))


def parse_one_txt(txt_path: Path) -> Tuple[Optional[ParsedDeal], str]:
    try:
        text = txt_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return None, f"read_error: {e}"

    deal, reason = parse_offer_blob_with_reason(text)
    return deal, reason

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug-root", required=True, help="Path to _debug_offers/<brand> folder that contains page_*_offers")
    ap.add_argument("--brand", required=True, help="brand name, e.g. shaws")
    ap.add_argument("--week", required=True, help="week code, e.g. week51")
    ap.add_argument("--out", default="", help="Output CSV path (default: debug_root/parsed_week.csv)")
    args = ap.parse_args()

    debug_root = Path(args.debug_root)
    if not debug_root.exists() or not debug_root.is_dir():
        raise SystemExit(f"debug-root not found: {debug_root}")

    out_csv = Path(args.out) if args.out else (debug_root / "parsed_week.csv")

    fieldnames = [
    "status", "fail_reason", "reject_reason",
    "brand", "week_code", "page_dir",
    "offer_txt", "offer_png",
    "item_name", "sale_price", "unit",
    "is_multibuy", "multibuy_qty", "multibuy_total",
    "percent_off", "percent_text",
    "limit_qty", "limit_scope", "limit_text",
]


    rows: List[Dict] = []
    ok = 0
    bad = 0
    pages = 0
    offers_total = 0

    for page_dir in iter_page_offer_dirs(debug_root):
        pages += 1
        for txt_path in iter_offer_txt_files(page_dir):
            offers_total += 1
            deal, status = parse_one_txt(txt_path)

            if deal:
                ok += 1
                d = asdict(deal)
                d.update({
                    "status": status,
                    "brand": args.brand,
                    "week_code": args.week,
                    "page_dir": page_dir.name,
                    "offer_txt": txt_path.name,
                    "offer_png": txt_path.name.replace(".txt", ".png"),
                })
                rows.append({k: d.get(k, "") for k in fieldnames})
            else:
                bad += 1
                rows.append({
                    "status": status,
                    "fail_reason": status,
                    "reject_reason": "",
                    "brand": args.brand,
                    "week_code": args.week,
                    "page_dir": page_dir.name,
                    "offer_txt": txt_path.name,
                    "offer_png": txt_path.name.replace(".txt", ".png"),
                    "item_name": "",
                    "sale_price": "",
                    "unit": "",
                    "is_multibuy": "",
                    "multibuy_qty": "",
                    "multibuy_total": "",
                    "limit_qty": "",
                    "limit_scope": "",
                    "limit_text": "",
                    "percent_off": "",
                    "percent_text": "",
                })

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

            print("[done]")
            print(f"  brand:        {args.brand}")
            print(f"  week_code:     {args.week}")
            print(f"  debug_root:   {debug_root}")
            print(f"  output:       {out_csv}")
            print(f"  pages:        {pages}")
            print(f"  offers_total: {offers_total}")
            print(f"  parsed_ok:    {ok}")
            print(f"  parsed_bad:   {bad}")


if __name__ == "__main__":
    main()
