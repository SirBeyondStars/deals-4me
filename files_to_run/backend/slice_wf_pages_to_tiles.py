# deals-4me/files_to_run/backend/slice_wf_pages_to_tiles.py
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image


# -----------------------
# Data models
# -----------------------

@dataclass
class LocatedPages:
    store_slug: str
    week: str
    week_dir: Optional[str]
    page_pngs: List[str]
    notes: List[str]


@dataclass
class TileMeta:
    offer_id: int
    src_page: str
    page_index: int
    column_index: int
    bbox: Tuple[int, int, int, int]  # left, top, right, bottom
    out_png: str


# -----------------------
# Repo + folder resolution (STRICT)
# -----------------------

def repo_root_from_this_file() -> Path:
    """
    Walk upward from this script until we find a folder containing 'flyers'.
    This avoids the 'repo_root=C:\\Users\\...\\Desktop' mistake.
    """
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "flyers").exists():
            return parent
    # Fallback: deals-4me/files_to_run/backend/script.py -> parents[3] is usually deals-4me
    return p.parents[3]


def find_week_dir(repo_root: Path, store_slug: str, week: str) -> Optional[Path]:
    """
    STRICT (for now): flyers/NE/<store_slug>/<week>
    No guessing, no fallback into other stores.
    """
    week_dir = repo_root / "flyers" / "NE" / store_slug / week
    if week_dir.exists() and week_dir.is_dir():
        return week_dir
    return None


# -----------------------
# Page PNG discovery (PNG-only)
# -----------------------

def _natural_png_sort_key(p: Path) -> Tuple[int, str]:
    """
    Sort files like 1.png, 2.png, 10.png naturally.
    """
    m = re.match(r"^(\d+)\.png$", p.name, re.IGNORECASE)
    if m:
        return (int(m.group(1)), p.name.lower())
    # fallback: try to extract any number
    m2 = re.search(r"(\d+)", p.stem)
    if m2:
        return (int(m2.group(1)), p.name.lower())
    return (10**9, p.name.lower())


def locate_page_pngs(week_dir: Path) -> List[Path]:
    """
    Prefer raw_png. Only returns *.png files.
    """
    likely_dirs = [
        week_dir / "raw_png",
        week_dir / "processed" / "pages",
        week_dir / "processed" / "page_pngs",
        week_dir / "pages",
        week_dir / "raw_images",
        week_dir / "raw_imgs",
    ]

    for d in likely_dirs:
        if d.exists() and d.is_dir():
            pngs = [p for p in d.glob("*.png") if p.is_file()]
            if pngs:
                return sorted(pngs, key=_natural_png_sort_key)

    # Fallback: scan week_dir for any png (excluding our output folders)
    all_pngs: List[Path] = []
    for p in week_dir.rglob("*.png"):
        s = p.as_posix().lower()
        if "/processed/slices_auto/" in s or "/processed/slices_" in s or "/processed/tiles" in s:
            continue
        all_pngs.append(p)

    return sorted(all_pngs, key=_natural_png_sort_key)


def write_page_manifest(week_dir: Path, payload: LocatedPages) -> Path:
    processed_dir = week_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / "page_manifest.json"
    out_path.write_text(json.dumps(payload.__dict__, indent=2), encoding="utf-8")
    return out_path


# -----------------------
# Image utility helpers
# -----------------------

def _img_to_gray(img: Image.Image) -> Image.Image:
    return img.convert("L")


def _row_ink_profile(gray: Image.Image, dark_thresh: int) -> List[float]:
    """
    For each row, compute fraction of pixels considered 'ink' (dark).
    """
    w, h = gray.size
    px = gray.load()
    prof: List[float] = []
    for y in range(h):
        dark = 0
        for x in range(w):
            if px[x, y] < dark_thresh:
                dark += 1
        prof.append(dark / float(w))
    return prof


def _col_ink_profile(gray: Image.Image, dark_thresh: int) -> List[float]:
    """
    For each column, compute fraction of pixels considered 'ink' (dark).
    """
    w, h = gray.size
    px = gray.load()
    prof: List[float] = []
    for x in range(w):
        dark = 0
        for y in range(h):
            if px[x, y] < dark_thresh:
                dark += 1
        prof.append(dark / float(h))
    return prof


def _smooth_1d(vals: List[float], radius: int) -> List[float]:
    if radius <= 0:
        return vals[:]
    n = len(vals)
    out = [0.0] * n
    for i in range(n):
        lo = max(0, i - radius)
        hi = min(n, i + radius + 1)
        out[i] = sum(vals[lo:hi]) / float(hi - lo)
    return out


