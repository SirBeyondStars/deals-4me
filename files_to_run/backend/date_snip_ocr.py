"""
date_snip_ocr.py

Read flyer date ranges from a small "date.png" snip in each store/week folder.

Expected structure:

  flyers/
    aldi/
      week52/
        date.png
        raw_png/...
    whole_foods/
      week52/
        date.png
        raw_png/...

For each store that has <week>/date.png, we run OCR on that image,
look for a date range, and output:

  store, week_code, start_date, end_date, status

We also write a CSV in the current folder:

  date_snip_results_<week_code>.csv
"""

import argparse
import csv
import re
from pathlib import Path
from datetime import datetime

from PIL import Image
import pytesseract
from ocr_config import TESSERACT_EXE

pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_EXE)

# Numeric MM/DD pattern, e.g. 12/10, 1/5, 09/30
DATE_PATTERN_NUMERIC = re.compile(r"(\d{1,2}/\d{1,2})")

# Month names (both full + abbreviated)
MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Matches BOTH:
#   Dec 10th
#   December 10, 2025
#   September 4
MONTH_PATTERN = re.compile(
    r"\b("
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t)?(?:ember)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    r")\b"
    r"\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,\s*(\d{4}))?",
    re.IGNORECASE,
)


def discover_store_dirs(flyers_root: Path):
    """Return list of store dirs under flyers_root (skip logs/temp)."""
    stores = []
    for child in flyers_root.iterdir():
        if not child.is_dir():
            continue
        name = child.name.lower()
        if name.startswith("_") or name in {"logs", "temp", "tmp"}:
            continue
        stores.append(child)
    return sorted(stores, key=lambda p: p.name.lower())


def ocr_date_from_snip(snip_path: Path) -> str:
    img = Image.open(snip_path)

    # Preprocess for OCR
    img = img.convert("L")          # grayscale
    img = img.point(lambda x: 0 if x < 140 else 255, "1")  # high-contrast threshold

    text = pytesseract.image_to_string(img, config="--psm 6")
    return text.strip()



def parse_dates_from_text(text: str, default_year: int):
    """
    Try to extract a start/end date from OCR text.

    Supports:
      - 'Valid 12/10 - 12/16'
      - 'Valid December 4, 2025 - December 10, 2025'
      - 'Weekly Ad\\nDec 10th - Dec 16th'
      - 'Dec 10 - Dec 16'
      - 'Dec 10th - Dec 16th'

    Returns (start_iso, end_iso) as 'YYYY-MM-DD' strings,
    or (None, None) if we can't find two dates.
    """

    def month_to_num(month_word: str) -> int:
        key = month_word.strip().lower().rstrip(".")
        # normalize "Sept" to "sep"
        if key.startswith("sept"):
            key = "sep"
        return MONTH_MAP.get(key, 0)

    # 1) Try month-name style first (covers Dec + December)
    matches = list(MONTH_PATTERN.finditer(text))
    if len(matches) >= 2:
        def match_to_iso(m):
            month_word = m.group(1)
            day_str = m.group(2)
            year_str = m.group(3)

            year = int(year_str) if year_str else default_year
            month = month_to_num(month_word)
            day = int(day_str)

            if not month:
                raise ValueError(f"Unknown month name: {month_word!r}")

            dt = datetime(year=year, month=month, day=day)
            return dt.strftime("%Y-%m-%d")

        try:
            start_iso = match_to_iso(matches[0])
            end_iso = match_to_iso(matches[1])
            return start_iso, end_iso
        except Exception:
            # fall through to numeric if something odd happens
            pass

    # 2) Fallback: numeric MM/DD style
    num_matches = DATE_PATTERN_NUMERIC.findall(text)
    if len(num_matches) >= 2:
        def mmdd_to_iso(mmdd: str) -> str:
            month, day = mmdd.split("/")
            dt = datetime(year=default_year, month=int(month), day=int(day))
            return dt.strftime("%Y-%m-%d")

        start_iso = mmdd_to_iso(num_matches[0])
        end_iso = mmdd_to_iso(num_matches[1])
        return start_iso, end_iso

    return None, None


def main():
    parser = argparse.ArgumentParser(
        description="Read flyer date ranges from date.png snips in each store/week folder."
    )
    parser.add_argument(
        "--flyers-root",
        required=True,
        type=Path,
        help="Root folder where store subfolders live "
             "(e.g. C:\\Users\\...\\files_to_run\\flyers)",
    )
    parser.add_argument(
        "--week-code",
        required=True,
        help="Week code, e.g. week52 or week01_2026",
    )
    parser.add_argument(
        "--year",
        required=True,
        type=int,
        help="Year to assume for dates missing a year (e.g. 2025).",
    )

    args = parser.parse_args()
    flyers_root: Path = args.flyers_root
    week_code: str = args.week_code
    default_year: int = args.year

    if not flyers_root.exists():
        raise SystemExit(f"[FATAL] Flyers root does not exist: {flyers_root}")

    print(f"[INFO] Flyers root: {flyers_root}")
    print(f"[INFO] Week code:   {week_code}")
    print(f"[INFO] Year:        {default_year}")
    print()

    stores = discover_store_dirs(flyers_root)
    if not stores:
        print("[WARN] No store folders found.")
        return

    csv_name = f"date_snip_results_{week_code}.csv"
    csv_path = Path.cwd() / csv_name
    csv_rows = []

    print("{:<20} {:<10} {:<12} {:<12} {}".format(
        "Store", "Week", "StartDate", "EndDate", "Status"
    ))
    print("-" * 70)

    for store_dir in stores:
        store = store_dir.name
        week_dir = store_dir / week_code

        if not week_dir.exists():
            print(f"{store:<20} {week_code:<10} {'-':<12} {'-':<12} no such week folder")
            csv_rows.append([store, week_code, "", "", "NO_WEEK_FOLDER"])
            continue

        snip_path = week_dir / "date.png"
        if not snip_path.exists():
            print(f"{store:<20} {week_code:<10} {'-':<12} {'-':<12} no date.png")
            csv_rows.append([store, week_code, "", "", "NO_DATE_SNIP"])
            continue

        try:
            text = ocr_date_from_snip(snip_path)
        except Exception as exc:
            status = f"ERROR: {exc!r}"
            print(f"{store:<20} {week_code:<10} {'-':<12} {'-':<12} {status}")
            csv_rows.append([store, week_code, "", "", status])
            continue

        start_iso, end_iso = parse_dates_from_text(text, default_year)
        if not start_iso or not end_iso:
            status = f"NO_DATES_IN_OCR ({text!r})"
            print(f"{store:<20} {week_code:<10} {'-':<12} {'-':<12} {status}")
            csv_rows.append([store, week_code, "", "", status])
            continue

        print(f"{store:<20} {week_code:<10} {start_iso:<12} {end_iso:<12} OK")
        csv_rows.append([store, week_code, start_iso, end_iso, "OK"])

    if csv_rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["store", "week_code", "start_date", "end_date", "status"])
            writer.writerows(csv_rows)
        print()
        print(f"[INFO] Wrote CSV: {csv_path}")
    else:
        print()
        print("[INFO] No rows to write; nothing processed.")


if __name__ == "__main__":
    main()
