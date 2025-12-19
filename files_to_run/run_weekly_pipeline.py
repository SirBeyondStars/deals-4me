# run_weekly_pipeline.py
# One-store runner with explicit if/elif/else dispatch for OCR / MANUAL / SCRAPER.
# Creates/uses these per-store, per-week folders:
#   flyers/<store>/<week>/{raw_images, ocr_text, manual_text, raw_html, parsed}

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List

# Local helper to map pipeline keys -> on-disk folders (shaws -> shaws_and_star_market, etc.)
from folder_resolver import resolve_store_dir

# --- Optional OCR dependencies (we degrade gracefully if missing) ---
try:
    from PIL import Image  # type: ignore
    import pytesseract  # type: ignore

    # 👇 Tesseract path (your existing setting)
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    _OCR_AVAILABLE = True
except Exception:
    _OCR_AVAILABLE = False

# --- Optional Supabase dependencies (also degrade gracefully) ---
try:
    from supabase import create_client, Client  # type: ignore

    _SUPABASE_AVAILABLE = True
except Exception:
    _SUPABASE_AVAILABLE = False
    Client = object  # type: ignore

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
)

# --- Optional date extractor from parse_flyer_text (if present) ---
try:
    from parse_flyer_text import extract_flyer_dates  # type: ignore

    _DATE_EXTRACTOR_AVAILABLE = True
except Exception:
    _DATE_EXTRACTOR_AVAILABLE = False

# =========================
# Configuration
# =========================

# Store operating modes
#   "ocr"    : expect images under raw_images/
#   "manual" : expect TXT files under manual_text/
#   "scraper": expect HTML/JSON (placeholder here)
STORES = {
    "hannaford": "ocr",
    "shaws": "ocr",
    "pricechopper": "ocr",
    "rochebros": "ocr",
    "stopandshop_mari": "ocr",  # set zip for 02324
    "stopandshop_ct": "ocr",  # set zip for 06106
    "marketbasket": "ocr",  # set "scraper" later when you implement it
    "bigy": "ocr",  # set "scraper" later when you implement it
}

# Flyer week start day per store (controls auto-week folder name if --week not provided)
# One of: "SUN","MON","TUE","WED","THU","FRI","SAT"
STORE_START_DAY = {
    "hannaford": "SUN",
    "shaws": "FRI",
    "pricechopper": "SUN",
    "rochebros": "FRI",
    "stopandshop_mari": "FRI",
    "stopandshop_ct": "FRI",
    "marketbasket": "SUN",
    "bigy": "THU",
}

WEEK_RX = re.compile(r"^\d{6}$")  # e.g., 101025
IMG_EXTS = (".png", ".jpg", ".jpeg")


# =========================
# Small helpers
# =========================

def project_root() -> Path:
    # /scripts/run_weekly_pipeline.py -> go up to project root
    return Path(__file__).resolve().parent.parent


def week_from_date_and_start(today: dt.date, start_day: str) -> str:
    """Compute 6-digit week folder (MMDDYY) whose start is the most recent <start_day>."""
    dow_map = dict(
        SUN=6, MON=0, TUE=1, WED=2, THU=3, FRI=4, SAT=5
    )  # Python: Monday=0
    target = dow_map[start_day.upper()]
    # Find the most recent target weekday (including today)
    delta = (today.weekday() - target) % 7
    week_start = today - dt.timedelta(days=delta)
    return week_start.strftime("%m%d%y")


def week_to_date(week: str) -> dt.date:
    """Convert 'MMDDYY' to date (assume 20YY)."""
    m = int(week[0:2])
    d = int(week[2:4])
    y = 2000 + int(week[4:6])
    return dt.date(y, m, d)


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def list_nonempty(p: Path) -> bool:
    return p.exists() and any(p.iterdir())


def debug_print_paths(store_key: str, week_dir: Path) -> None:
    print(f"[Paths] {store_key} week_dir = {week_dir}")
    for sub in ["raw_images", "ocr_text", "manual_text", "raw_html", "parsed"]:
        print(f"        {sub}: {week_dir / sub}")


