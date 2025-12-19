#!/usr/bin/env python3
"""
prep_week_folders.py
Create ONLY missing week folders under flyers/<store>/<week>/raw_images,
with support for per-store ad cycle start days and mid-week overrides.

Usage examples:
  # Prep NEXT cycle per store (default behavior), only missing
  python scripts/prep_week_folders.py --force

  # Prep CURRENT cycle per store, only missing
  python scripts/prep_week_folders.py --period current --force

  # Target a specific week for all stores (overrides cycle logic)
  python scripts/prep_week_folders.py --week 102625 --force

  # Only specific stores (names are folder names under flyers/)
  python scripts/prep_week_folders.py --stores trucchis shaws --period current --force

  # Dry run (show what would be created)
  python scripts/prep_week_folders.py --period current --dry-run --force
"""

from __future__ import annotations
import argparse
import sys
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import List, Dict

# ---------- paths / config ----------
PROJECT_ROOT = Path(__file__).resolve().parents[1]         # deals-4me/
FLYERS_DIR   = PROJECT_ROOT / "flyers"                      # deals-4me/flyers
INBOX_DIR    = FLYERS_DIR / "_inbox"
WEEK_FMT     = "%m%d%y"                                     # MMddyy (e.g., 102625)

# Map of store folder name -> weekly ad start day (0=Mon ... 6=Sun)
# Tweak these as you learn each store's cycle. Unknown stores default to 5 (Friday).
CYCLE_MAP: Dict[str, int] = {
    "aldi": 3,             # Wed
    "whole_foods": 3,      # Wed (Prime promos flip mid-week)
    "shaws": 5,            # Fri
    "stopandshop": 5,      # Fri
    "big_y": 4,            # Thu
    "hannaford": 0,        # Mon (adjust if needed)
    "wegmans": 3,          # Wed-ish; Wegmans varies (use what fits you)
    "price_rite": 4,       # Thu (example)
    "market_basket": 4,    # Thu (many MBs flip Thu)
    "trucchis": 6,         # Sun (your call; adjust once confirmed)
}

# ---------- helpers ----------
def is_saturday() -> bool:
    # Monday=0 ... Saturday=5, Sunday=6
    return datetime.now().weekday() == 5

def normalize_store_name(s: str) -> str:
    return s.strip().lower().replace(" ", "_")

def existing_store_dirs() -> List[str]:
    """Return store folder names that already exist under flyers/ (exclude _inbox)."""
    if not FLYERS_DIR.exists():
        return []
    return sorted([p.name for p in FLYERS_DIR.iterdir() if p.is_dir() and p.name != "_inbox"])

def ensure_dir(p: Path, dry_run: bool) -> None:
    if not dry_run:
        p.mkdir(parents=True, exist_ok=True)

def week_code_for_store(start_dow: int, period: str = "next", ref: date | None = None) -> str:
    """
    Compute the week code (MMddyy) for a store given its weekly ad start day.
    start_dow: 0=Mon ... 6=Sun
    period: 'current' -> most recent start on/before 'ref' (active cycle)
            'next'    -> next upcoming start after 'ref'
    """
    ref = ref or date.today()
    wd = ref.weekday()  # 0..6
    if period == "current":
        delta = (wd - start_dow) % 7
        eff = ref - timedelta(days=delta)
    else:  # 'next'
        delta = (start_dow - wd) % 7
        if delta == 0:
            delta = 7
        eff = ref + timedelta(days=delta)
    return eff.strftime(WEEK_FMT)

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Create ONLY missing week/raw_images folders for flyers.")
    ap.add_argument("--week", help="Week code (MMddyy). If provided, overrides per-store cycle logic.", default=None)
    ap.add_argument("--period", choices=["current", "next"], default="next",
                    help="Use each store's CURRENT or NEXT ad cycle to compute week code (ignored if --week is provided).")
    ap.add_argument("--stores", nargs="*", help="Specific store folder names (e.g., aldi shaws trucchis). Omit to use all stores found under flyers/.", default=None)
    ap.add_argument("--force", action="store_true", help="Bypass Saturday-only guard (safe mid-week override).")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be created, but do not write anything.")
    args = ap.parse_args()

    # Saturday guard (you can still override safely)
    if not is_saturday() and not args.force:
        print("⚠️  Not Saturday. Use --force for a safe mid-week run (only missing folders are created).")
        sys.exit(1)

    # Collect store list
    if args.stores:
        stores = [normalize_store_name(s) for s in args.stores]
    else:
        stores = existing_store_dirs()

    if not stores:
        print("ℹ️  No store folders found under 'flyers/'. Create at least one (e.g., 'flyers\\trucchis') or pass --stores.")
        sys.exit(0)

    # Ensure base folders exist
    FLYERS_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    created: List[str] = []
    skipped_existing: List[str] = []
    skipped_missing_top: List[str] = []
    computed_weeks: Dict[str, str] = {}  # store -> week used

    # Prepare per store
    for store in stores:
        store_dir = FLYERS_DIR / store
        if not store_dir.exists():
            skipped_missing_top.append(store)
            continue

        # Determine week for this store
        if args.week:
            week_code = args.week
        else:
            start_dow = CYCLE_MAP.get(store, 5)  # default Friday if unknown
            week_code = week_code_for_store(start_dow, period=args.period)
        computed_weeks[store] = week_code

        # Target path flyers/<store>/<week>/raw_images
        target = store_dir / week_code / "raw_images"
        if target.exists():
            skipped_existing.append(store)
        else:
            print(f"📁 Creating: {target}")
            ensure_dir(target, args.dry_run)
            created.append(store)

    # Summary
    print("\n— Summary —")
    if args.week:
        print(f"Week (override for all): {args.week}")
    else:
        print(f"Period: {args.period}  (per-store week based on CYCLE_MAP)")

    print(f"Dry run: {'yes' if args.dry_run else 'no'}")
    if created:
        print(f"✅ Created ({len(created)}): {', '.join(created)}")
    else:
        print("✅ Created: 0")

    if skipped_existing:
        print(f"🟡 Already existed ({len(skipped_existing)}): {', '.join(skipped_existing)}")

    if skipped_missing_top:
        print(f"🔴 Skipped (no top-level folder under flyers/) ({len(skipped_missing_top)}): {', '.join(skipped_missing_top)}")
        print("   → Create the top-level store folder once, e.g.:  mkdir flyers\\trucchis")
        print("     Then re-run with --stores trucchis (and it will create only the missing week folder).")

    # Show per-store computed weeks when not using --week
    if not args.week and computed_weeks:
        print("\nPer-store week codes used:")
        for s in sorted(computed_weeks):
            print(f"  - {s}: {computed_weeks[s]}")

    print("\nDone.")

if __name__ == "__main__":
    main()
