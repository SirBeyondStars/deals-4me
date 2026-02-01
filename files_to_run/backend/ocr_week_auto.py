from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
DEFAULT_LANG = "eng"


def project_root() -> Path:
    # <project_root>/files_to_run/backend/ocr_week_auto.py
    return Path(__file__).resolve().parents[2]


def flyers_region_root(region: str) -> Path:
    return project_root() / "flyers" / region


def week_dir(region: str, store_slug: str, week_code: str) -> Path:
    return flyers_region_root(region) / store_slug / week_code


def find_pdftoppm() -> Optional[str]:
    """
    Find Poppler's pdftoppm.exe.
    1) If it's on PATH, use that.
    2) Else try your known location.
    """
    exe = shutil.which("pdftoppm")
    if exe:
        return exe

    # Your confirmed location:
    candidate = r"C:\Users\jwein\OneDrive\Desktop\bin\pdftoppm.exe"
    if Path(candidate).exists():
        return candidate

    return None


def dir_has_images(d: Path) -> bool:
    if not d.exists():
        return False
    for p in d.iterdir():
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            return True
    return False


def dir_has_pdfs(d: Path) -> bool:
    if not d.exists():
        return False
    for p in d.iterdir():
        if p.is_file() and p.suffix.lower() == ".pdf":
            return True
    return False


def convert_pdfs_to_png(raw_pdf: Path, tmp_png: Path) -> None:
    """
    Convert all PDFs in raw_pdf into PNGs inside tmp_png using pdftoppm.
    """
    pdftoppm = find_pdftoppm()
    if not pdftoppm:
        raise RuntimeError(
            "Poppler not found: pdftoppm.exe is required to convert PDFs. "
            "Add it to PATH or place it at C:\\Users\\jwein\\OneDrive\\Desktop\\bin\\pdftoppm.exe"
        )

    tmp_png.mkdir(parents=True, exist_ok=True)

    pdfs = sorted([p for p in raw_pdf.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"])
    if not pdfs:
        return

    for pdf in pdfs:
        # Output prefix: tmp_png/<pdf_stem>_p001.png etc.
        out_prefix = tmp_png / pdf.stem

        cmd = [
            pdftoppm,
            "-png",
            str(pdf),
            str(out_prefix),
        ]
        print("[AUTO] PDF->PNG:", " ".join(f'"{c}"' if " " in c else c for c in cmd))
        # check=True will raise if conversion fails
        subprocess.run(cmd, check=True, cwd=str(project_root()))


def choose_input_dir_and_prepare(wk: Path) -> Tuple[Path, Optional[Path]]:
    """
    Returns:
      (in_dir, tmp_dir_used)
    - If raw_png has images, use it.
    - Else if raw_pdf has pdfs, convert to tmp and use tmp.
    - Else fall back to raw_png/raw_pdf/wk for clearer errors.
    """
    raw_png = wk / "raw_png"
    raw_pdf = wk / "raw_pdf"

    if dir_has_images(raw_png):
        return raw_png, None

    if dir_has_pdfs(raw_pdf):
        tmp_png = wk / "tmp" / "pdf_png_auto"
        convert_pdfs_to_png(raw_pdf, tmp_png)
        return tmp_png, tmp_png

    # Nothing obvious; return something sensible for the downstream warning messages
    if raw_png.exists():
        return raw_png, None
    if raw_pdf.exists():
        return raw_pdf, None
    return wk, None


def ensure_output_dir(wk: Path) -> Path:
    # Put OCR text outputs under: <week_dir>/ocr_text_auto/
    out_dir = wk / "ocr_text_auto"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def run(cmd: List[str]) -> int:
    print("[AUTO] RUN:", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    return subprocess.call(cmd, cwd=str(project_root()))


def main() -> int:
    ap = argparse.ArgumentParser(prog="ocr_week_auto.py")
    ap.add_argument("store", help="store slug, e.g. whole_foods")
    ap.add_argument("--week", required=True, help="wk_YYYYMMDD (preferred) or weekNN")
    ap.add_argument("--region", required=True, help="NE, MIDATL, etc.")
    ap.add_argument("--lang", default=DEFAULT_LANG, help="Tesseract language, default eng")
    ap.add_argument("--psm", default=None, help="optional psm (passes through)")
    ap.add_argument("--oem", default=None, help="optional oem (passes through)")
    ap.add_argument("--force", action="store_true", help="force overwrite / re-run (passes through)")
    args = ap.parse_args()

    wk = week_dir(args.region, args.store, args.week)
    if not wk.exists():
        print(f"[FATAL] Week folder not found: {wk}")
        return 2

    in_dir, tmp_used = choose_input_dir_and_prepare(wk)
    out_dir = ensure_output_dir(wk)

    tool = project_root() / "files_to_run" / "backend" / "ocr_images_to_text.py"
    if not tool.exists():
        print(f"[FATAL] Missing tool: {tool}")
        return 2

    cmd = [
        sys.executable,
        str(tool),
        "--in-dir", str(in_dir),
        "--out-dir", str(out_dir),
        "--lang", args.lang,
    ]
    if args.psm is not None:
        cmd += ["--psm", str(args.psm)]
    if args.oem is not None:
        cmd += ["--oem", str(args.oem)]
    if args.force:
        cmd += ["--force"]

    rc = run(cmd)

    # Helpful info if we used a temp folder
    if tmp_used is not None and tmp_used.exists():
        # If conversion produced nothing, say it clearly
        pngs = list(tmp_used.rglob("*.png"))
        if not pngs:
            print(f"[WARN] PDF->PNG produced no PNGs in: {tmp_used}")

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
