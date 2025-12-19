# scripts/ingest_pdf_and_ocr.py
# PDF → PNG → OCR in one step, always using the current Python interpreter.

import argparse
import subprocess
from pathlib import Path
import sys  # <<< use the exact interpreter that's running this script

def main():
    ap = argparse.ArgumentParser(description="PDF → PNG → OCR in one step.")
    ap.add_argument("--pdf", required=True, help="Path to flyer PDF")
    ap.add_argument("--store", required=True, help="Store folder (e.g., aldi)")
    ap.add_argument("--week", required=True, help="Week code (e.g., 102925)")
    ap.add_argument("--root", default="flyers", help="Root flyers dir")
    ap.add_argument("--dpi", type=int, default=350, help="Image DPI")
    args = ap.parse_args()

    base = Path(args.root) / args.store / args.week
    raw = base / "raw_images"
    raw.mkdir(parents=True, exist_ok=True)

    # 1) Convert PDF → PNGs (use this exact interpreter)
    cmd_convert = [
        sys.executable, ".\\scripts\\pdf_to_png.py",
        "--pdf", str(args.pdf),
        "--out", str(raw),
        "--dpi", str(args.dpi),
    ]
    print(f"[convert] {' '.join(cmd_convert)}")
    subprocess.run(cmd_convert, check=True)

    # 2) OCR the PNGs (use this exact interpreter)
    cmd_ocr = [
        sys.executable, ".\\scripts\\ocr_folder.py",
        "--store", args.store,
        "--week", args.week,
        "--root", args.root,
    ]
    print(f"[ocr]     {' '.join(cmd_ocr)}")
    subprocess.run(cmd_ocr, check=True)

    print("[done] PDF ingested and OCR complete.")

if __name__ == "__main__":
    main()
