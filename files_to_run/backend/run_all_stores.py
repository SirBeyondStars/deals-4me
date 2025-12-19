"""
run_all_stores.py - robust multi-store/week runner for Deals-4Me flyers

Chunk 2 guardrails:
- Parses importer stdout for:
    [SUMMARY] files=... inserted=... errors=... week=...
- Marks RED FLAG if files>0 and inserted==0 (even if returncode==0)
- Prints per-store receipt + grand totals

Chunk 2.5 add-on:
- Week mismatch warnings (folder week vs calendar ISO week) in the runner too
"""

import argparse
import subprocess
import sys
from pathlib import Path
import re
from typing import Optional, Dict, List, Tuple
from datetime import datetime


# ---------------------------------------------------------------------------
# CONFIG – EDIT THESE FOR YOUR SETUP
# ---------------------------------------------------------------------------

FLYERS_ROOT = Path(r"C:\deals-4me-flyers")  # <-- CHANGE THIS
DEFAULT_REGION = "NE"  # <-- CHANGE IF NEEDED

IMPORT_SCRIPT = Path(__file__).parent / "ingest_store_week.py"  # <-- keep if same folder

WEEK_NUM_RE = re.compile(r"^week(\d{1,2})$", re.IGNORECASE)
DATE_6DIGIT_RE = re.compile(r"^\d{6}$")

SUMMARY_RE = re.compile(
    r"\[SUMMARY\]\s+files=(\d+)\s+inserted=(\d+)\s+errors=(\d+)\s+week=([^\s]+)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def iso_week_now() -> int:
    return datetime.now().isocalendar().week


def week_num_from_label(label: str) -> Optional[int]:
    m = re.match(r"^week(\d{1,2})$", (label or "").strip().lower())
    if not m:
        return None
    return int(m.group(1))


def week_mismatch_note(folder_week_label: str) -> str:
    """
    Returns a short warning tag if folder week is far from calendar week.
    Warn-only; does not block.
    """
    fw = week_num_from_label(folder_week_label)
    if fw is None:
        return ""
    cw = iso_week_now()
    # Use >=2 to avoid noise (end-of-week / different flyer start days)
    if abs(fw - cw) >= 2:
        return f"⚠ WEEK MISMATCH (folder={folder_week_label}, cal=week{cw})"
    return ""


def discover_store_dirs(root: Path) -> List[Path]:
    if not root.exists():
        raise SystemExit(f"[FATAL] Flyers root does not exist: {root}")

    stores: List[Path] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        name = child.name.lower()
        if name.startswith("_") or name in {"logs", "temp", "tmp"}:
            continue
        stores.append(child)

    return sorted(stores, key=lambda p: p.name.lower())


def classify_week_dirs(store_dir: Path) -> Dict[str, Path]:
    result: Dict[str, Path] = {}

    for child in store_dir.iterdir():
        if not child.is_dir():
            continue

        name = child.name.strip()

        m = WEEK_NUM_RE.match(name)
        if m:
            week_num = int(m.group(1))
            label = f"week{week_num:02d}"
            result[label] = child
            continue

        if DATE_6DIGIT_RE.match(name):
            result[name] = child
            continue

        result[name] = child

    return result


def pick_week_for_store(
    weeks: Dict[str, Path],
    explicit_week: Optional[str] = None
) -> Optional[Tuple[str, Path]]:
    if not weeks:
        return None

    if explicit_week:
        m = WEEK_NUM_RE.match(explicit_week.strip())
        if m:
            normalized = f"week{int(m.group(1)):02d}"
            if normalized in weeks:
                return normalized, weeks[normalized]

        if explicit_week in weeks:
            return explicit_week, weeks[explicit_week]

        for label, path in weeks.items():
            if path.name == explicit_week:
                return label, path

        return None

    numeric_candidates: List[Tuple[int, str]] = []
    for label in weeks:
        m = re.match(r"^week(\d{2})$", label)
        if m:
            numeric_candidates.append((int(m.group(1)), label))

    if numeric_candidates:
        numeric_candidates.sort()
        _, best_label = numeric_candidates[-1]
        return best_label, weeks[best_label]

    best_label = sorted(weeks.keys())[-1]
    return best_label, weeks[best_label]


def has_raw_files(week_dir: Path) -> bool:
    exts = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}

    for child in week_dir.iterdir():
        if child.is_file() and child.suffix.lower() in exts:
            return True

    for sub in ("raw_pdfs", "raw_images", "raw_pdf", "raw_images_snips", "raw_png", "raw_pngs"):
        subdir = week_dir / sub
        if subdir.exists() and subdir.is_dir():
            for child in subdir.rglob("*"):
                if child.is_file() and child.suffix.lower() in exts:
                    return True

    return False


def build_ingest_command(
    store_slug: str,
    week_label: str,
    week_path: Path,
    region: str
) -> List[str]:
    python_exe = sys.executable
    return [
        python_exe,
        str(IMPORT_SCRIPT),
        "--store", store_slug,
        "--week", week_label,
        "--region", region,
        "--week-path", str(week_path),
    ]


