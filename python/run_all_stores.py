# run_all_stores.py
# Batch runner with region support and auto week detection.

import argparse
import re
import sys
from pathlib import Path

from folder_resolver import resolve_store_dir
from run_weekly_pipeline import main as run_weekly_pipeline

# --------------------------
# Regions → store keys
# (pipeline keys, not folder names)
# --------------------------
REGIONS = {
    "new_england": [
        "hannaford",
        "shaws",
        "pricechopper",
        "rochebros",
        "stopandshop_mari",
	"stopandshop_ct",
        "marketbasket",
        "bigy",
    ],
    # Add future regions here (examples):
    # "midatlantic": ["giant", "weis", "acme"],
    # "southeast":   ["publix", "foodlion"],
    # "midwest":     ["meijer", "hyvee", "jewelosco"],
    # "westcoast":   ["safeway", "ralphs", "albertsons"],
}

WEEK_RX = re.compile(r"^\d{6}$")  # e.g., 101025

def project_root() -> Path:
    return Path(__file__).resolve().parent.parent  # /deals-4me

def _nonempty(p: Path) -> bool:
    return p.exists() and any(p.iterdir())

def has_inputs(week_dir: Path) -> bool:
    """Consider a week 'ready' if any expected input folder is non-empty."""
    return any(
        _nonempty(week_dir / sub)
        for sub in ("raw_images", "manual_text", "raw_html")
    )

def latest_ready_week(store_root: Path) -> str | None:
    """Pick the newest 6-digit week folder that actually has inputs."""
    if not store_root.exists():
        return None
    week_dirs = [d for d in store_root.iterdir() if d.is_dir() and WEEK_RX.match(d.name)]
    for d in sorted(week_dirs, key=lambda p: p.name, reverse=True):
        if has_inputs(d):
            return d.name
    return None

def collect_stores_for_region(region: str) -> list[str]:
    if region.lower() == "all":
        # union of all regions (deduplicated, keep order by region listing)
        seen, result = set(), []
        for stores in REGIONS.values():
            for s in stores:
                if s not in seen:
                    seen.add(s)
                    result.append(s)
        return result
    if region not in REGIONS:
        raise SystemExit(f"[Error] Unknown region '{region}'. "
                         f"Choose one of: {', '.join(['all'] + list(REGIONS.keys()))}")
    return REGIONS[region]

def run_all_stores(stores: list[str], week_override: str | None) -> None:
    ROOT = project_root()

    for store in stores:
        print(f"\n[All] Starting run for {store} …")

        store_dir = resolve_store_dir(ROOT, store)  # maps alias → correct folder
        if not store_dir.exists():
            print(f"[Skip] Store folder not found: {store_dir}")
            continue

        # Decide week to run
        if week_override:
            if not WEEK_RX.match(week_override):
                print(f"[Skip] --week must be 6 digits like 101025; got: {week_override}")
                continue
            week = week_override
            print(f"[Auto] {store}: using specified --week {week}")
        else:
            week = latest_ready_week(store_dir)
            if not week:
                print(f"[Skip] No ready inputs found under {store_dir} "
                      f"(raw_images/manual_text/raw_html).")
                continue
            print(f"[Auto] {store}: using existing week folder {week}")

        try:
            # Mimic CLI call: python run_weekly_pipeline.py <store> --week <week>
            sys.argv = ["run_weekly_pipeline.py", store, "--week", week]
            run_weekly_pipeline()
        except Exception as e:
            print(f"[ERROR] Failed to run {store}: {e}")

    print("\n[All] Finished running selected stores.")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Deals-4Me pipelines by region.")
    parser.add_argument(
        "--region",
        default="new_england",
        help="Region to run (default: new_england). "
             "Use 'all' to run every region.",
    )
    parser.add_argument(
        "--week",
        help="Override week folder (MMDDYY). If omitted, auto-detect latest week with inputs.",
    )
    args = parser.parse_args()

    stores = collect_stores_for_region(args.region.lower())
    run_all_stores(stores, args.week)

if __name__ == "__main__":
    main()
