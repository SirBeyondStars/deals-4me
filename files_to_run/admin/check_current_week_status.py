import os
import argparse
import subprocess
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

BASE_DIR = Path(r"C:\Users\jwein\OneDrive\Desktop\deals-4me\flyers")
RUN_OCR_SCRIPT = Path(r"C:\Users\jwein\OneDrive\Desktop\deals-4me\files_to_run\run_ocr_missing.py")

def find_all_week_folders(base_dir: Path):
    weeks = defaultdict(list)
    for store_dir in base_dir.iterdir():
        if not store_dir.is_dir():
            continue
        for sub in store_dir.iterdir():
            name = sub.name
            if sub.is_dir() and len(name) == 6 and name.isdigit():
                weeks[name].append(sub)
    return weeks

def detect_latest_week_by_mtime(weeks_map):
    latest = None
    for week, paths in weeks_map.items():
        freshest_path = max(paths, key=lambda p: p.stat().st_mtime)
        freshest_mtime = freshest_path.stat().st_mtime
        if latest is None or freshest_mtime > latest[2]:
            latest = (week, freshest_path, freshest_mtime)
    return latest

def human_time(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

def count_txt_files(folder: Path):
    return sum(1 for _ in folder.rglob("*.txt"))

def list_image_like(folder: Path):
    exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf", ".webp"}
    return [p for p in folder.rglob("*") if p.suffix.lower() in exts]

def run_ocr_for_targets(week: str, stores: list[str]) -> None:
    """
    Try running OCR only for given stores for the specified week.
    If run_ocr_missing.py supports --week and --only flags, use them.
    Otherwise, call it with just --week (which will process the week generally).
    """
    if not RUN_OCR_SCRIPT.exists():
        print(f"[WARN] OCR script not found: {RUN_OCR_SCRIPT}")
        return

    if stores:
        # Attempt per-store targeting first
        for s in stores:
            try:
                print(f"[OCR] Running OCR for store='{s}' week={week} …")
                subprocess.run(
                    ["python", str(RUN_OCR_SCRIPT), "--week", week, "--only", s],
                    check=False
                )
            except Exception as e:
                print(f"[WARN] Per-store OCR call failed for {s}: {e}")
                # Fallback: whole-week call
                subprocess.run(["python", str(RUN_OCR_SCRIPT), "--week", week], check=False)
    else:
        # Nothing matched; do nothing
        print("[INFO] No target stores passed to OCR runner.")

def main():
    parser = argparse.ArgumentParser(description="Check latest week and optionally OCR newly modified stores.")
    parser.add_argument("--base", type=str, default=str(BASE_DIR), help="Flyers base directory")
    parser.add_argument("--week", type=str, default=None, help="Override week (6 digits, e.g., 102625)")
    parser.add_argument("--top", type=int, default=3, help="Show the top N most recent weeks")
    parser.add_argument("--auto-ocr-new", action="store_true",
                        help="Auto-run OCR for stores in the chosen week with 0 OCR txt and recent mtime")
    parser.add_argument("--window-hours", type=int, default=6,
                        help="How recent a store folder must be (by mtime) to qualify for auto-OCR")
    args = parser.parse_args()

    base = Path(args.base)
    if not base.exists():
        print(f"Base path not found: {base}")
        return

    weeks_map = find_all_week_folders(base)
    if not weeks_map:
        print(f"No 6-digit week folders found under: {base}")
        return

    if args.week:
        if args.week not in weeks_map:
            print(f"Week {args.week} not found under any store.")
            return
        week = args.week
        chosen_path = max(weeks_map[week], key=lambda p: p.stat().st_mtime)
        chosen_mtime = chosen_path.stat().st_mtime
    else:
        detected = detect_latest_week_by_mtime(weeks_map)
        if detected is None:
            print("Could not detect a latest week.")
            return
        week, chosen_path, chosen_mtime = detected

    print(f"=== Checking flyer folders for latest week {week} ===")
    print(f"(Detected by most recent modification: {chosen_path} at {human_time(chosen_mtime)})\n")

    # Show recent weeks
    ranked = []
    for w, paths in weeks_map.items():
        fp = max(paths, key=lambda p: p.stat().st_mtime)
        ranked.append((w, fp.stat().st_mtime))
    ranked.sort(key=lambda x: x[1], reverse=True)

    top_n = min(args.top, len(ranked))
    print("Recent weeks by freshness:")
    for i in range(top_n):
        w, ts = ranked[i]
        mark = "← chosen" if w == week else ""
        print(f"  {w}  {human_time(ts)} {mark}")
    print("")

    # Per-store status + build OCR target list
    stores = sorted([d for d in base.iterdir() if d.is_dir()], key=lambda p: p.name.lower())
    found_count = 0
    need_ocr_recent = []
    recent_cutoff = datetime.now() - timedelta(hours=args.window_hours)

    for store_dir in stores:
        wk = store_dir / week
        if not wk.exists():
            print(f"❌ {store_dir.name:25s} — missing")
            continue

        found_count += 1
        txt_count = count_txt_files(wk)
        ocr_note = f" | OCR txt: {txt_count}"
        print(f"✅ {store_dir.name:25s} — FOUND{ocr_note}")

        # If zero OCR, check if this week folder looks newly modified and has images
        if txt_count == 0:
            mtime_dt = datetime.fromtimestamp(wk.stat().st_mtime)
            has_images = len(list_image_like(wk)) > 0
            if has_images and mtime_dt >= recent_cutoff:
                need_ocr_recent.append(store_dir.name)

    total = len(stores)
    print(f"\nSummary: {found_count}/{total} stores have week {week}.")

    if args.auto_ocr_new:
        if need_ocr_recent:
            print(f"\n[Auto-OCR] Targeting stores modified within last {args.window_hours}h with 0 OCR:")
            print("  " + ", ".join(need_ocr_recent))
            run_ocr_for_targets(week, need_ocr_recent)
            print("\n[Auto-OCR] Complete.")
        else:
            print(f"\n[Auto-OCR] No newly modified, OCR-missing stores within last {args.window_hours}h.")

    print("Done.")

if __name__ == "__main__":
    main()
