# scripts/extract_flyer_text.py
# One command to (optionally) convert a PDF to PNGs, auto-enhance small images, OCR, log a summary,
# and (optionally) push the combined text to Supabase.
#
# Usage:
#   # PDF -> PNGs -> enhance if needed -> OCR -> logs -> (optional) Supabase
#   python .\scripts\extract_flyer_text.py --store aldi --week 102925 --pdf "C:\Users\...\aldi_102925.pdf" --dpi 350
#
#   # PNGs only (e.g., Whole Foods)
#   python .\scripts\extract_flyer_text.py --store whole_foods --week 102925
#
# Env (optional for Supabase push):
#   SUPABASE_URL=https://xxxxx.supabase.co
#   SUPABASE_SERVICE_KEY=eyJhbGciOiJI...
#   SUPABASE_TABLE=flyer_text (default if not set)

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path
import shutil
# ==== JSON PATCH (handles WindowsPath, sets, tuples) ====
import json
from pathlib import Path

class D4M_JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, (set, tuple)):
            return list(obj)
        return super().default(obj)

json.JSONEncoder = D4M_JSONEncoder
json._default_encoder = D4M_JSONEncoder()
# ========================================================

# OCR + image deps
from PIL import Image, ImageOps, ImageFilter
import pytesseract

ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

# ---------------------------
# Tesseract discovery
# ---------------------------

def ensure_tesseract() -> None:
    """Ensure pytesseract can call Tesseract, even if not on PATH."""
    import shutil as _shutil
    if _shutil.which("tesseract"):
        return
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for exe in candidates:
        if Path(exe).exists():
            pytesseract.pytesseract.tesseract_cmd = exe
            print(f"[info] Using Tesseract at: {exe}")
            return
    raise SystemExit(
        "[error] Tesseract not found.\n"
        "  Install from https://github.com/tesseract-ocr/tesseract or\n"
        r"  C:\Program Files\Tesseract-OCR\tesseract.exe, or add to PATH."
    )

# ---------------------------
# Optional PDF conversion
# ---------------------------

def convert_with_pdf2image(pdf_path: Path, out_dir: Path, dpi: int) -> int:
    from pdf2image import convert_from_path
    pages = convert_from_path(str(pdf_path), dpi=dpi)  # Poppler if available
    n = 0
    for i, page in enumerate(pages, 1):
        out = out_dir / f"img{i:02d}.png"
        page.save(out, "PNG")
        print(f"[OK] {out.name}")
        n += 1
    return n

def convert_with_pymupdf(pdf_path: Path, out_dir: Path, dpi: int) -> int:
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

def maybe_convert_pdf(pdf: Path | None, out_dir: Path, dpi: int) -> int:
    if not pdf:
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[convert] {pdf.name} @ {dpi} DPI → {out_dir}")
    try:
        import pdf2image  # noqa
        n = convert_with_pdf2image(pdf, out_dir, dpi)
        print(f"[done] {n} page(s) saved with pdf2image.")
        return n
    except Exception as e:
        print(f"[warn] pdf2image failed ({e}). Trying PyMuPDF fallback...")

    try:
        import fitz  # noqa
        n = convert_with_pymupdf(pdf, out_dir, dpi)
        print(f"[done] {n} page(s) saved with PyMuPDF.")
        return n
    except Exception as e2:
        print("[error] Both converters failed.")
        raise SystemExit(e2)

# ---------------------------
# Enhancement for small images
# ---------------------------

def upscale_and_enhance(src: Path, dst: Path, min_w=1500, min_h=1800, max_scale=3.0):
    img = Image.open(src).convert("RGB")
    w, h = img.size
    scale = max(min_w / w, min_h / h, 1.0)
    scale = min(scale, max_scale)
    if scale > 1.01:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    # light cleanup for OCR
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    sharp = gray.filter(ImageFilter.UnsharpMask(radius=1.2, percent=150, threshold=3))
    sharp.save(dst)

