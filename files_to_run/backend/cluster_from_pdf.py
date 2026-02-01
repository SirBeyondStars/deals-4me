from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import fitz  # PyMuPDF
from PIL import Image, ImageOps

import pytesseract
from pytesseract import Output

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

from offer_clusterer import OcrWord, build_offers_from_words, default_store_knobs


def render_pdf_to_images(pdf_path: str, out_dir: Path, dpi: int) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths: List[Path] = []

    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        p = out_dir / f"page_{i+1:02d}.png"
        pix.save(str(p))
        paths.append(p)

    return paths


def prep_for_ocr(img_rgb: Image.Image, invert: bool = False) -> Image.Image:
    """
    Simple image cleanup to help OCR:
      - grayscale
      - optional invert (negative)
      - autocontrast to stretch faint text
    """
    g = img_rgb.convert("L")
    if invert:
        g = ImageOps.invert(g)
    g = ImageOps.autocontrast(g)
    return g


def ocr_words_from_image(img_path: Path) -> List[OcrWord]:
    """
    Page-level OCR for clustering:
      - run OCR on normal image
      - run OCR on inverted (negative) image
      - merge results, keeping higher-confidence duplicates
    """
    img_rgb = Image.open(img_path).convert("RGB")

    def words_from(img_for_ocr: Image.Image) -> List[OcrWord]:
        data = pytesseract.image_to_data(img_for_ocr, output_type=Output.DICT)
        words: List[OcrWord] = []
        n = len(data["text"])
        for i in range(n):
            t = (data["text"][i] or "").strip()
            if not t:
                continue
            try:
                conf = int(float(data["conf"][i]))
            except Exception:
                conf = -1

            x = int(data["left"][i])
            y = int(data["top"][i])
            w = int(data["width"][i])
            h = int(data["height"][i])
            words.append(OcrWord(text=t, x0=x, y0=y, x1=x + w, y1=y + h, conf=conf))
        return words

    w1 = words_from(prep_for_ocr(img_rgb, invert=False))
    w2 = words_from(prep_for_ocr(img_rgb, invert=True))

    # Merge + de-dupe: keep the higher confidence word if it’s the same box/text
    best = {}
    for w in (w1 + w2):
        key = (w.text, w.x0, w.y0, w.x1, w.y1)
        if key not in best or w.conf > best[key].conf:
            best[key] = w

    return list(best.values())


def ocr_offer_pass2(img_path: Path) -> str:
    """
    Offer-crop OCR (extra pass):
      - OCR on normal crop + inverted crop
      - return combined text so downstream parsing has more signal
    """
    img_rgb = Image.open(img_path).convert("RGB")

    config = "--psm 6 -c tessedit_char_whitelist=0123456789.$/¢"

    t1 = pytesseract.image_to_string(prep_for_ocr(img_rgb, invert=False), config=config)
    t2 = pytesseract.image_to_string(prep_for_ocr(img_rgb, invert=True), config=config)

    return (t1.strip() + "\n" + t2.strip()).strip()


def crop_and_save_offers(img_path: Path, offers, store_knobs: dict, debug_dir: Path) -> None:
    img = Image.open(img_path).convert("RGB")
    pad = int(store_knobs["pad_px"])

    offer_dir = debug_dir / (img_path.stem + "_offers")
    offer_dir.mkdir(parents=True, exist_ok=True)

    for idx, off in enumerate(offers, start=1):
        x0, y0, x1, y1 = off.bbox
        x0 = max(0, x0 - pad)
        y0 = max(0, y0 - pad)
        x1 = min(img.width, x1 + pad)
        y1 = min(img.height, y1 + pad)

        crop = img.crop((x0, y0, x1, y1))
        crop_path = offer_dir / f"offer_{idx:04d}.png"
        crop.save(crop_path)

        # Combine text from:
        # - clusterer text block
        # - OCR pass2 (normal + inverted OCR)
        text1 = off.text_block()
        text2 = ocr_offer_pass2(crop_path)

        combined = text1.strip() + "\n" + text2.strip()
        txt_path = offer_dir / f"offer_{idx:04d}.txt"
        txt_path.write_text(combined, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", required=True, help="wegmans | shaws (we’ll add more later)")
    ap.add_argument("--pdf", required=True, help="path to PDF")
    ap.add_argument("--out", default="files_to_run/backend/_debug_offers", help="debug output folder")
    ap.add_argument("--dpi", type=int, default=350, help="render DPI (300-450 is typical)")
    args = ap.parse_args()

    brand = args.brand.strip().lower()
    knobs_all = default_store_knobs()
    if brand not in knobs_all:
        raise SystemExit(f"Unknown brand '{brand}'. Known: {', '.join(knobs_all.keys())}")

    store_knobs = knobs_all[brand]

    pdf_path = args.pdf
    debug_root = Path(args.out)
    run_dir = debug_root / f"{brand}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[render] PDF -> images @ {args.dpi} DPI")
    pages_dir = run_dir / "pages"
    page_imgs = render_pdf_to_images(pdf_path, pages_dir, dpi=args.dpi)
    print(f"[render] pages: {len(page_imgs)}")

    total_offers = 0

    for pi, img_path in enumerate(page_imgs, start=1):
        print(f"[ocr] page {pi}/{len(page_imgs)}: {img_path.name}")
        words = ocr_words_from_image(img_path)

        offers = build_offers_from_words(
            page_index=pi,
            words=words,
            store_knobs=store_knobs,
        )

        total_offers += len(offers)
        print(f"[cluster] {img_path.name} -> {len(offers)} offer blobs")

        crop_and_save_offers(img_path, offers, store_knobs, debug_dir=run_dir)

    print("\n[done]")
    print(f"  brand:        {brand}")
    print(f"  pages:        {len(page_imgs)}")
    print(f"  offer_blobs:  {total_offers}")
    print(f"  debug_dir:    {run_dir.resolve()}")


if __name__ == "__main__":
    main()
