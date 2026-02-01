"""
run_all_stores.py - region-first multi-store runner for Deals-4Me flyers

Folder layout (NEW):
  flyers/<REGION>/<store>/<wk_YYYYMMDD>/
    raw_pdf/
    raw_png/
    raw_images/
    processed/
    ocr/
    exports/
    logs/

What it does:
- Discovers stores under flyers/<REGION>/
- For each store, picks the requested week folder (wk_YYYYMMDD)
- Skips stores with no raw files
- Runs ingest_store_week.py
- Parses the ingest [SUMMARY] line:
    [SUMMARY] files=52 inserted=25 errors=0 week=wk_20251228
- Flags RED cases (raw files present but inserted==0)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple


WEEK_RE = re.compile(r"^wk_\d{8}$", re.IGNORECASE)

SUMMARY_RE = re.compile(
    r"\[SUMMARY\]\s+files=(\d+)\s+inserted=(\d+)\s+errors=(\d+)\s+week=([^\s]+)",
    re.IGNORECASE,
)

RAW_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_week_code(code: str) -> str:
    c = (code or "").strip()
    if not WEEK_RE.match(c):
        raise SystemExit(f"[FATAL] Invalid --week '{code}'. Expected wk_YYYYMMDD (e.g. wk_20251228).")
    return c


def discover_store_dirs(flyers_root: Path, region: str) -> List[Path]:
    region_root = flyers_root / region
    if not region_root.exists():
        raise SystemExit(f"[FATAL] Region folder not found: {region_root}")

    stores: List[Path] = []
    for child in region_root.iterdir():
        if child.is_dir() and not child.name.startswith("_"):
            stores.append(child)

    return sorted(stores, key=lambda p: p.name.lower())


def week_dir_for_store(store_dir: Path, week_code: str) -> Path:
    # store_dir = flyers/<REGION>/<store>
    return store_dir / week_code


def has_raw_files(week_dir: Path) -> bool:
    """
    Detect raw media in:
      - raw_pdf/
      - raw_png/
      - raw_images/
    """
    for sub in ("raw_pdf", "raw_png", "raw_images"):
        d = week_dir / sub
        if not d.exists() or not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix.lower() in RAW_EXTS:
                return True
    return False


def parse_summary(output: str) -> Optional[Tuple[int, int, int, str]]:
    if not output:
        return None
    m = SUMMARY_RE.search(output)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)


def build_ingest_command(backend_dir: Path, *, region: str, store: str, week: str, ocr_mode: str) -> List[str]:
    ingest_script = backend_dir / "ingest_store_week.py"
    if not ingest_script.exists():
        raise SystemExit(f"[FATAL] Missing ingest script: {ingest_script}")

    return [
        sys.executable,
        str(ingest_script),
        "--region", region,
        "--store", store,
        "--week", week,
        "--ocr", ocr_mode,
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flyers-root", type=Path, default=None, help="Project flyers root (default: <project>/flyers)")
    ap.add_argument("--region", required=True, help="Region code, e.g. NE")
    ap.add_argument("--week", required=True, help="Week code, wk_YYYYMMDD")
    ap.add_argument("--store", default=None, help="Optional single store slug, e.g. whole_foods")
    ap.add_argument("--ocr-mode", default="none", choices=["none", "auto", "full"], help="OCR mode for ingest")
    ap.add_argument("--dry-run", action="store_true", help="List what would run, but do not run ingest")
    ap.add_argument("--show-stdout", action="store_true", help="Show full ingest stdout for each store")
    args = ap.parse_args()

    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent.parent  # files_to_run/backend -> files_to_run -> <project>
    flyers_root = args.flyers_root.resolve() if args.flyers_root else (project_root / "flyers")

    region = args.region.strip().upper()
    week_code = ensure_week_code(args.week)
    ocr_mode = args.ocr_mode

    print(f"[INFO] Flyers root: {flyers_root}")
    print(f"[INFO] Region:      {region}")
    print(f"[INFO] Week:        {week_code}")
    print(f"[INFO] Store:       {args.store or 'ALL'}")
    print(f"[INFO] OCR mode:    {ocr_mode}")
    print()

    stores = discover_store_dirs(flyers_root, region)
    if args.store:
        stores = [s for s in stores if s.name.lower() == args.store.lower()]

    total_files = 0
    total_inserted = 0
    total_errors = 0
    red_flags: List[str] = []

    header = "{:<20} {:<12} {:<4} {:>6} {:>8} {:>6} {}".format(
        "Store", "Week", "Raw", "Files", "Inserted", "Errs", "Status"
    )
    print(header)
    print("-" * len(header))

    for store_dir in stores:
        store_slug = store_dir.name
        week_dir = week_dir_for_store(store_dir, week_code)

        if not week_dir.exists():
            print(f"{store_slug:<20} {week_code:<12} {'-':<4} {0:>6} {0:>8} {0:>6} NO WEEK FOLDER")
            continue

        raw = has_raw_files(week_dir)

        if not raw:
            print(f"{store_slug:<20} {week_code:<12} NO {0:>6} {0:>8} {0:>6} no raw files")
            continue

        if args.dry_run:
            print(f"{store_slug:<20} {week_code:<12} YES {0:>6} {0:>8} {0:>6} DRY RUN")
            continue

        cmd = build_ingest_command(backend_dir, region=region, store=store_slug, week=week_code, ocr_mode=ocr_mode)
        proc = subprocess.run(cmd, capture_output=True, text=True)

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        files = inserted = errs = 0
        parsed = parse_summary(stdout)
        if parsed:
            files, inserted, errs, _wk = parsed
        else:
            # If ingest didn't print a summary, treat as error
            errs = 1

        status = "OK"
        if inserted == 0:
            status = "RED FLAG"
            red_flags.append(f"{store_slug}:{week_code}")

        total_files += files
        total_inserted += inserted
        total_errors += errs

        print(f"{store_slug:<20} {week_code:<12} YES {files:>6} {inserted:>8} {errs:>6} {status}")

        if args.show_stdout:
            if stdout.strip():
                print(stdout.rstrip())
            if stderr.strip():
                print(stderr.rstrip())

        # If process non-zero, reflect it (but still keep the row above)
        if proc.returncode != 0 and errs == 0:
            total_errors += 1

    print()
    print(f"[TOTAL] files={total_files} inserted={total_inserted} errors={total_errors}")

    if red_flags:
        print("[TOTAL] RED FLAGS:")
        for r in red_flags:
            print(" -", r)

    print("[DONE]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
