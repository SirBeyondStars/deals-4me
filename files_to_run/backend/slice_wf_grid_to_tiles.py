# site/files_to_run/backend/slice_wf_grid_to_tiles.py
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image  # type: ignore


# -----------------------------
# Models
# -----------------------------

@dataclass
class TileMeta:
    offer_id: str
    page: int
    row: int
    col: int
    bbox: Tuple[int, int, int, int]   # (x1,y1,x2,y2)
    src_page_png: str
    out_png: str


# -----------------------------
# Paths / discovery
# -----------------------------

def find_repo_root(start: Path) -> Path:
    """
    Walk upward until we find 'flyers' folder.
    """
    cur = start.resolve()
    for _ in range(8):
        if (cur / "flyers").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    # fallback: current working directory
    return Path.cwd().resolve()


def week_dir(repo_root: Path, region: str, store_slug: str, week: str) -> Path:
    return repo_root / "flyers" / region / store_slug / week


def find_page_pngs(week_path: Path) -> List[Path]:
    raw_png = week_path / "raw_png"
    if not raw_png.exists():
        return []
    # numeric filenames like 1.png, 2.png, ... 125.png
    pngs = list(raw_png.glob("*.png"))
    def key(p: Path) -> Tuple[int, str]:
        stem = p.stem
        try:
            return (int(stem), p.name)
        except Exception:
            return (999999, p.name)
    return sorted(pngs, key=key)


# -----------------------------
# Image heuristics
# -----------------------------

def is_tile_mostly_blank(img: Image.Image, *, white_thresh: int = 245, max_nonwhite_pct: float = 0.02) -> bool:
    """
    Fast "blank tile" test.
    - Convert to grayscale
    - Downsample
    - Count pixels that are not near-white
    If the non-white fraction is tiny -> blank.
    """
    g = img.convert("L")
    # Downsample hard to speed up
    g = g.resize((160, 160))
    px = g.getdata()
    total = 160 * 160
    nonwhite = 0
    for v in px:
        if v < white_thresh:
            nonwhite += 1
    frac = nonwhite / total
    return frac <= max_nonwhite_pct


def safe_crop(img: Image.Image, bbox: Tuple[int, int, int, int]) -> Image.Image:
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(img.width, x2); y2 = min(img.height, y2)
    return img.crop((x1, y1, x2, y2))


# -----------------------------
# Grid slicing
# -----------------------------

def compute_grid_boxes(
    w: int,
    h: int,
    *,
    cols: int,
    rows: int,
    left_pad: int = 0,
    right_pad: int = 0,
    top_pad: int = 0,
    bottom_pad: int = 0,
    gutter_x: int = 0,
    gutter_y: int = 0,
) -> List[Tuple[int, int, int, int]]:
    """
    Divide a page into rows*cols tiles with optional padding and gutters.
    Returns list of bboxes in row-major order.
    """
    usable_w = w - left_pad - right_pad
    usable_h = h - top_pad - bottom_pad
    if usable_w <= 0 or usable_h <= 0:
        return []

    # total space gutters consume
    total_gx = gutter_x * (cols - 1)
    total_gy = gutter_y * (rows - 1)

    tile_w = (usable_w - total_gx) / cols
    tile_h = (usable_h - total_gy) / rows

    boxes: List[Tuple[int, int, int, int]] = []
    for r in range(rows):
        for c in range(cols):
            x1 = int(left_pad + c * (tile_w + gutter_x))
            y1 = int(top_pad + r * (tile_h + gutter_y))
            x2 = int(x1 + tile_w)
            y2 = int(y1 + tile_h)
            boxes.append((x1, y1, x2, y2))
    return boxes