def prepare_images(raw_dir: Path, hd_dir: Path, min_w: int, min_h: int) -> dict:
    """
    Copy or upscale/enhance images from raw_dir -> hd_dir.
    Returns dict with counts and a list of processed file paths.
    """
    hd_dir.mkdir(parents=True, exist_ok=True)
    imgs = sorted([p for p in raw_dir.iterdir() if p.suffix.lower() in ALLOWED])
    result = {"total": len(imgs), "enhanced": 0, "kept": 0, "processed": []}
    for i, p in enumerate(imgs, 1):
        out = hd_dir / f"img{i:02d}.png"
        w, h = Image.open(p).size
        if w < min_w or h < min_h:
            upscale_and_enhance(p, out, min_w=min_w, min_h=min_h)
            result["enhanced"] += 1
            print(f"[prep] {p.name} -> {out.name} (upscaled/enhanced from {w}x{h})")
        else:
            shutil.copy2(p, out)
            result["kept"] += 1
            print(f"[prep] {p.name} -> {out.name} (kept: {w}x{h})")
        result["processed"].append(out)
    return result

# ---------------------------
# OCR
# ---------------------------

def ocr_images(img_paths: list[Path], ocr_dir: Path) -> dict:
    ensure_tesseract()
    ocr_dir.mkdir(parents=True, exist_ok=True)
    page_chars = []
    for i, p in enumerate(img_paths, 1):
        text = pytesseract.image_to_string(Image.open(p))
        (ocr_dir / f"page{i:02d}.txt").write_text(text, encoding="utf-8")
        print(f"[OK] {p.name} -> page{i:02d}.txt ({len(text)} chars)")
        page_chars.append(len(text))

    combined = "\n\n".join((ocr_dir / f"page{i:02d}.txt").read_text(encoding="utf-8")
                           for i in range(1, len(img_paths) + 1))
    (ocr_dir / "full_text.txt").write_text(combined, encoding="utf-8")
    return {"pages": len(img_paths), "chars_total": len(combined), "page_chars": page_chars}

# ---------------------------
# Logging (JSON per run + rolling CSV)
# ---------------------------

def write_logs(root: Path, store: str, week: str, summary: dict) -> None:
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = logs / f"extract_{store}_{week}_{ts}.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[log] {json_path}")

    # rolling CSV: append one row per run
    csv_path = logs / "extract_summary.csv"
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp", "store", "week",
                "pages", "chars_total",
                "images_total", "images_enhanced", "images_kept",
                "pdf_pages_saved", "dpi", "min_w", "min_h"
            ],
        )
        if write_header:
            w.writeheader()
        w.writerow({
            "timestamp": ts,
            "store": store,
            "week": week,
            "pages": summary["ocr"]["pages"],
            "chars_total": summary["ocr"]["chars_total"],
            "images_total": summary["prep"]["total"],
            "images_enhanced": summary["prep"]["enhanced"],
            "images_kept": summary["prep"]["kept"],
            "pdf_pages_saved": summary["pdf"]["pages_saved"],
            "dpi": summary["pdf"]["dpi"],
            "min_w": summary["prep"]["min_w"],
            "min_h": summary["prep"]["min_h"],
        })
    print(f"[log] {csv_path}")

# ---------------------------
# Optional Supabase push
# ---------------------------

