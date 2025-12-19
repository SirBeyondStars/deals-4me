# date_ocr_utils.py
#
# Utilities for extracting start/end dates from OCR text,
# and logging flyers that fail date detection.

from __future__ import annotations

import re
import csv
from pathlib import Path
from datetime import date, datetime
from typing import Optional, Tuple

# Month name -> number
MONTHS = {
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

ORDINAL_SUFFIX_RE = re.compile(r"(st|nd|rd|th)", re.IGNORECASE)


def _normalize_text(text: str) -> str:
    """Normalize dashes + whitespace so regex is easier."""
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("\u00a0", " ")  # non-breaking space
    text = re.sub(r"\s+", " ", text)
    return text


def _safe_date(y: int, m: int, d: int) -> Optional[date]:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _year_or_default(year_str: Optional[str], default_year: Optional[int]) -> int:
    """Pick year from string or fall back to a default or current year."""
    if year_str:
        y = int(year_str)
        if y < 100:  # e.g. "24" -> 2024
            y += 2000
        return y
    if default_year is not None:
        return default_year
    return date.today().year


def extract_date_range(ocr_text: str, default_year: Optional[int] = None) -> Tuple[Optional[date], Optional[date]]:
    """
    Try to extract a (start_date, end_date) from OCR text.

    Handles patterns like:
      - "Dec 3rd - Dec 9th"
      - "Dec 3rd - 9th, 2025"
      - "December 3-9"
      - "12/03/2025 - 12/09/2025"
      - "12/03 - 12/09/25"

    Returns (None, None) if nothing reasonable is found.
    """
    if not ocr_text:
        return None, None

    text = _normalize_text(ocr_text)

    # --- 1) Month name + day range, optional year at end ---
    # e.g. "Dec 3rd - 9th, 2025" or "December 3 - 9"
    month_range_pattern = re.compile(
        r"\b("
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?"
        r")\s+(\d{1,2}(?:st|nd|rd|th)?)\s*[-]\s*(\d{1,2}(?:st|nd|rd|th)?)"
        r"(?:,\s*(\d{2,4}))?",
        re.IGNORECASE,
    )

    m = month_range_pattern.search(text)
    if m:
        month_name, d1_raw, d2_raw, year_raw = m.groups()
        month = MONTHS[month_name.lower()]
        d1 = int(ORDINAL_SUFFIX_RE.sub("", d1_raw))
        d2 = int(ORDINAL_SUFFIX_RE.sub("", d2_raw))
        year = _year_or_default(year_raw, default_year)

        start = _safe_date(year, month, d1)
        end = _safe_date(year, month, d2)
        if start and end:
            return start, end

    # --- 2) Two explicit month+day dates ---
    # e.g. "Dec 3rd - Dec 9th, 2025" or "Dec 3, 2025 to Dec 9, 2025"
    month_day_pattern = re.compile(
        r"\b("
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?"
        r")\s+(\d{1,2}(?:st|nd|rd|th)?)(?:,?\s*(\d{2,4}))?",
        re.IGNORECASE,
    )

    matches = list(month_day_pattern.finditer(text))
    if len(matches) >= 2:
        m1, m2 = matches[0], matches[1]
        month1, d1_raw, y1_raw = m1.groups()
        month2, d2_raw, y2_raw = m2.groups()
        day1 = int(ORDINAL_SUFFIX_RE.sub("", d1_raw))
        day2 = int(ORDINAL_SUFFIX_RE.sub("", d2_raw))
        month1_num = MONTHS[month1.lower()]
        month2_num = MONTHS[month2.lower()]

        year1 = _year_or_default(y1_raw or y2_raw, default_year)
        year2 = _year_or_default(y2_raw or y1_raw, default_year)

        start = _safe_date(year1, month1_num, day1)
        end = _safe_date(year2, month2_num, day2)
        if start and end:
            return start, end

    # --- 3) Numeric date ranges: "12/03/24 - 12/09/24" etc. ---
    numeric_range_pattern = re.compile(
        r"\b(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?"
        r"\s*(?:-|to)\s*"
        r"(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?",
        re.IGNORECASE,
    )

    m = numeric_range_pattern.search(text)
    if m:
        m1, d1, y1_raw, m2, d2, y2_raw = m.groups()
        month1 = int(m1)
        day1 = int(d1)
        month2 = int(m2)
        day2 = int(d2)
        year1 = _year_or_default(y1_raw or y2_raw, default_year)
        year2 = _year_or_default(y2_raw or y1_raw, default_year)
        start = _safe_date(year1, month1, day1)
        end = _safe_date(year2, month2, day2)
        if start and end:
            return start, end

    # --- Nothing matched ---
    return None, None


def log_date_ocr_failure(
    store_slug: str,
    flyer_key: str,
    source_path: Path,
    reason: str,
    log_file: Path,
) -> None:
    """
    Append a row to a CSV log when we fail to detect dates for a flyer.

    store_slug: 'aldi', 'market_basket', etc.
    flyer_key:  something to identify the flyer (week folder, flyer_id, etc.)
    source_path: original file (pdf/png) we tried to OCR
    reason: short text reason, e.g. 'no_date_found', 'ocr_timeout', etc.
    log_file: path to a CSV file, e.g. Path('logs/date_ocr_failures.csv')
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "store_slug": store_slug,
        "flyer_key": flyer_key,
        "source_path": str(source_path),
        "reason": reason,
    }

    write_header = not log_file.exists()
    with log_file.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(row)