def get_supabase_client() -> Client | None:
    """
    Lazily create a Supabase client if everything is configured.
    If anything's missing, we just print a note and skip silently.
    """
    if not _SUPABASE_AVAILABLE:
        print("[Supabase] supabase-py not installed; skipping flyer_weeks upsert.")
        return None
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print(
            "[Supabase] SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set; "
            "skipping flyer_weeks upsert."
        )
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    except Exception as e:
        print(f"[Supabase] Failed to create client: {e}")
        return None


# =========================
# OCR pipeline (images → txt)
# =========================

def run_ocr_pipeline(store_dir: Path, week_dir: Path) -> None:
    raw_images = week_dir / "raw_images"
    ocr_text = week_dir / "ocr_text"
    ensure_dir(ocr_text)

    if not list_nonempty(raw_images):
        print(f"[OCR] No images found in {raw_images}")
        return

    if not _OCR_AVAILABLE:
        print("[OCR] PIL/pytesseract not available; skipping OCR.")
        return

    imgs = sorted([p for p in raw_images.iterdir() if p.suffix.lower() in IMG_EXTS])
    print(f"[OCR] Found {len(imgs)} image(s) in {raw_images}")

    for idx, img_path in enumerate(imgs, 1):
        base = img_path.stem
        out_txt = ocr_text / f"{base}.txt"
        if out_txt.exists():
            print(f"[OCR] Skip (exists) {out_txt.name}")
            continue

        try:
            txt = pytesseract.image_to_string(Image.open(img_path))
            out_txt.write_text(txt, encoding="utf-8")
            print(f"[OCR] Wrote {out_txt.name}")
        except Exception as e:
            print(f"[OCR] ERROR on {img_path.name}: {e}")


# =========================
# Parsing pipeline (txt → csv)
# =========================

def parse_text_to_rows(text: str) -> List[List[str]]:
    """
    Very simple fallback parser:
      - Splits lines
      - Grabs crude 'price' tokens like $x.xx
      - Returns rows: [line_no, price_found, text]
    If you have a richer parser (e.g., parse_flyer_text.py), we try to import it below.
    """
    rows: List[List[str]] = []
    price_rx = re.compile(r"\$\s*\d+(?:\.\d{1,2})?")
    for i, line in enumerate(text.splitlines(), 1):
        m = price_rx.search(line)
        price = m.group(0) if m else ""
        if line.strip():
            rows.append([str(i), price, line.strip()])
    return rows


# Try to use your existing rich parser if present.
_PARSER_USABLE = False
try:
    # Expect a function: parse_text_block(str) -> List[List[str]]  (or similar)
    from parse_flyer_text import parse_text_block  # type: ignore

    _PARSER_USABLE = True
except Exception:
    _PARSER_USABLE = False


def parse_one_txt_to_csv(txt_path: Path, out_csv: Path) -> None:
    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    if _PARSER_USABLE:
        try:
            rows = parse_text_block(text)  # type: ignore
        except Exception as e:
            print(f"[Parse] custom parser failed on {txt_path.name}: {e}; using fallback.")
            rows = parse_text_to_rows(text)
    else:
        rows = parse_text_to_rows(text)

    # Write CSV (basic headers)
    ensure_dir(out_csv.parent)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["line_no", "price", "text"])
        w.writerows(rows)


def run_parse_pipeline_from_ocr(week_dir: Path) -> None:
    ocr_text = week_dir / "ocr_text"
    parsed = week_dir / "parsed"
    ensure_dir(parsed)

    if not list_nonempty(ocr_text):
        print(f"[Parse] Found 0 txt file(s) in {ocr_text}")
        print("[Parse] Nothing to parse.")
        return

    txts = sorted([p for p in ocr_text.iterdir() if p.suffix.lower() == ".txt"])
    print(f"[Parse] Found {len(txts)} txt file(s) in {ocr_text}")

    for txt in txts:
        base = txt.stem
        out_csv = parsed / f"{base}.csv"
        if out_csv.exists():
            print(f"[Parse] Skip (exists) {out_csv.name}")
            continue
        try:
            parse_one_txt_to_csv(txt, out_csv)
            print(f"[Parse] Wrote {out_csv.name}")
        except Exception as e:
            print(f"[Parse] ERROR on {txt.name}: {e}")