def maybe_push_supabase(base: Path, store: str, week: str) -> None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    table = os.getenv("SUPABASE_TABLE", "flyer_text")
    if not (url and key):
        print("[info] Supabase env vars not set; skipping push.")
        return

    full_text = (base / "ocr_txt" / "full_text.txt").read_text(encoding="utf-8")

    payload = {
        "store": store,
        "week": week,
        "full_text": full_text,
        "char_count": len(full_text),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    try:
        import requests
        res = requests.post(
            f"{url}/rest/v1/{table}",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=payload,
            timeout=30,
        )
        if res.status_code >= 300:
            print(f"[warn] Supabase push failed: {res.status_code} {res.text}")
        else:
            print("[done] Supabase push OK.")
    except Exception as e:
        print(f"[warn] Supabase push error: {e}")

# ---------------------------
# CLI
# ---------------------------

def main():
    ap = argparse.ArgumentParser(
        description="PDF->PNG (optional), auto-enhance, OCR, log, and (optional) Supabase push."
    )
    ap.add_argument("--store", required=True)
    ap.add_argument("--week", required=True)
    ap.add_argument("--root", default="flyers")
    ap.add_argument("--pdf", default=None, help="Optional path to a flyer PDF")
    ap.add_argument("--dpi", type=int, default=350, help="PDF render DPI if converting")
    ap.add_argument("--min_w", type=int, default=1500, help="Min width before upscaling")
    ap.add_argument("--min_h", type=int, default=1800, help="Min height before upscaling")
    args = ap.parse_args()

    base = Path(args.root) / args.store / args.week
    raw = base / "raw_images"
    hd  = base / "raw_images_hd"
    ocr = base / "ocr_txt"
    base.mkdir(parents=True, exist_ok=True)

    pdf_path = Path(args.pdf) if args.pdf else None
    if pdf_path and not pdf_path.exists():
        raise SystemExit(f"[error] PDF not found: {pdf_path}")

    # 1) PDF -> PNGs (if given)
    pages_saved = maybe_convert_pdf(pdf_path, raw, args.dpi)

    # 2) Prep images (upscale/enhance if below threshold)
    prep_info = prepare_images(raw, hd, args.min_w, args.min_h)
    prep_info["min_w"] = args.min_w
    prep_info["min_h"] = args.min_h

    # 3) OCR
    processed_imgs = sorted(hd.iterdir())
    ocr_info = ocr_images(processed_imgs, ocr)

    # Summary + logs
    summary = {
        "store": args.store,
        "week": args.week,
        "pdf": {"pages_saved": pages_saved, "dpi": args.dpi},
        "prep": prep_info,
        "ocr": ocr_info,
        "paths": {
            "base": str(base),
            "raw": str(raw),
            "raw_hd": str(hd),
            "ocr_txt": str(ocr),
        },
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    write_logs(Path(args.root), args.store, args.week, summary)

    # 4) Optional Supabase push
    maybe_push_supabase(base, args.store, args.week)

    print("[done] All steps complete.")

if __name__ == "__main__":
    main()
# ==== DEALS-4ME PATCH (drop-in, safe to paste at end of file) =================
# Fix JSON serialization for Paths in write_logs + friendlier missing-folder error
# for prepare_images. No other code changes required.

import json
from pathlib import Path

def _to_jsonable(obj):
    """Recursively convert objects (Path, set, tuple, etc.) to JSON-safe types."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (set, tuple, list)):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj  # ints, floats, str, bool, None, already OK

# --- Override write_logs so it never crashes on Path serialization -------------
# We keep the signature used by your main():
#   write_logs(Path(args.root), args.store, args.week, summary)
def write_logs(root, store, week, summary):
    try:
        out_dir = Path(root) / "logs" / str(store) / str(week)
        out_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "store": str(store),
            "week": str(week),
            "root": str(root),
            "summary": _to_jsonable(summary),
        }

        with (out_dir / "summary.json").open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as e:
        # Fail-soft: write a tiny plaintext note if JSON writing somehow fails
        try:
            with (out_dir / "summary_fallback.txt").open("w", encoding="utf-8") as f:
                f.write(f"write_logs failed: {e}\n")
                f.write(f"store={store}, week={week}, root={root}\n")
                f.write(f"summary keys: {list(summary.keys()) if hasattr(summary, 'keys') else type(summary)}\n")
        except Exception:
            pass
        raise

# --- Wrap prepare_images to produce a clearer error if raw_images is missing ---
# Only do this if a prepare_images already exists in the module.
_orig_prepare_images = globals().get("prepare_images", None)

if _orig_prepare_images is not None:
    def _prepare_images_wrapper(raw_dir, *args, **kwargs):
        raw_dir = Path(raw_dir)
        if not raw_dir.exists():
            # Match the path style your error showed and explain what to do.
            raise FileNotFoundError(
                f"Expected raw images at:\n  {raw_dir}\n\n"
                "Create this folder and put flyer images there first, "
                "or run a store/week that actually exists.\n"
                "Tip: path layout should be .../flyers/<store>/<week>/raw_images/"
            )
        return _orig_prepare_images(str(raw_dir), *args, **kwargs)

    # Monkey-patch the original
    globals()["prepare_images"] = _prepare_images_wrapper

# ==== END PATCH ================================================================
# ==== UNIVERSAL JSON PATCH (handles Path, set) ====
import json
from pathlib import Path

# Keep the original JSONEncoder.default so we can fall back to it
__D4M__orig_default = json.JSONEncoder.default

def __D4M__json_default(self, obj):
    # Convert pathlib.Path to string
    if isinstance(obj, Path):
        return str(obj)
    # Convert sets to lists (JSON has no set type)
    if isinstance(obj, set):
        return list(obj)
    # Fallback to the original behavior; if it still fails, coerce to str
    try:
        return __D4M__orig_default(self, obj)
    except TypeError:
        return str(obj)

# Monkey-patch the encoder so ANY json.dumps/json.dump call in this module works
json.JSONEncoder.default = __D4M__json_default
# ==== END PATCH ====
