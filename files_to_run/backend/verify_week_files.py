from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List, Optional

import requests

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
PDF_EXTS = {".pdf"}

STORE_SLUGS = [
    "aldi",
    "big_y",
    "hannaford",
    "market_basket",
    "price_chopper_market_32",
    "pricerite",
    "roche_bros",
    "shaws",
    "stop_and_shop_ct",
    "stop_and_shop_mari",
    "trucchis",
    "wegmans",
    "whole_foods",
]

# If your on-disk store folder names differ, map them here.
# Otherwise it will use the slug as the folder name.
STORE_DIR_OVERRIDE: Dict[str, str] = {
    # "price_chopper_market_32": "price_chopper",
    # "stop_and_shop_mari": "stop_and_shop_ri_ma",  # example
}


def normalize_week_code(raw: str) -> str:
    """
    Accepts common formats and returns a folder-friendly week code:
      - "week51" -> "week51"
      - "51"     -> "week51"
      - "wk_20251228" / "wk20251228" -> "wk_20251228"
      - "20251228" -> "wk_20251228"   (assumes YYYYMMDD start-date style)
    """
    s = (raw or "").strip().lower().replace(" ", "")
    if not s:
        return s

    if s.startswith("week"):
        return s

    if s.startswith("wk_") and s[3:].isdigit() and len(s[3:]) == 8:
        return s
    if s.startswith("wk") and s[2:].isdigit() and len(s[2:]) == 8:
        return "wk_" + s[2:]

    if s.isdigit() and len(s) == 8:
        return "wk_" + s

    if s.isdigit():
        return f"week{int(s)}"

    return s


def list_media_files(folder: Path) -> List[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    out: List[Path] = []
    for p in folder.iterdir():
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in IMAGE_EXTS or ext in PDF_EXTS:
            # skip "date" anchor if present
            if p.name.lower() in ("date.png", "date.jpg", "date.jpeg"):
                continue
            out.append(p)
    out.sort()
    return out


def supabase_headers(api_key: str) -> dict:
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }


def fetch_db_counts_total(url: str, key: str, week_code: str) -> Dict[str, int]:
    """
    Read-only totals for a given week_code from flyer_items.
    Assumes flyer_items has fields: flyer_store_id, brand, source_file, week_code.
    """
    endpoint = (
        url.rstrip("/")
        + "/rest/v1/flyer_items"
        + "?select=flyer_store_id,brand,source_file"
        + f"&week_code=eq.{week_code}"
        + "&limit=100000"
    )

    r = requests.get(endpoint, headers=supabase_headers(key), timeout=60)
    r.raise_for_status()
    rows = r.json()

    out = {
        "db_rows_total": len(rows),
        "db_rows_missing_source_file": 0,
        "db_rows_missing_brand": 0,
        "db_rows_missing_store_id": 0,
    }

    for row in rows:
        if row.get("source_file") is None:
            out["db_rows_missing_source_file"] += 1
        if row.get("brand") is None:
            out["db_rows_missing_brand"] += 1
        if row.get("flyer_store_id") is None:
            out["db_rows_missing_store_id"] += 1

    return out


