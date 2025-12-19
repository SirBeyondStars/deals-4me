# parse_flyer_text.py — turns one OCR .txt into a .csv (generic; week/store passed in)

from __future__ import annotations

import re, csv, sys, argparse
import datetime as dt
from pathlib import Path
from typing import Optional, Tuple

PRICE_RE = re.compile(r'(?<!\d)(\d+)\s*for\s*\$?(\d+(?:\.\d{2})?)', re.I)  # 2 for 5
EACH_RE  = re.compile(r'\$?(\d+(?:\.\d{2}))\s*(?:ea|each)?', re.I)          # 3.99 ea
SAVE_RE  = re.compile(r'Save\s*\$?(\d+(?:\.\d{2}))', re.I)
REG_RE   = re.compile(r'Reg(?:ular)?\s*\$?(\d+(?:\.\d{2}))', re.I)
BOGO_RE  = re.compile(r'\bBOGO\b|\bBuy\s*1\s*Get\s*1\b', re.I)
SIZE_RE  = re.compile(r'\b(oz|lb|ct|pk|pack|gal|fl\s?oz)\b', re.I)

# -------------------------
# Date extraction helpers
# -------------------------

def _week_code_to_date(week_code: str) -> dt.date:
    """MMDDYY -> date(20YY, MM, DD)."""
    if len(week_code) != 6 or not week_code.isdigit():
        raise ValueError(f"Invalid week_code: {week_code}")
    m = int(week_code[0:2])
    d = int(week_code[2:4])
    y = 2000 + int(week_code[4:6])
    return dt.date(y, m, d)