def run_manual_parser(week_dir: Path) -> None:
    manual_text = week_dir / "manual_text"
    parsed = week_dir / "parsed"
    ensure_dir(parsed)

    if not list_nonempty(manual_text):
        print(f"[Parse] Found 0 txt file(s) in {manual_text}")
        print("[Parse] Nothing to parse.")
        return

    txts = sorted([p for p in manual_text.iterdir() if p.suffix.lower() == ".txt"])
    print(f"[Parse] Found {len(txts)} txt file(s) in {manual_text}")

    for txt in txts:
        base = txt.stem
        out_csv = parsed / f"{base}.csv"
        if out_csv.exists():
            print(f"[Parse] Skip (exists) {out_csv.name}")
            continue
        try:
            parse_one_txt_to_csv(txt, out_csv)
            print(f"[Parse] Wrote {out_csv.name}")
        except Exception as e:
            print(f"[Parse] ERROR on {txt.name}: {e}")


# =========================
# Scraper placeholder
# =========================

def scraper_is_ready(store_key: str) -> bool:
    # Flip to True when you add an actual scraper for that store.
    return False


def run_scraper(store_dir: Path, week_dir: Path) -> None:
    print(f"[Scraper] (Placeholder) No scraper implemented for '{store_dir.name}' yet.")
    print(f"[Scraper] When ready, write page CSVs to: {week_dir/'parsed'}")


# =========================
# Supabase flyer_weeks upsert (extra layer)
# =========================

def upsert_flyer_week_metadata(store_key: str, week: str, week_dir: Path, start_day: str) -> None:
    """
    Best-effort:
      - Grab one TXT file from ocr_text/ or manual_text/
      - Use extract_flyer_dates(...) if available to get start/end
      - Fallback to week_to_date(week) + 6 days
      - Upsert into Supabase flyer_weeks table
    Does nothing (but logs) if Supabase/date-extractor are not configured.
    """
    if not WEEK_RX.match(week):
        # We only care about real "MMDDYY" weeks, not raw_pdfs/raw_images, etc.
        print(f"[Meta] Week '{week}' is not 6-digit MMDDYY; skipping flyer_weeks upsert.")
        return

    client = get_supabase_client()
    if client is None:
        return

    flyer_start: dt.date | None = None
    flyer_end: dt.date | None = None

    # Look for any TXT file we can inspect
    txt_candidates: List[Path] = []
    for sub in ["ocr_text", "manual_text"]:
        folder = week_dir / sub
        if folder.exists():
            txt_candidates.extend(
                sorted([p for p in folder.iterdir() if p.suffix.lower() == ".txt"])
            )

    if _DATE_EXTRACTOR_AVAILABLE and txt_candidates:
        try:
            sample_txt = txt_candidates[0].read_text(encoding="utf-8", errors="ignore")
            flyer_start, flyer_end = extract_flyer_dates(
                sample_txt, fallback_week=week
            )  # type: ignore
        except Exception as e:
            print(f"[Meta] extract_flyer_dates failed: {e}")

    # Fallbacks if date extractor not present or didn't return anything
    base_start = week_to_date(week)
    if flyer_start is None:
        flyer_start = base_start
    if flyer_end is None:
        flyer_end = base_start + dt.timedelta(days=6)

    payload = {
        "store_slug": store_key,
        "week_code": week,
        "start_date": flyer_start.isoformat(),
        "end_date": flyer_end.isoformat(),
        # You can set this to "new_england" or per-store if you like
        "region": None,
    }

    try:
        client.table("flyer_weeks").upsert(
            payload, on_conflict="store_slug,week_code,region"
        ).execute()
        print(
            f"[Supabase] Upserted flyer_weeks row for store={store_key}, week={week}, "
            f"{flyer_start} → {flyer_end}"
        )
    except Exception as e:
        print(f"[Supabase] ERROR during flyer_weeks upsert: {e}")


