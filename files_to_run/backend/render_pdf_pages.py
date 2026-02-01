# deals-4me/files_to_run/backend/render_pdf_pages.py
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class RenderManifest:
    store_slug: str
    week: str
    region: str
    repo_root: str
    week_dir: Optional[str]
    pdfs_found: List[str]
    pages_out_dir: Optional[str]
    pages_written: int
    notes: List[str]


def repo_root_from_this_file() -> Path:
    """
    Walk upward from this script until we find a folder containing 'flyers'.
    Prevents accidentally using Desktop/ as repo_root.
    """
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "flyers").exists():
            return parent
    return p.parents[3]


def find_week_dir(repo_root: Path, region: str, store_slug: str, week: str) -> Optional[Path]:
    week_dir = repo_root / "flyers" / region / store_slug / week
    if week_dir.exists() and week_dir.is_dir():
        return week_dir
    return None


def find_pdfs(raw_pdf_dir: Path) -> List[Path]:
    pdfs = [p for p in raw_pdf_dir.glob("*.pdf") if p.is_file()]
    return sorted(pdfs, key=lambda p: p.name.lower())


def ensure_clean_dir(d: Path, clean: bool) -> None:
    d.mkdir(parents=True, exist_ok=True)
    if clean:
        for p in d.glob("*.png"):
            p.unlink(missing_ok=True)


def render_with_pdftoppm(pdf_path: Path, out_dir: Path, dpi: int) -> List[Path]:
    """
    Uses Poppler's pdftoppm to render pages as PNG.
    Output format: <stem>_p0001.png, <stem>_p0002.png, ...
    """
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("pdftoppm not found. Install Poppler and ensure pdftoppm is on PATH.")

    prefix = out_dir / f"{pdf_path.stem}_p"
    cmd = [
        pdftoppm,
        "-png",
        "-r",
        str(dpi),
        str(pdf_path),
        str(prefix),
    ]
    subprocess.run(cmd, check=True)

    # pdftoppm creates files like: <stem>_p-1.png, <stem>_p-2.png ... depending on version
    # Also sometimes: <stem>_p-01.png. We’ll just glob by stem.
    created = sorted(out_dir.glob(f"{pdf_path.stem}_p*.png"), key=lambda p: p.name.lower())
    return created


def main() -> int:
    ap = argparse.ArgumentParser(description="Render flyer PDFs into page PNGs (for slicing).")
    ap.add_argument("store_slug", help="e.g. shaws, stop_and_shop_ct")
    ap.add_argument("--week", required=True, help="e.g. wk_20251221")
    ap.add_argument("--region", default="NE", help="e.g. NE (default: NE)")
    ap.add_argument("--repo_root", default="", help="Optional path to deals-4me root. Default: auto-detect.")
    ap.add_argument("--dpi", type=int, default=220, help="Render DPI (default: 220)")
    ap.add_argument("--clean", action="store_true", help="Delete existing processed/pages/*.png first.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_this_file()
    notes: List[str] = [f"repo_root={repo_root}"]

    week_dir = find_week_dir(repo_root, args.region, args.store_slug, args.week)
    if not week_dir:
        manifest = RenderManifest(
            store_slug=args.store_slug,
            week=args.week,
            region=args.region,
            repo_root=str(repo_root),
            week_dir=None,
            pdfs_found=[],
            pages_out_dir=None,
            pages_written=0,
            notes=notes + ["ERROR: Could not find week directory flyers/<region>/<store>/<week>."],
        )
        print(json.dumps(manifest.__dict__, indent=2))
        return 2

    raw_pdf_dir = week_dir / "raw_pdf"
    if not raw_pdf_dir.exists():
        manifest = RenderManifest(
            store_slug=args.store_slug,
            week=args.week,
            region=args.region,
            repo_root=str(repo_root),
            week_dir=str(week_dir),
            pdfs_found=[],
            pages_out_dir=None,
            pages_written=0,
            notes=notes + [f"ERROR: Missing raw_pdf folder: {raw_pdf_dir}"],
        )
        print(json.dumps(manifest.__dict__, indent=2))
        return 2

    pdfs = find_pdfs(raw_pdf_dir)
    pages_out_dir = week_dir / "processed" / "pages"
    ensure_clean_dir(pages_out_dir, clean=args.clean)

    total_pages = 0
    for pdf in pdfs:
        created = render_with_pdftoppm(pdf, pages_out_dir, dpi=args.dpi)
        total_pages += len(created)

    manifest = RenderManifest(
        store_slug=args.store_slug,
        week=args.week,
        region=args.region,
        repo_root=str(repo_root),
        week_dir=str(week_dir),
        pdfs_found=[str(p) for p in pdfs],
        pages_out_dir=str(pages_out_dir),
        pages_written=total_pages,
        notes=notes + [f"pdfs={len(pdfs)}", f"pages_written={total_pages}", f"dpi={args.dpi}"],
    )

    manifest_path = week_dir / "processed" / "page_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest.__dict__, indent=2), encoding="utf-8")

    print(f"\nRendered {total_pages} page PNG(s) to:\n  {pages_out_dir}")
    print(f"Manifest written to:\n  {manifest_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
