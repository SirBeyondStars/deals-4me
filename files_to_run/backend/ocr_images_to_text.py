# ocr_images_to_text.py
# OCR a folder of images -> .txt files (one per image)
# Designed for your band-split workflow: raw_png -> ocr_work\wf_bands -> this -> wf_bands_text

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Tuple

# Optional OCR deps (fail fast with a clear message)
try:
    from PIL import Image  # type: ignore
    import pytesseract  # type: ignore
except Exception as e:
    raise SystemExit(
        "[ERROR] Missing OCR deps. Install: pip install pillow pytesseract\n"
        f"Details: {e}"
    )

# Your Tesseract path (same one you've been using)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


def iter_images(in_dir: Path) -> Iterable[Path]:
    for p in sorted(in_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            yield p


def ocr_one(img_path: Path, psm: int, oem: int, lang: str) -> str:
    # Tesseract config:
    # - psm 6: assume a block of text (good default for “tile bands”)
    # - oem 3: default engine
    config = f"--oem {oem} --psm {psm}"
    with Image.open(img_path) as im:
        # Light normalization that often helps OCR
        im = im.convert("RGB")
        return pytesseract.image_to_string(im, lang=lang, config=config)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True, help="Input image folder (e.g., ...\\ocr_work\\wf_bands)")
    ap.add_argument("--out-dir", required=True, help="Output text folder (e.g., ...\\ocr_work\\wf_bands_text)")
    ap.add_argument("--psm", type=int, default=6, help="Tesseract page segmentation mode (default 6)")
    ap.add_argument("--oem", type=int, default=3, help="Tesseract OCR engine mode (default 3)")
    ap.add_argument("--lang", default="eng", help="Tesseract language (default eng)")
    ap.add_argument("--force", action="store_true", help="Re-OCR even if output .txt exists")
    args = ap.parse_args()

    in_dir = Path(args.in_dir).resolve()
    out_dir = Path(args.out_dir).resolve()

    if not in_dir.exists():
        print(f"[ERROR] in-dir not found: {in_dir}")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    imgs = list(iter_images(in_dir))
    if not imgs:
        print(f"[WARN] No images found in: {in_dir}")
        return 0

    ok = 0
    fail = 0
    skipped = 0

    print(f"[OCR] Input:  {in_dir}")
    print(f"[OCR] Output: {out_dir}")
    print(f"[OCR] Found {len(imgs)} image(s)")

    for i, img_path in enumerate(imgs, 1):
        rel = img_path.relative_to(in_dir)
        out_txt = (out_dir / rel).with_suffix(".txt")
        out_txt.parent.mkdir(parents=True, exist_ok=True)

        if out_txt.exists() and not args.force:
            skipped += 1
            continue

        try:
            txt = ocr_one(img_path, psm=args.psm, oem=args.oem, lang=args.lang)
            out_txt.write_text(txt, encoding="utf-8", errors="ignore")
            ok += 1
        except Exception as e:
            fail += 1
            print(f"[OCR] ERROR {img_path.name}: {e}")

        if i % 50 == 0:
            print(f"[OCR] progress: {i}/{len(imgs)} (ok={ok}, fail={fail}, skipped={skipped})")

    print("[DONE]")
    print(f"  images:  {len(imgs)}")
    print(f"  ok:      {ok}")
    print(f"  failed:  {fail}")
    print(f"  skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