def parse_summary(stdout: str) -> Optional[Tuple[int, int, int, str]]:
    """
    Returns (files, inserted, errors, week) or None if not found.
    """
    if not stdout:
        return None
    m = SUMMARY_RE.search(stdout)
    if not m:
        return None
    files = int(m.group(1))
    inserted = int(m.group(2))
    errors = int(m.group(3))
    week = m.group(4)
    return files, inserted, errors, week


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run flyer ingestion for all stores (or a subset) for a given week."
    )
    parser.add_argument("--flyers-root", type=Path, default=FLYERS_ROOT)
    parser.add_argument("--region", type=str, default=DEFAULT_REGION)
    parser.add_argument("--week", type=str, default=None,
                        help="Explicit week folder/label to use (e.g. week49). If omitted, picks latest per store.")
    parser.add_argument("--store", type=str, default=None,
                        help="Limit to a single store slug (e.g. 'aldi'). If omitted, run all stores.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be ingested, but do not actually run the importer.")
    parser.add_argument("--show-stdout", action="store_true",
                        help="Print importer stdout/stderr for each store (verbose).")
    args = parser.parse_args()

    flyers_root: Path = args.flyers_root
    region: str = args.region
    explicit_week: Optional[str] = args.week
    only_store: Optional[str] = args.store.lower() if args.store else None
    dry_run: bool = args.dry_run
    verbose: bool = args.show_stdout

    print(f"[INFO] Flyers root: {flyers_root}")
    print(f"[INFO] Region:      {region}")
    print(f"[INFO] Week:        {explicit_week} (explicit)" if explicit_week else "[INFO] Week:        auto (pick latest per store)")
    print(f"[INFO] Store:       {only_store} (filtered)" if only_store else "[INFO] Store:       ALL stores")
    if dry_run:
        print("[INFO] Mode:        DRY RUN (no ingestion will actually run)")

    # Chunk 2.5: header warning if explicit week looks off
    if explicit_week and WEEK_NUM_RE.match(explicit_week.strip()):
        normalized = f"week{int(WEEK_NUM_RE.match(explicit_week.strip()).group(1)):02d}"
        note = week_mismatch_note(normalized)
        if note:
            print(f"[WARN] {note}")

    print()

    stores = discover_store_dirs(flyers_root)
    if only_store:
        stores = [s for s in stores if s.name.lower() == only_store]
        if not stores:
            print(f"[WARN] No matching store directory for '{only_store}' under {flyers_root}")
            return

    total_files = 0
    total_inserted = 0
    total_errors = 0
    red_flags: List[str] = []
    week_mismatches: List[str] = []

    header = "{:<20}  {:<12}  {:<4}  {:>6}  {:>8}  {:>6}  {}".format(
        "Store", "WeekLabel", "Raw", "Files", "Inserted", "Errs", "Status"
    )
    print(header)
    print("-" * len(header))

    for store_dir in stores:
        store_slug = store_dir.name
        weeks = classify_week_dirs(store_dir)

        if not weeks:
            print(f"{store_slug:<20}  {'-':<12}  {'-':<4}  {0:>6}  {0:>8}  {0:>6}  No week folders, skipping")
            continue

        pick = pick_week_for_store(weeks, explicit_week)
        if not pick:
            reason = f"Explicit week '{explicit_week}' not found" if explicit_week else "No usable week folder found"
            print(f"{store_slug:<20}  {'-':<12}  {'-':<4}  {0:>6}  {0:>8}  {0:>6}  {reason}")
            continue

        week_label, week_path = pick
        raw_present = has_raw_files(week_path)

        if not raw_present:
            status = "No raw files, skipping"
            note = week_mismatch_note(week_label)
            if note:
                status = f"{status} | {note}"
                week_mismatches.append(f"{store_slug}:{week_label}")
            print(f"{store_slug:<20}  {week_label:<12}  {'NO':<4}  {0:>6}  {0:>8}  {0:>6}  {status}")
            continue

        if dry_run:
            status = "(dry run) would ingest"
            note = week_mismatch_note(week_label)
            if note:
                status = f"{status} | {note}"
                week_mismatches.append(f"{store_slug}:{week_label}")
            print(f"{store_slug:<20}  {week_label:<12}  {'YES':<4}  {0:>6}  {0:>8}  {0:>6}  {status}")
            continue

        cmd = build_ingest_command(store_slug, week_label, week_path, region)

        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)

            files = 0
            inserted = 0
            errs = 0
            summary_week = week_label

            parsed = parse_summary(result.stdout or "")
            if parsed:
                files, inserted, errs, summary_week = parsed

            status = "OK"
            if result.returncode != 0:
                status = f"FAIL(code {result.returncode})"

            if files > 0 and inserted == 0:
                status = "RED FLAG (0 inserts)"
                red_flags.append(f"{store_slug}:{week_label}")

            note = week_mismatch_note(week_label)
            if note:
                status = f"{status} | {note}"
                week_mismatches.append(f"{store_slug}:{week_label}")

            total_files += files
            total_inserted += inserted
            total_errors += errs

            print("{:<20}  {:<12}  {:<4}  {:>6}  {:>8}  {:>6}  {}".format(
                store_slug, week_label, "YES", files, inserted, errs, status
            ))

            if verbose:
                if result.stdout:
                    print("  [stdout]")
                    print("  " + "\n  ".join(result.stdout.splitlines()))
                if result.stderr:
                    print("  [stderr]")
                    print("  " + "\n  ".join(result.stderr.splitlines()))

        except Exception as exc:
            status = f"EXCEPTION: {exc!r}"
            note = week_mismatch_note(week_label)
            if note:
                status = f"{status} | {note}"
                week_mismatches.append(f"{store_slug}:{week_label}")
            print("{:<20}  {:<12}  {:<4}  {:>6}  {:>8}  {:>6}  {}".format(
                store_slug, week_label, "YES", 0, 0, 0, status
            ))

    print()
    print(f"[TOTAL] files={total_files} inserted={total_inserted} errors={total_errors}")

    if red_flags:
        print("[TOTAL] RED FLAGS (files found but 0 inserts):")
        for rf in red_flags:
            print(f"  - {rf}")

    if week_mismatches:
        print("[TOTAL] WEEK MISMATCH WARNINGS:")
        for wm in week_mismatches:
            print(f"  - {wm}")

    print("[DONE] run_all_stores.py completed.")


if __name__ == "__main__":
    main()
