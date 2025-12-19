# scripts/ocr_folder.py
# ---------------------------------------------
# Run example:
#   python .\scripts\ocr_folder.py --store aldi --week 102925
# ---------------------------------------------

import argparse
import os
from pathlib import Path

# pip deps: pillow, pytesseract
from PIL import Image
import pytesseract

# ---- Point pytesseract to your Tesseract binary (Windows) ----
# Uses env var TESSERACT_CMD if set, otherwise falls back to the known install path.
DEFAULT_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
tess_cmd = os.environ.get("TESSERACT_CMD", DEFAULT_TESSERACT)
pytesseract.pytesseract.tesseract_cmd = tess_cmd

ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def list_images(raw_dir: Path):
    """List allowed image files in a stable, name-sorted order."""
    return sorted(p for p in raw_dir.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED)


def ocr_one_image(src: Path) -> str:
    """Open with PIL and OCR to text. Converts to RGB if needed to avoid mode errors."""
    with Image.open(src) as im:
        # Convert paletted/CMYK/etc to RGB so Tesseract is happy
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        text = pytesseract.image_to_string(im)
    return text


def main():
    ap = argparse.ArgumentParser(description="OCR all images in flyers/<store>/<week>/raw_images → ocr_txt/pageNN.txt")
    ap.add_argument("--store", required=True, help="store folder name (e.g., aldi)")
    ap.add_argument("--week", required=True, help="week code (e.g., 102925)")
    ap.add_argument("--root", default="flyers", help="root flyers directory (default: flyers)")
    args = ap.parse_args()

    base = Path(args.root) / args.store / args.week
    raw = base / "raw_images"
    out = base / "ocr_txt"

    # Sanity checks
    if not Path(tess_cmd).exists():
        print(f"[error] Tesseract not found at: {tess_cmd}")
        print("        Fix one of these:")
        print("          • Install Tesseract (UB Mannheim build), or")
        print('          • Set env var TESSERACT_CMD to the full path, e.g.:')
        print('              setx TESSERACT_CMD "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"')
        return 2

    if not raw.exists():
        print(f"[error] Raw images folder not found: {raw}")
        return 2

    out.mkdir(parents=True, exist_ok=True)
    images = list_images(raw)
    print(f"[info] {len(images)} image(s) in {raw}")

    if not images:
        print("[warn] No images found. Put your flyer images into raw_images and re-run.")
        return 0

    errors = 0
    for i, img_path in enumerate(images, 1):
        try:
            text = ocr_one_image(img_path)
            (out / f"page{i:02d}.txt").write_text(text, encoding="utf-8")
            print(f"[OK] {img_path.name} -> page{i:02d}.txt ({len(text)} chars)")
        except Exception as e:
            errors += 1
            print(f"[ERR] {img_path.name}: {e}")

    if errors:
        print(f"[done] Completed with {errors} error(s).")
        return 1

    print("[done] OCR complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
