# scripts/check_image_sizes.py
# Usage: python .\scripts\check_image_sizes.py --week 102925 [--minw 1500 --minh 1800]
import argparse
from pathlib import Path
from PIL import Image
import csv

def main():
    ap = argparse.ArgumentParser(description="Check flyer image sizes for all stores for a week.")
    ap.add_argument("--root", default="flyers", help="Root flyers dir (default: flyers)")
    ap.add_argument("--week", required=True, help="Week code, e.g. 102925")
    ap.add_argument("--minw", type=int, default=1500, help="Minimum width for OK (default 1500)")
    ap.add_argument("--minh", type=int, default=1800, help="Minimum height for OK (default 1800)")
    ap.add_argument("--csv", default=None, help="Optional path to write CSV report")
    args = ap.parse_args()

    base = Path(args.root)
    stores = sorted([p.name for p in base.iterdir() if p.is_dir()])
    rows = []
    print(f"[info] Checking stores for week {args.week} in {base.resolve()}")
    print(f"[info] Threshold: width>={args.minw}, height>={args.minh}\n")

    for store in stores:
        raw = base / store / args.week / "raw_images"
        if not raw.exists():
            continue
        any_small = False
        for img in sorted(raw.iterdir()):
            if not img.is_file():
                continue
            if img.suffix.lower() not in {".png",".jpg",".jpeg",".webp",".bmp",".tif",".tiff"}:
                continue
            try:
                with Image.open(img) as im:
                    w, h = im.size
            except Exception as e:
                print(f"[ERR] {store}/{img.name}: {e}")
                rows.append([store, img.name, "", "", "ERROR"])
                continue
            status = "OK" if (w >= args.minw and h >= args.minh) else "SMALL"
            if status == "SMALL":
                any_small = True
            print(f"{store:15} {img.name:20} {w:5}x{h:<5}  {status}")
            rows.append([store, img.name, w, h, status])

        if any_small:
            print(f"-> {store}: has SMALL images — consider re-capturing or using PDF.\n")

    if args.csv:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["store","file","width","height","status"])
            writer.writerows(rows)
        print(f"\n[done] CSV report written to {out.resolve()}")

if __name__ == "__main__":
    main()