def extract_flyer_dates(
    text: str,
    fallback_week: Optional[str] = None,
) -> Tuple[Optional[dt.date], Optional[dt.date]]:
    """
    Best-effort extraction of flyer start/end dates from OCR text.

    Looks for patterns like:
      - 10/24 - 10/30/25
      - 10/24/25 - 10/30/25
      - 10/24/25 - 10/30

    If nothing is found, falls back to:
      - the supplied fallback_week (MMDDYY) as start, start+6 as end, OR
      - today's year as last resort.

    Returns (start_date, end_date) where each element may be None.
    """

    default_year: Optional[int] = None
    if fallback_week:
        try:
            default_year = _week_code_to_date(fallback_week).year
        except Exception:
            default_year = None

    # Collapse text to one line so cross-line ranges still match.
    blob = " ".join(line.strip() for line in text.splitlines() if line.strip())

    # 1) Range: MM/DD[/YY] - MM/DD[/YY]
    range_re = re.compile(
        r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s*[-–]\s*'
        r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?',
        re.I,
    )

    def _make_date(mo: re.Match, idx_m: int, idx_d: int, idx_y: int) -> dt.date:
        month = int(mo.group(idx_m))
        day = int(mo.group(idx_d))
        y_str = mo.group(idx_y)
        if y_str:
            year = int(y_str)
            if year < 100:
                year += 2000
        elif default_year is not None:
            year = default_year
        else:
            year = dt.date.today().year
        return dt.date(year, month, day)

    m = range_re.search(blob)
    if m:
        start_date = _make_date(m, 1, 2, 3)
        end_date = _make_date(m, 4, 5, 6)
        return start_date, end_date

    # 2) Fallback: single MM/DD[/YY] → assume 7-day flyer.
    single_re = re.compile(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', re.I)
    m2 = single_re.search(blob)
    if m2:
        start_date = _make_date(m2, 1, 2, 3)
        end_date = start_date + dt.timedelta(days=6)
        return start_date, end_date

    # 3) Final fallback: derive from week_code if we have it.
    if fallback_week:
        try:
            start_date = _week_code_to_date(fallback_week)
            return start_date, start_date + dt.timedelta(days=6)
        except Exception:
            pass

    return None, None


# -------------------------
# Item parsing
# -------------------------

def guess_line_items(text: str):
    chunks = re.split(r'\n{2,}|•|-{3,}', text)
    return [c.strip() for c in chunks if c.strip()]


def normalize(block: str):
    deal_raw = None
    qty = None
    sale = None
    unit = None
    reg = None
    save_raw = None

    m = PRICE_RE.search(block)
    if m:
        qty = int(m.group(1))
        sale = float(m.group(2))
        unit = round(sale / qty, 2)
        deal_raw = m.group(0)
    else:
        m2 = EACH_RE.search(block)
        if m2:
            qty = 1
            sale = float(m2.group(1))
            unit = sale
            deal_raw = m2.group(0)

    if BOGO_RE.search(block):
        deal_raw = (deal_raw + " + BOGO") if deal_raw else "BOGO"

    m3 = SAVE_RE.search(block)
    if m3:
        save_raw = f"Save ${m3.group(1)}"
    m4 = REG_RE.search(block)
    if m4:
        reg = float(m4.group(1))
        if sale is None and m3:
            try:
                save_amt = float(m3.group(1))
                sale = round(reg - save_amt, 2)
                unit = sale
                deal_raw = (deal_raw + f" | {save_raw}") if deal_raw else save_raw
            except Exception:
                pass

    first = block.splitlines()[0] if '\n' in block else block[:120]
    name = PRICE_RE.sub('', first)
    name = EACH_RE.sub('', name)
    name = BOGO_RE.sub('', name)
    name = re.sub(r'\s{2,}', ' ', name).strip(' -•:|')

    size = ''
    variant = ''
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    if len(lines) >= 2:
        if SIZE_RE.search(lines[1]):
            size = lines[1]
        else:
            variant = lines[1][:80]

    return dict(
        product_name=name or "Unknown",
        variant=variant,
        size=size,
        deal_raw=deal_raw or "",
        qty=qty or "",
        sale_price=f"{sale:.2f}" if sale is not None else "",
        unit_price=f"{unit:.2f}" if unit is not None else "",
        reg_price=f"{reg:.2f}" if reg is not None else "",
        savings_raw=save_raw or "",
    )


def parse_text_block(text: str):
    """
    Optional helper if you want run_weekly_pipeline to use the “rich” parser.
    Returns rows compatible with the headers used in main().
    """
    rows = []
    for block in guess_line_items(text):
        r = normalize(block)
        rows.append([
            r["product_name"],
            r["variant"],
            r["size"],
            r["deal_raw"],
            r["qty"],
            r["sale_price"],
            r["unit_price"],
            r["reg_price"],
            r["savings_raw"],
        ])
    return rows


def main(in_txt: Path, week_start: str, week_end: str, store_name: str, store_id: str):
    text = in_txt.read_text(encoding="utf-8", errors="ignore")

    # If CLI didn't give us dates, try to infer them from the text.
    if not week_start or not week_end:
        inferred_start, inferred_end = extract_flyer_dates(text)
        if inferred_start and not week_start:
            week_start = inferred_start.isoformat()
        if inferred_end and not week_end:
            week_end = inferred_end.isoformat()

    rows = [normalize(b) for b in guess_line_items(text)]

    # derive the current week's /parsed/ folder from the input path:
    # ...\<store>\<week>\(ocr_text|manual_text)\file.txt  ->  ...\<store>\<week>\parsed\file.csv
    week_dir = in_txt.parent.parent
    out_csv = week_dir / "parsed" / (in_txt.stem + ".csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "chain_name",
                "store_id",
                "store_city",
                "store_state",
                "flyer_week_start",
                "flyer_week_end",
                "product_name",
                "variant",
                "size",
                "deal_raw",
                "qty",
                "sale_price",
                "unit_price",
                "reg_price",
                "savings_raw",
                "category",
                "source_type",
                "source_url",
                "notes",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    store_name,
                    store_id,
                    "",
                    "",
                    week_start,
                    week_end,
                    r["product_name"],
                    r["variant"],
                    r["size"],
                    r["deal_raw"],
                    r["qty"],
                    r["sale_price"],
                    r["unit_price"],
                    r["reg_price"],
                    r["savings_raw"],
                    "",
                    "manual-ocr",
                    "",
                    "",
                ]
            )
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("in_txt")
    ap.add_argument("--week-start", default="")
    ap.add_argument("--week-end", default="")
    ap.add_argument("--store", default="Hannaford")
    ap.add_argument("--store-id", default="1005")
    args = ap.parse_args()
    main(Path(args.in_txt), args.week_start, args.week_end, args.store, args.store_id)
