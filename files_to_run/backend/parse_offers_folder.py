from __future__ import annotations

import argparse
import csv
import re
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Tuple

from price_select import ParsedDeal  # using your ParsedDeal dataclass


# Matches either "1.97" or "97¢"
PRICE_TOKEN_RE = re.compile(
    r"(?<!\d)(\d{1,3}\.\d{2})(?!\d)|\b(\d{1,3})\s*¢\b",
    re.IGNORECASE,
)


def _price_from_line(line: str) -> Optional[float]:
    """
    Extract a price from a line.
    Supports:
      - 1.97
      - 97¢
    Returns float dollars (e.g., 0.97 for 97¢)
    """
    m = PRICE_TOKEN_RE.search(line)
    if not m:
        return None

    if m.group(1):  # decimal dollars
        try:
            return float(m.group(1))
        except Exception:
            return None

    if m.group(2):  # cents
        try:
            cents = int(m.group(2))
            return round(cents / 100.0, 2)
        except Exception:
            return None

    return None


def split_offer_into_candidates(lines: List[str]) -> List[Tuple[str, float]]:
    """
    Given OCR text lines from a single offer box, return [(name_guess, price), ...]
    Heuristic:
      - find each line with a price
      - use the closest non-empty text above it as the item name
    """
    out: List[Tuple[str, float]] = []

    for i, line in enumerate(lines):
        price = _price_from_line(line)
        if price is None:
            continue

        # look upward for a name-ish line
        name = None
        for j in range(i - 1, max(-1, i - 6), -1):  # look up to 5 lines above
            t = lines[j].strip()
            if not t or len(t) < 3:
                continue
            if any(ch.isalpha() for ch in t):
                name = t
                break

        if name:
            out.append((name, price))

    # de-dupe
    seen = set()
    deduped: List[Tuple[str, float]] = []
    for name, price in out:
        key = (name.lower(), round(price, 2))
        if key in seen:
            continue
        seen.add(key)
        deduped.append((name, price))

    return deduped


def iter_offer_txt_files(offers_dir: Path) -> List[Path]:
    return sorted(offers_dir.glob("offer_*.txt"))


def parse_one_file(txt_path: Path) -> Tuple[List[ParsedDeal], str]:
    """
    Returns (list_of_deals, status).
    If we can't parse anything, list is empty and status explains why.
    """
    try:
        text = txt_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [], f"read_error: {e}"

    lines = text.splitlines()
    candidates = split_offer_into_candidates(lines)

    if not candidates:
        return [], "no_candidates"

    deals: List[ParsedDeal] = []
    for name, price in candidates:
        deals.append(
            ParsedDeal(
                item_name=name,
                sale_price=price,
                unit="",              # we’ll improve later
                is_multibuy=False,    # we’ll improve later
                multibuy_qty=None,
                multibuy_total=None,
                raw_token=f"{price:.2f}",
                reason="candidate_split",
            )
        )

    return deals, "ok"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offers-dir", required=True, help="Path to a page_XX_offers folder containing offer_####.txt")
    ap.add_argument("--brand", required=True, help="brand name, e.g. shaws")
    ap.add_argument("--week", required=True, help="week code, e.g. week51")
    ap.add_argument("--out", default="", help="Output CSV path (default: offers_dir/parsed_deals.csv)")
    args = ap.parse_args()

    offers_dir = Path(args.offers_dir)
    if not offers_dir.exists() or not offers_dir.is_dir():
        raise SystemExit(f"offers-dir not found: {offers_dir}")

    out_csv = Path(args.out) if args.out else (offers_dir / "parsed_deals.csv")

    rows: List[dict] = []
    ok = 0
    bad = 0

    for txt_path in iter_offer_txt_files(offers_dir):
        deals, status = parse_one_file(txt_path)

        if deals:
            ok += len(deals)
            for deal in deals:
                d = asdict(deal)
                d.update(
                    {
                        "status": status,
                        "brand": args.brand,
                        "week_code": args.week,
                        "offer_txt": str(txt_path.name),
                        "offer_png": txt_path.name.replace(".txt", ".png"),
                    }
                )
                rows.append(d)
        else:
            bad += 1
            rows.append(
                {
                    "status": status,
                    "brand": args.brand,
                    "week_code": args.week,
                    "offer_txt": str(txt_path.name),
                    "offer_png": txt_path.name.replace(".txt", ".png"),
                    "item_name": "",
                    "sale_price": "",
                    "unit": "",
                    "is_multibuy": "",
                    "multibuy_qty": "",
                    "multibuy_total": "",
                    "raw_token": "",
                    "reason": "",
                }
            )

    # write CSV
    fieldnames = [
        "status", "brand", "week_code", "offer_txt", "offer_png",
        "item_name", "sale_price", "unit", "is_multibuy", "multibuy_qty", "multibuy_total",
        "raw_token", "reason"
    ]

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            out_row = {k: r.get(k, "") for k in fieldnames}
            w.writerow(out_row)

    print("[done]")
    print(f"  offers_dir: {offers_dir}")
    print(f"  output:     {out_csv}")
    print(f"  parsed_ok:  {ok}")
    print(f"  parsed_bad: {bad}")


if __name__ == "__main__":
    main()
