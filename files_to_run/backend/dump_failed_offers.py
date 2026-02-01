from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parsed-csv", required=True, help="Path to parsed_week.csv")
    ap.add_argument("--out", default="", help="Output CSV path (default next to parsed)")
    ap.add_argument("--only", default="", help="Filter reason (e.g., no_price_found)")
    ap.add_argument("--max", type=int, default=5000, help="Max rows to write")
    args = ap.parse_args()

    parsed_csv = Path(args.parsed_csv).resolve()
    if not parsed_csv.exists():
        raise SystemExit(f"Not found: {parsed_csv}")

    out_csv = Path(args.out) if args.out else parsed_csv.parent / "failed_offers_review.csv"

    rows = []
    with parsed_csv.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            reason = (row.get("reason") or "").strip()
            if reason == "ok" or reason == "":
                continue
            if args.only and reason != args.only:
                continue

            blob = (row.get("blob_text") or row.get("text") or "").replace("\n", " ").strip()
            blob = (blob[:160] + "…") if len(blob) > 160 else blob

            rows.append({
                "page_dir": row.get("page_dir", ""),
                "offer_file": row.get("offer_file", ""),
                "reason": reason,
                "sale_price": row.get("sale_price", ""),
                "unit": row.get("unit", ""),
                "snippet": blob,
            })

            if len(rows) >= args.max:
                break

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["page_dir", "offer_file", "reason", "sale_price", "unit", "snippet"])
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote: {out_csv}  (rows={len(rows)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
