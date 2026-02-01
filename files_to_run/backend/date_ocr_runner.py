# date_ocr_runner.py
#
# Standalone runner that:
#  - walks flyers folders for a given week code
#  - OCRs PNGs in raw_png/
#  - uses date_ocr_utils.extract_date_range() to detect flyer date ranges
#  - logs failures to logs/date_ocr_failures.csv
from __future__ import annotations

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

import argparse
import subprocess
from pathlib import Path
from typing import List, Optional

from PIL import Image
import pytesseract

from date_ocr_utils import extract_date_range, log_date_ocr_failure
from ocr_guardrails import get_fail_count, log_ocr_attempt, mark_manual_needed

LOG_FAIL = Path("logs/date_ocr_failures.csv")


def preprocess_for_ocr(image_path: Path) -> Path:
    """
    Create a grayscale, higher-contrast copy for OCR.
    Returns path to the processed image.
    """
    out_path = image_path.with_suffix(".ocr.png")

    if out_path.exists():
        return out_path

    subprocess.run(
        [
            "magick",
            str(image_path),
            "-colorspace",
            "Gray",
            "-contrast-stretch",
            "0.5%x0.5%",
            "-sharpen",
            "0x1",
            str(out_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return out_path


def ocr_image(image_path: Path, store_id: str, week_code: str) -> str:
    """Run OCR on a single image file and return text (with guardrails + preprocessing)."""
    source_file = str(image_path)

    fails = get_fail_count(store_id, week_code, source_file)

    # If it already failed 3+ times, mark it once and stop trying.
    if fails >= 3:
        mark_manual_needed(store_id, week_code, source_file, reason="MAX_FAILS_REACHED")
        log_ocr_attempt(store_id, week_code, source_file, fails + 1, "FAIL", "MAX_FAILS_REACHED")
        return ""

    try:
        ocr_path = preprocess_for_ocr(image_path)
        img = Image.open(ocr_path)
        text = pytesseract.image_to_string(img)

        if text and text.strip():
            log_ocr_attempt(store_id, week_code, source_file, fails + 1, "OK", "OK")
            return text

        # Empty text = failure
        log_ocr_attempt(store_id, week_code, source_file, fails + 1, "FAIL", "EMPTY_TEXT")
        if (fails + 1) >= 3:
            mark_manual_needed(store_id, week_code, source_file, reason="FAILED_3X_EMPTY_TEXT")
        return ""

    except Exception as e:
        log_ocr_attempt(
            store_id,
            week_code,
            source_file,
            fails + 1,
            "FAIL",
            f"EXCEPTION:{type(e).__name__}",
        )
        if (fails + 1) >= 3:
            mark_manual_needed(store_id, week_code, source_file, reason=f"FAILED_3X_EXCEPTION:{type(e).__name__}")
        return ""


def find_store_week_pngs(flyers_root: Path, week_code: str) -> List[tuple]:
    """
    Return a list of (store_slug, flyer_key, image_path) for all PNGs under:
      <flyers_root>/<store_slug>/<week_code>/raw_png/*.png
    """
    results: List[tuple] = []

    if not flyers_root.exists():
        print(f"[date_ocr] Flyers root does not exist: {flyers_root}")
        return results

    for store_dir in flyers_root.iterdir():
        if not store_dir.is_dir():
            continue

        store_slug = store_dir.name
        week_dir = store_dir / week_code
        png_dir = week_dir / "raw_png"

        if not png_dir.exists():
            continue

        for img_path in png_dir.glob("*.png"):
        # Skip already-processed OCR images
         if ".ocr." in img_path.name:
          continue

    flyer_key = f"{store_slug}:{week_code}"
    results.append((store_slug, flyer_key, img_path))

    return results


def run_for_week(flyers_root: Path, week_code: str, default_year: Optional[int] = None) -> None:
    print(f"[date_ocr] Scanning flyers in {flyers_root} for {week_code}...")

    triplets = find_store_week_pngs(flyers_root, week_code)
    if not triplets:
        print(f"[date_ocr] No raw_png images found for {week_code}.")
        return

    success_count = 0
    fail_count = 0

    for store_slug, flyer_key, img_path in triplets:
        print(f"[date_ocr] {store_slug} {week_code} -> {img_path.name}")

        text = ocr_image(img_path, store_id=store_slug, week_code=week_code)
        start_date, end_date = extract_date_range(text, default_year=default_year)

        if start_date and end_date:
            success_count += 1
            print(f"  ✅ Dates detected: {start_date.isoformat()} -> {end_date.isoformat()}")
        else:
            fail_count += 1
            print("  ❌ No date range detected.")
            log_date_ocr_failure(
                store_slug=store_slug,
                flyer_key=flyer_key,
                source_path=img_path,
                reason="no_date_found",
                log_file=LOG_FAIL,
            )
            
            log_ocr_attempt(
                store_id=store_slug,
                week_code=week_code,
                source_file=str(img_path),
                attempt=999,
                status="FAIL",
                reason="NO_DATE_FOUND",
            )
            
            

    print(f"[date_ocr] Done. Success: {success_count}, Failures: {fail_count}")
    if fail_count > 0:
        print(f"[date_ocr] See failure log: {LOG_FAIL}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect flyer date ranges using OCR on raw_png snippets.",
    )
    parser.add_argument(
        "--flyers-root",
        required=True,
        help="Root folder where store subfolders live (e.g. D:\\flyers\\NE)",
    )
    parser.add_argument(
        "--week-code",
        required=True,
        help="Week code, e.g. week51 or week51_2025",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Default year to assume if OCR doesn't include a year (e.g. 2025).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.flyers_root)
    week_code = args.week_code
    default_year = args.year

    run_for_week(root, week_code, default_year=default_year)


if __name__ == "__main__":
    main()