def _find_runs_below(vals: List[float], thresh: float, min_len: int) -> List[Tuple[int, int]]:
    """
    Return [(start, end)] inclusive runs where vals[i] <= thresh and run length >= min_len.
    """
    runs: List[Tuple[int, int]] = []
    n = len(vals)
    i = 0
    while i < n:
        if vals[i] <= thresh:
            j = i
            while j < n and vals[j] <= thresh:
                j += 1
            if (j - i) >= min_len:
                runs.append((i, j - 1))
            i = j
        else:
            i += 1
    return runs


# -----------------------
# Slicing logic (WF-tuned)
# -----------------------

def _split_into_columns(img: Image.Image) -> List[Tuple[int, int]]:
    """
    WF pages are often multi-card grids. For now we treat the full width as one column.
    We keep this hook if you later want a 2-column mode for other layouts.
    """
    w, _ = img.size
    return [(0, w)]


def _slice_column_into_bands(
    col_img: Image.Image,
    dark_thresh: int,
    y_top_trim: int,
    y_bottom_trim: int,
    low_row_ink_thresh: float,
    min_blank_run_px: int,
    min_band_h: int,
    max_band_h: int,
) -> List[Tuple[int, int]]:
    """
    Slice a column into horizontal bands using whitespace separators.
    Returns [(y0, y1)] in column coordinates.
    """
    gray = _img_to_gray(col_img)
    w, h = gray.size

    y0 = max(0, y_top_trim)
    y1 = max(y0 + 1, h - y_bottom_trim)
    if y1 <= y0 + 10:
        y0, y1 = 0, h

    cropped = gray.crop((0, y0, w, y1))
    prof = _row_ink_profile(cropped, dark_thresh=dark_thresh)
    prof = _smooth_1d(prof, radius=4)

    blank_runs = _find_runs_below(prof, thresh=low_row_ink_thresh, min_len=min_blank_run_px)

    cut_lines: List[int] = [0]
    for a, b in blank_runs:
        cut_lines.append((a + b) // 2)
    cut_lines.append(len(prof))

    cut_lines = sorted(set(cut_lines))

    segments: List[Tuple[int, int]] = []
    for i in range(len(cut_lines) - 1):
        a = cut_lines[i]
        b = cut_lines[i + 1]
        if b <= a:
            continue
        seg_h = b - a
        if seg_h < min_band_h:
            continue
        segments.append((a, b))

    # Clamp overly tall bands by splitting
    final: List[Tuple[int, int]] = []
    for a, b in segments:
        seg_h = b - a
        if seg_h <= max_band_h:
            final.append((a, b))
        else:
            cur = a
            while cur < b:
                nxt = min(b, cur + max_band_h)
                if (nxt - cur) >= min_band_h:
                    final.append((cur, nxt))
                cur = nxt

    # Map back to original column coords
    return [(a + y0, b + y0) for (a, b) in final]


def _split_band_into_cards(
    band_img: Image.Image,
    dark_thresh: int,
    low_col_ink_thresh: float,
    min_gutter_px: int,
    min_card_w: int,
) -> List[Tuple[int, int]]:
    """
    Split a horizontal band into left-to-right cards using vertical whitespace gutters.
    Returns [(x0, x1)] in band coordinates.
    """
    gray = _img_to_gray(band_img)
    w, h = gray.size

    col_prof = _col_ink_profile(gray, dark_thresh=dark_thresh)
    col_prof = _smooth_1d(col_prof, radius=5)

    gutters = _find_runs_below(col_prof, thresh=low_col_ink_thresh, min_len=min_gutter_px)

    cuts = [0]
    for a, b in gutters:
        cuts.append((a + b) // 2)
    cuts.append(w)

    cuts = sorted(set(cuts))

    segments: List[Tuple[int, int]] = []
    for i in range(len(cuts) - 1):
        x0 = cuts[i]
        x1 = cuts[i + 1]
        if x1 <= x0:
            continue
        if (x1 - x0) < min_card_w:
            continue
        segments.append((x0, x1))

    if not segments:
        return [(0, w)]

    return segments


def slice_wf_pages_to_tiles(
    page_paths: List[Path],
    out_dir: Path,
    clean: bool,
) -> List[TileMeta]:
    """
    WF-tuned slicing:
    - treat page as one column
    - slice into horizontal bands (rows of cards)
    - split each band into left-to-right cards
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    if clean:
        for p in out_dir.glob("offer_*.png"):
            p.unlink(missing_ok=True)

    # Tunables (WF defaults)
    dark_thresh = 200

    # Horizontal banding
    y_top_trim = 120
    y_bottom_trim = 60
    low_row_ink_thresh = 0.015     # more willing to consider whitespace
    min_blank_run_px = 12          # thinner separators count
    min_band_h = 180
    max_band_h = 520

    # Vertical card splitting (within each band)
    low_col_ink_thresh = 0.008
    min_gutter_px = 18
    min_card_w = 260

    pad_x = 10
    pad_y = 8

    tiles: List[TileMeta] = []
    offer_id = 1

    for page_index, page_path in enumerate(page_paths, start=1):
        img = Image.open(page_path).convert("RGB")
        w, h = img.size

        cols = _split_into_columns(img)

        for col_index, (x0, x1) in enumerate(cols, start=1):
            col_img = img.crop((x0, 0, x1, h))

            bands = _slice_column_into_bands(
                col_img=col_img,
                dark_thresh=dark_thresh,
                y_top_trim=y_top_trim,
                y_bottom_trim=y_bottom_trim,
                low_row_ink_thresh=low_row_ink_thresh,
                min_blank_run_px=min_blank_run_px,
                min_band_h=min_band_h,
                max_band_h=max_band_h,
            )

            for (by0, by1) in bands:
                # Crop the band from the full page (not just the column crop)
                band = img.crop((x0, by0, x1, by1))

                card_ranges = _split_band_into_cards(
                    band_img=band,
                    dark_thresh=dark_thresh,
                    low_col_ink_thresh=low_col_ink_thresh,
                    min_gutter_px=min_gutter_px,
                    min_card_w=min_card_w,
                )

                for (cx0, cx1) in card_ranges:
                    tx0 = x0 + cx0
                    tx1 = x0 + cx1
                    ty0 = by0
                    ty1 = by1

                    tx0 = max(0, tx0 - pad_x)
                    tx1 = min(w, tx1 + pad_x)
                    ty0 = max(0, ty0 - pad_y)
                    ty1 = min(h, ty1 + pad_y)

                    tile = img.crop((tx0, ty0, tx1, ty1))

                    out_png = out_dir / f"offer_{offer_id:04d}.png"
                    tile.save(out_png)

                    tiles.append(
                        TileMeta(
                            offer_id=offer_id,
                            src_page=str(page_path),
                            page_index=page_index,
                            column_index=col_index,
                            bbox=(tx0, ty0, tx1, ty1),
                            out_png=str(out_png),
                        )
                    )
                    offer_id += 1

    return tiles


# -----------------------
# CLI / main
# -----------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Step 1: locate WF page PNGs. Step 2 (WF): slice into offer tiles with --slice."
    )
    ap.add_argument("store_slug", help="e.g. whole_foods")
    ap.add_argument("--week", required=True, help="e.g. wk_20251221")
    ap.add_argument(
        "--repo_root",
        default="",
        help="Optional path to deals-4me root. If omitted, we auto-detect by finding a folder containing 'flyers/'.",
    )
    ap.add_argument("--slice", action="store_true", help="Slice page PNGs into tiles.")
    ap.add_argument("--clean", action="store_true", help="Remove prior offer_*.png in output folder first.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_this_file()

    notes: List[str] = [f"repo_root={repo_root}"]
    week_dir = find_week_dir(repo_root, args.store_slug, args.week)

    if not week_dir:
        payload = LocatedPages(
            store_slug=args.store_slug,
            week=args.week,
            week_dir=None,
            page_pngs=[],
            notes=notes + ["ERROR: Could not find week directory for this store/week."],
        )
        print(json.dumps(payload.__dict__, indent=2))
        return 2

    page_pngs = locate_page_pngs(week_dir)

    payload = LocatedPages(
        store_slug=args.store_slug,
        week=args.week,
        week_dir=str(week_dir),
        page_pngs=[str(p) for p in page_pngs],
        notes=notes + [f"found_pages={len(page_pngs)}"],
    )

    manifest_path = write_page_manifest(week_dir, payload)

    print(f"\nFOUND {len(page_pngs)} PAGE PNG(S):")
    for p in page_pngs:
        print(f"  {p}")
    print(f"\nManifest written to:\n  {manifest_path}\n")

    if not args.slice:
        return 0

    out_dir = week_dir / "processed" / "slices_auto"
    tiles = slice_wf_pages_to_tiles(
        page_paths=[Path(p) for p in payload.page_pngs],
        out_dir=out_dir,
        clean=args.clean,
    )

    meta_path = out_dir / "tiles_meta.json"
    meta_path.write_text(json.dumps([t.__dict__ for t in tiles], indent=2), encoding="utf-8")

    print(f"\nSLICED {len(tiles)} TILE(S) to:\n  {out_dir}")
    print(f"Tile meta written to:\n  {meta_path}\n")

    for t in tiles[:10]:
        print(f"  offer_{t.offer_id:04d}  page={t.page_index} col={t.column_index} bbox={t.bbox}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
