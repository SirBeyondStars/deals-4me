# scripts/pdf_to_png.py
# Convert a flyer PDF into high-res PNGs.
# Tries pdf2image+poppler (fast) and falls back to PyMuPDF (no PATH needed).

import argparse
from pathlib import Path

def convert_with_pdf2image(pdf_path, out_dir, dpi):
    from pdf2image import convert_from_path
    pages = convert_from_path(str(pdf_path), dpi=dpi)  # uses poppler in PATH
    for i, page in enumerate(pages, 1):
        out = out_dir / f"img{i:02d}.png"
        page.save(out, "PNG")
        print(f"[OK] {out.name}")
    return len(pages)

def convert_with_pymupdf(pdf_path, out_dir, dpi):
    import fitz  # PyMuPDF
    doc = fitz.open(str(pdf_path))
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    n = 0
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=mat, alpha=False)
        out = out_dir / f"img{i:02d}.png"
        pix.save(out)
        print(f"[OK] {out.name} ({pix.width}x{pix.height})")
        n += 1
    doc.close()
    return n

def main():
    ap = argparse.ArgumentParser(description="Convert PDF pages to high-res PNGs.")
    ap.add_argument("--pdf", required=True, help="Path to flyer PDF")
    ap.add_argument("--out", required=True, help="Output folder for PNGs")
    ap.add_argument("--dpi", type=int, default=350, help="Render DPI (300–400 recommended)")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[info] Converting {pdf_path.name} at {args.dpi} DPI → {out_dir}")
    try:
        import pdf2image  # noqa
        n = convert_with_pdf2image(pdf_path, out_dir, args.dpi)
        print(f"[done] {n} page(s) saved with pdf2image.")
        return
    except Exception as e:
        print(f"[warn] pdf2image failed ({e}). Trying PyMuPDF fallback...")

    try:
        import fitz  # noqa
        n = convert_with_pymupdf(pdf_path, out_dir, args.dpi)
        print(f"[done] {n} page(s) saved with PyMuPDF.")
    except Exception as e:
        print(f"[error] Both converters failed.")
        print(f"        {e}")
        raise SystemExit(1)

if __name__ == "__main__":
    main()