def resolve_default_flyers_root() -> Path:
    """
    Flyers root resolution order:
      1) env DEALS4ME_FLYERS_ROOT if set
      2) <project_root>/flyers based on this file's location
    """
    env_root = os.getenv("DEALS4ME_FLYERS_ROOT", "").strip()
    if env_root:
        return Path(env_root)

    # This file lives at: <project_root>/files_to_run/backend/verify_week_files.py
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "flyers"


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="verify_week_files.py",
        description="Disk proof scanner for weekly flyer folders + optional Supabase read-only totals.",
    )

    ap.add_argument(
        "store",
        nargs="?",
        default="all",
        help='Optional store slug (e.g. "whole_foods"). Default: all stores.',
    )

    ap.add_argument(
        "--week",
        required=True,
        help='Examples: week51 | 51 | wk_20251228 | wk20251228 | 20251228',
    )

    ap.add_argument(
        "--flyers-root",
        default=None,
        help='Flyers root folder. If omitted, uses env DEALS4ME_FLYERS_ROOT or "<project_root>/flyers".',
    )

    ap.add_argument(
        "--check-db",
        action="store_true",
        help="Also read DB totals for that week (NO WRITES). Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY).",
    )

    args = ap.parse_args()

    store = (args.store or "all").strip().lower()
    if store != "all" and store not in STORE_SLUGS:
        print(f"[FATAL] Unknown store slug: {store}")
        print(f"        Valid: {', '.join(STORE_SLUGS)}")
        return 1

    slugs = STORE_SLUGS if store == "all" else [store]

    week_code = normalize_week_code(args.week)

    flyers_root = Path(args.flyers_root).expanduser() if args.flyers_root else resolve_default_flyers_root()
    flyers_root = flyers_root.resolve()

    if not flyers_root.exists():
        print(f"[FATAL] flyers_root not found: {flyers_root}")
        print('        Tip: pass --flyers-root or set env DEALS4ME_FLYERS_ROOT.')
        return 1

    print(f"[INFO] flyers_root: {flyers_root}")
    print(f"[INFO] week:       {week_code}")
    print(f"[INFO] store(s):   {('ALL' if store == 'all' else store)}")
    print()

    # Header
    print(f"{'store':<22} {'week_dir':<4} {'raw_pdf':>7} {'raw_png':>7} {'top':>5} {'total':>6}  sample_files")
    print("-" * 95)

    totals = {"raw_pdf": 0, "raw_png": 0, "top": 0, "total": 0}
    stores_with_any = 0

    for slug in slugs:
        store_dir_name = STORE_DIR_OVERRIDE.get(slug, slug)
        week_dir = flyers_root / store_dir_name / week_code

        raw_pdf_dir = week_dir / "raw_pdf"
        raw_png_dir = week_dir / "raw_png"

        raw_pdf_files = list_media_files(raw_pdf_dir)
        raw_png_files = list_media_files(raw_png_dir)
        top_files = list_media_files(week_dir)

        total = len(raw_pdf_files) + len(raw_png_files) + len(top_files)
        week_dir_flag = "YES" if week_dir.exists() else "NO"

        if total > 0:
            stores_with_any += 1

        totals["raw_pdf"] += len(raw_pdf_files)
        totals["raw_png"] += len(raw_png_files)
        totals["top"] += len(top_files)
        totals["total"] += total

        sample: List[str] = []
        for p in (raw_pdf_files[:1] + raw_png_files[:1] + top_files[:1]):
            sample.append(p.name)
        sample_str = ", ".join(sample) if sample else "-"

        print(
            f"{slug:<22} {week_dir_flag:<4} "
            f"{len(raw_pdf_files):>7} {len(raw_png_files):>7} {len(top_files):>5} {total:>6}  {sample_str}"
        )

    print("-" * 95)
    print(
        f"{'TOTAL':<22} {'':<4} "
        f"{totals['raw_pdf']:>7} {totals['raw_png']:>7} {totals['top']:>5} {totals['total']:>6}  "
        f"stores_with_any={stores_with_any}/{len(slugs)}"
    )
    print()

    if args.check_db:
        url = os.getenv("SUPABASE_URL", "").strip()
        key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_KEY", "").strip())
        if not url or not key:
            print("[WARN] --check-db was set, but SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) are missing.")
            return 0

        try:
            t = fetch_db_counts_total(url, key, week_code)
            print("[DB] flyer_items (week only) totals (read-only):")
            print(f"     db_rows_total:               {t['db_rows_total']}")
            print(f"     db_rows_missing_source_file: {t['db_rows_missing_source_file']}")
            print(f"     db_rows_missing_brand:       {t['db_rows_missing_brand']}")
            print(f"     db_rows_missing_store_id:    {t['db_rows_missing_store_id']}")
            print()
            print("[PROOF] Disk totals vs DB totals:")
            print(f"        disk_files_total: {totals['total']}")
            print(f"        db_rows_total:    {t['db_rows_total']}")
        except Exception as e:
            print(f"[WARN] DB read failed: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
