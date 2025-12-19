"""
scan_archived_weeks.py

Quick scanner for your archived flyers.

Assumes structure like:

deals-4me/
    deals-4me-archived-files/
        aldi/
            102925/
                pdf/
                raw_images/
                ...
            110125/
                ...
        big_y/
            102925/
            ...
        shaws/
            ...
        Week46/          # new-style week folder (optional, will be handled too)

What it does:
- Walks each store folder under deals-4me-archived-files
- For each week/date folder under that store, counts PDFs and images
- Ignores week folders that have *no* pdf/raw_images files
- Prints a summary grouped by (week -> stores) to the console
- Writes the same info to archive_report.csv for reference

This is SAFE: it does not modify or delete anything.
"""

from pathlib import Path
import csv

# Change this if your path is slightly different
ARCHIVE_ROOT = Path(__file__).resolve().parent / "deals-4me-archived-files"

# File extensions we care about
PDF_EXTS = {".pdf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}


def is_week_folder(name: str) -> bool:
    """
    Heuristic for week/date folder names inside a store:
    - Either 6 digits like 102925 (MMDDYY)
    - Or 'WeekNN', 'weekNN', etc.
    """
    name_lower = name.lower()
    if name_lower.startswith("week") and name_lower[4:].isdigit():
        return True
    if len(name) == 6 and name.isdigit():
        return True
    return False


def count_files_in_week(week_path: Path):
    """
    Look for PDFs and images in likely places inside a week folder:
    - pdf/
    - raw_images/
    - raw_images_hd/
    (and directly under the week folder just in case)
    """
    pdf_count = 0
    img_count = 0

    # Directly under the week folder
    for p in week_path.iterdir():
        if p.is_file():
            ext = p.suffix.lower()
            if ext in PDF_EXTS:
                pdf_count += 1
            elif ext in IMAGE_EXTS:
                img_count += 1

    # Standard subfolders you showed in the screenshot
    for subname in ["pdf", "raw_images", "raw_images_hd"]:
        subdir = week_path / subname
        if subdir.is_dir():
            for p in subdir.rglob("*"):
                if p.is_file():
                    ext = p.suffix.lower()
                    if ext in PDF_EXTS:
                        pdf_count += 1
                    elif ext in IMAGE_EXTS:
                        img_count += 1

    return pdf_count, img_count


def scan_archive(root: Path):
    """
    Walk the archive and build a dict:
       week_code -> list of (store_slug, pdf_count, image_count)
    """
    if not root.is_dir():
        print(f"[ERROR] Archive root not found: {root}")
        return {}

    print(f"[scan] Scanning archive root: {root}")
    week_map = {}  # week_code -> list of dicts {store, pdfs, images}

    # Root contains store folders AND maybe WeekNN folders
    for entry in root.iterdir():
        if not entry.is_dir():
            continue

        name = entry.name

        # If this is a WeekNN folder at root, treat it as "mixed stores" week
        if is_week_folder(name):
            week_code = name
            # We don't know store structure in here yet; just report it as-is
            pdfs, imgs = count_files_in_week(entry)
            if pdfs == 0 and imgs == 0:
                continue
            week_map.setdefault(week_code, []).append({
                "store": "(mixed-or-unknown)",
                "pdfs": pdfs,
                "images": imgs,
            })
            continue

        # Otherwise, assume this is a store folder like 'aldi', 'big_y', etc.
        store_slug = name
        for week_entry in entry.iterdir():
            if not week_entry.is_dir():
                continue

            if not is_week_folder(week_entry.name):
                # e.g. 'logs', 'exports', etc. inside store root — skip
                continue

            week_code = week_entry.name
            pdfs, imgs = count_files_in_week(week_entry)

            # Ignore completely empty weeks
            if pdfs == 0 and imgs == 0:
                continue

            week_map.setdefault(week_code, []).append({
                "store": store_slug,
                "pdfs": pdfs,
                "images": imgs,
            })

    return week_map


def print_report(week_map):
    if not week_map:
        print("[scan] No non-empty week folders found.")
        return

    print("\n========== ARCHIVE SUMMARY ==========")
    for week_code in sorted(week_map.keys()):
        print(f"\nWeek/Date: {week_code}")
        for info in sorted(week_map[week_code], key=lambda d: d["store"]):
            store = info["store"]
            pdfs = info["pdfs"]
            imgs = info["images"]
            print(f"  - {store:20s} PDFs: {pdfs:3d} | Images: {imgs:3d}")
    print("\n=====================================\n")


def write_csv(week_map, csv_path: Path):
    if not week_map:
        return

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["week_code", "store_slug", "pdf_count", "image_count"])
        for week_code, stores in week_map.items():
            for info in stores:
                writer.writerow([
                    week_code,
                    info["store"],
                    info["pdfs"],
                    info["images"],
                ])

    print(f"[scan] Wrote archive report to: {csv_path}")


def main():
    week_map = scan_archive(ARCHIVE_ROOT)
    print_report(week_map)
    csv_path = Path(__file__).resolve().parent / "archive_report.csv"
    write_csv(week_map, csv_path)


if __name__ == "__main__":
    main()