def slice_pages_to_tiles(
    page_pngs: List[Path],
    *,
    out_dir: Path,
    cols: int,
    rows: int,
    left_pad: int,
    right_pad: int,
    top_pad: int,
    bottom_pad: int,
    gutter_x: int,
    gutter_y: int,
    blank_white_thresh: int,
    blank_max_nonwhite_pct: float,
) -> List[TileMeta]:
    out_dir.mkdir(parents=True, exist_ok=True)

    metas: List[TileMeta] = []
    offer_idx = 1

    for p in page_pngs:
        try:
            page_num = int(p.stem)
        except Exception:
            # If non-numeric pages exist, still process but label page=0
            page_num = 0

        img = Image.open(p).convert("RGB")
        boxes = compute_grid_boxes(
            img.width,
            img.height,
            cols=cols,
            rows=rows,
            left_pad=left_pad,
            right_pad=right_pad,
            top_pad=top_pad,
            bottom_pad=bottom_pad,
            gutter_x=gutter_x,
            gutter_y=gutter_y,
        )

        for i, bbox in enumerate(boxes):
            r = i // cols
            c = i % cols
            tile = safe_crop(img, bbox)

            # Skip blank tiles
            if is_tile_mostly_blank(tile, white_thresh=blank_white_thresh, max_nonwhite_pct=blank_max_nonwhite_pct):
                continue

            offer_id = f"offer_{offer_idx:04d}"
            out_png = out_dir / f"{offer_id}.png"
            tile.save(out_png)

            metas.append(
                TileMeta(
                    offer_id=offer_id,
                    page=page_num,
                    row=r + 1,
                    col=c + 1,
                    bbox=bbox,
                    src_page_png=str(p).replace("\\", "/"),
                    out_png=str(out_png).replace("\\", "/"),
                )
            )
            offer_idx += 1

    return metas


# -----------------------------
# CLI
# -----------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Slice WF grid-style page PNGs into tile PNGs (processed/slices_auto)."
    )
    ap.add_argument("--region", required=True, help="Region code (e.g., NE)")
    ap.add_argument("--store", required=True, help="Store slug (e.g., whole_foods)")
    ap.add_argument("--week", required=True, help="Week folder (e.g., wk_20251228)")
    ap.add_argument("--repo-root", default=None, help="Repo root. If omitted, auto-detect.")

    ap.add_argument("--cols", type=int, default=7, help="Grid columns across (default 7)")
    ap.add_argument("--rows", type=int, default=1, help="Grid rows down (default 1). Use 2 if pages have two bands.")
    ap.add_argument("--left-pad", type=int, default=0)
    ap.add_argument("--right-pad", type=int, default=0)
    ap.add_argument("--top-pad", type=int, default=0)
    ap.add_argument("--bottom-pad", type=int, default=0)
    ap.add_argument("--gutter-x", type=int, default=0)
    ap.add_argument("--gutter-y", type=int, default=0)

    ap.add_argument("--blank-white-thresh", type=int, default=245, help="Grayscale threshold for 'near-white'")
    ap.add_argument("--blank-max-nonwhite-pct", type=float, default=0.02, help="Max nonwhite fraction to consider blank")

    ap.add_argument("--clean", action="store_true", help="Delete processed/slices_auto before writing")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    wk_path = week_dir(repo_root, args.region, args.store, args.week)

    if not wk_path.exists():
        print(f"[ERROR] Week path not found: {wk_path}")
        return 2

    page_pngs = find_page_pngs(wk_path)
    if not page_pngs:
        print(f"[ERROR] No page PNGs found in: {wk_path / 'raw_png'}")
        return 3

    processed = wk_path / "processed"
    out_dir = processed / "slices_auto"

    if args.clean and out_dir.exists():
        for f in out_dir.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass

    metas = slice_pages_to_tiles(
        page_pngs,
        out_dir=out_dir,
        cols=args.cols,
        rows=args.rows,
        left_pad=args.left_pad,
        right_pad=args.right_pad,
        top_pad=args.top_pad,
        bottom_pad=args.bottom_pad,
        gutter_x=args.gutter_x,
        gutter_y=args.gutter_y,
        blank_white_thresh=args.blank_white_thresh,
        blank_max_nonwhite_pct=args.blank_max_nonwhite_pct,
    )

    meta_path = out_dir / "tiles_meta.json"
    meta_path.write_text(json.dumps([asdict(m) for m in metas], indent=2), encoding="utf-8")

    print(f"Found {len(page_pngs)} page PNG(s) in: {wk_path / 'raw_png'}")
    print(f"SLICED {len(metas)} TILE(S) to:\n  {out_dir}")
    print(f"Tile meta written to:\n  {meta_path}")

    # print first few lines for sanity
    for m in metas[:10]:
        print(f"{m.offer_id}  page={m.page} row={m.row} col={m.col} bbox={m.bbox}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
