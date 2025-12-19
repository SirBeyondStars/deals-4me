# ingest_store_week.py
# Drop-in replacement
# - Always sets flyer_store_id + brand + source_file
# - Optional OCR for image files (--ocr)
# - Keeps week sanity warning + end summary

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional

import requests

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
PDF_EXTS = {".pdf"}

# ---- Store mappings (slug -> DB id / display brand) ----
STORE_ID_MAP = {
    "aldi": 1,
    "big_y": 2,
    "hannaford": 3,
    "market_basket": 4,
    "price_chopper_market_32": 5,
    "pricerite": 6,
    "roche_bros": 7,
    "shaws": 8,
    "stop_and_shop_ct": 9,
    "stop_and_shop_mari": 10,
    "trucchis": 11,
    "wegmans": 12,
    "whole_foods": 13,
}

STORE_BRAND_MAP = {
    "aldi": "Aldi",
    "big_y": "Big Y",
    "hannaford": "Hannaford",
    "market_basket": "Market Basket",
    "price_chopper_market_32": "Price Chopper / Market 32",
    "pricerite": "PriceRite",
    "roche_bros": "Roche Bros",
    "shaws": "Shaw's",
    "stop_and_shop_ct": "Stop & Shop",
    "stop_and_shop_mari": "Stop & Shop",
    "trucchis": "Trucchi's",
    "wegmans": "Wegmans",
    "whole_foods": "Whole Foods",
}


def iso_week_now() -> int:
    return datetime.now().isocalendar().week


def normalize_week_code(raw: str) -> str:
    s = (raw or "").strip().lower().replace(" ", "")
    m = re.fullmatch(r"week(\d{1,2})", s)
    if m:
        return f"week{int(m.group(1))}"
    m2 = re.fullmatch(r"(\d{1,2})", s)
    if m2:
        return f"week{int(m2.group(1))}"
    return s


def list_media_files(week_path: Path) -> List[Path]:
    if not week_path.exists():
        return []
    files: List[Path] = []
    for p in week_path.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in IMAGE_EXTS or ext in PDF_EXTS:
            files.append(p)
    files.sort()
    return files


def supabase_headers(api_key: str) -> dict:
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
        "Accept": "application/json",
    }


def insert_rows_supabase(url: str, key: str, table: str, rows: List[dict]) -> Tuple[bool, str]:
    try:
        endpoint = url.rstrip("/") + f"/rest/v1/{table}"
        r = requests.post(endpoint, headers=supabase_headers(key), data=json.dumps(rows), timeout=60)
        if r.status_code in (200, 201, 204):
            return True, f"Inserted {len(rows)} rows"
        return False, f"HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)


def try_ocr_image(path: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (ocr_text, ocr_name). If OCR deps aren't installed, returns (None, None).
    """
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        img = Image.open(path)
        text = pytesseract.image_to_string(img)
        text = (text or "").strip()
        return text if text else None, "tesseract"
    except Exception:
        return None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--week", required=True)
    ap.add_argument("--region", default=None)
    ap.add_argument("--week-path", required=True)
    ap.add_argument("--table", default="flyer_items")
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--ocr", action="store_true", help="Run OCR on IMAGE files during ingest")
    args = ap.parse_args()

    store = (args.store or "").strip()
    week_code = normalize_week_code(args.week)
    week_path = Path(args.week_path)

    store_id = STORE_ID_MAP.get(store)
    brand = STORE_BRAND_MAP.get(store)
    if store_id is None or brand is None:
        print(f"[ERROR] No store mapping for '{store}' (missing store_id/brand).")
        return 1

    # Guardrail: week sanity warning
    try:
        folder_week_num = int(week_code.replace("week", ""))
        current_week = iso_week_now()
        if abs(folder_week_num - current_week) >= 2:
            print(f"[WARN] Week mismatch: folder={week_code} calendar=week{current_week}")
    except Exception:
        pass

    print(f"[ingest] store={store} brand='{brand}' store_id={store_id} week={week_code}")

    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        print("[ERROR] Missing Supabase credentials (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY).")
        return 1

    media = list_media_files(week_path)
    if not media:
        print("[ingest] No media files found")
        return 0

    rows: List[dict] = []
    ocr_done = 0
    ocr_skipped_pdf = 0

    for p in media:
        ext = p.suffix.lower()

        ocr_text = None
        ocr_name = None

        if args.ocr:
            if ext in IMAGE_EXTS:
                ocr_text, ocr_name = try_ocr_image(p)
                if ocr_text:
                    ocr_done += 1
            elif ext in PDF_EXTS:
                # PDF OCR needs rendering pages to images (poppler/pdf2image/etc).
                # For now, we store file path and leave OCR blank.
                ocr_skipped_pdf += 1

        rows.append(
            {
                "item_name": f"Flyer page {p.stem}",
                "week_code": week_code,
                "flyer_store_id": store_id,
                "brand": brand,
                "source_file": str(p).replace("\\", "/"),
                "ocr_text": ocr_text,
                "ocr_name": ocr_name,
                "promo_start": None,
                "promo_end": None,
            }
        )

    inserted = 0
    errors = 0

    for i in range(0, len(rows), args.batch_size):
        batch = rows[i : i + args.batch_size]
        ok, msg = insert_rows_supabase(url, key, args.table, batch)
        if ok:
            inserted += len(batch)
        else:
            errors += 1
            print(f"[ERROR] Insert batch failed: {msg}")

    if inserted == 0 and len(rows) > 0:
        print("[RED FLAG] Files were found but ZERO rows were inserted")

    print(
        f"[SUMMARY] files={len(rows)} inserted={inserted} errors={errors} "
        f"week={week_code} store={store} ocr_images_with_text={ocr_done} pdf_skipped={ocr_skipped_pdf}"
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