# =========================
# Combine step (per week)
# =========================

def combine_csvs(store_key: str, week: str, week_dir: Path) -> None:
    parsed = week_dir / "parsed"
    if not parsed.exists():
        print(f"[Combine] No parsed folder at {parsed}")
        print("[Done] Nothing to combine.")
        return

    csvs = sorted([p for p in parsed.iterdir() if p.suffix.lower() == ".csv"])
    if not csvs:
        print(f"[Combine] No CSVs found in {parsed}")
        print("[Done] Nothing to combine.")
        return

    root = project_root()
    exports = root / "exports"
    ensure_dir(exports)

    week_date = week_to_date(week)
    out_name = f"{store_key}_{week_date:%Y-%m-%d}_combined.csv"
    out_path = exports / out_name

    # Combine all rows (skip headers after first)
    total_rows = 0
    with out_path.open("w", newline="", encoding="utf-8") as f_out:
        writer = csv.writer(f_out)
        wrote_header = False
        for i, csv_path in enumerate(csvs, 1):
            with csv_path.open("r", newline="", encoding="utf-8") as f_in:
                reader = csv.reader(f_in)
                for j, row in enumerate(reader):
                    if j == 0:
                        if not wrote_header:
                            writer.writerow(row)
                            wrote_header = True
                        continue
                    writer.writerow(row)
                    total_rows += 1

    print(f"[Combine] Wrote {out_path} ({total_rows} rows)")
    print(f"[Done] Combined CSV ready: {out_path}")


# =========================
# Main
# =========================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("store", help="store key (e.g., shaws, marketbasket, bigy)")
    parser.add_argument("--week", help="override week folder (MMDDYY), else auto")
    args = parser.parse_args()

    store_key = args.store.lower().strip()
    root = project_root()
    store_dir = resolve_store_dir(root, store_key)

    # Mode dispatch
    store_mode = STORES.get(store_key, "ocr")
    start_day = STORE_START_DAY.get(store_key, "SUN")

    # Resolve week folder
    week = args.week
    if week and not WEEK_RX.match(week):
        print(f"[Error] --week must be 6 digits like 101025; got: {week}")
        sys.exit(2)

    if not week:
        today = dt.date.today()
        week = week_from_date_and_start(today, start_day)
        print(
            f"[Auto-Week] {store_key}: start day={start_day}, "
            f"week start={week_to_date(week)}, folder={week}"
        )

    week_dir = store_dir / week
    # Print a quick path snapshot (handy for debugging)
    # debug_print_paths(store_key, week_dir)

    # Ensure expected subfolders exist
    for sub in ["raw_images", "ocr_text", "manual_text", "raw_html", "parsed"]:
        ensure_dir(week_dir / sub)

    # --- Store mode dispatcher ---
    if store_mode == "ocr":
        print(f"[Mode] {store_key}: using OCR pipeline")
        run_ocr_pipeline(store_dir, week_dir)
        run_parse_pipeline_from_ocr(week_dir)

    elif store_mode == "manual":
        print(f"[Mode] {store_key}: using manual text parser")
        run_manual_parser(week_dir)

    elif store_mode == "scraper":
        print(f"[Mode] {store_key}: using scraper (HTML/JSON)")
        if scraper_is_ready(store_key):
            run_scraper(store_dir, week_dir)
        else:
            print(f"[Skip] Scraper not implemented for {store_key}.")
    else:
        print(f"[Skip] Unknown mode '{store_mode}' for {store_key}.")

    # --- Extra layer: upsert flyer_weeks metadata (non-breaking) ---
    upsert_flyer_week_metadata(store_key, week, week_dir, start_day)

    # Always try to combine whatever was produced
    combine_csvs(store_key, week, week_dir)


if __name__ == "__main__":
    main()
