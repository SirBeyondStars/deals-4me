from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

from PIL import Image


def find_white_gutters(img: Image.Image, white_thr: int, min_run_px: int, margin_px: int) -> List[Tuple[int, int]]:
    """
    Returns list of (x0, x1) gutter spans (inclusive-exclusive) where the column is mostly white.
    We detect gutters by measuring per-x "ink" (dark pixels) density.
    """
    g = img.convert("L")
    w, h = g.size

    # Crop margins away so page border/rounded corners don't confuse detection
    x0 = margin_px
    x1 = w - margin_px
    y0 = margin_px
    y1 = h - margin_px
    g = g.crop((x0, y0, x1, y1))
    w2, h2 = g.size

    px = g.load()

    # Compute "darkness density" per x: count pixels below white_thr
    # If very few dark pixels -> likely a gutter (white space).
    dark_counts = [0] * w2
    for x in range(w2):
        cnt = 0
        # sample every 3 pixels vertically for speed
        for y in range(0, h2, 3):
            if px[x, y] < white_thr:
                cnt += 1
        dark_counts[x] = cnt

    # Consider a column "white" if it has <= this many dark samples
    # This is adaptive: page may have different overall density.
    # We'll set cutoff relative to height samples.
    samples_per_col = (h2 + 2) // 3
    white_cutoff = max(2, int(samples_per_col * 0.01))  # <= 1% dark samples

    gutters: List[Tuple[int, int]] = []
    in_run = False
    run_start = 0

    for x in range(w2):
        is_white = dark_counts[x] <= white_cutoff
        if is_white and not in_run:
            in_run = True
            run_start = x
        elif not is_white and in_run:
            in_run = False
            run_end = x
            if run_end - run_start >= min_run_px:
                gutters.append((run_start, run_end))
    if in_run:
        run_end = w2
        if run_end - run_start >= min_run_px:
            gutters.append((run_start, run_end))

    # Convert back to original image coordinates
    gutters = [(gx0 + x0, gx1 + x0) for (gx0, gx1) in gutters]

    # Merge gutters that are very close
    merged: List[Tuple[int, int]] = []
    for a, b in gutters:
        if not merged:
            merged.append((a, b))
            continue
        pa, pb = merged[-1]
        if a <= pb + 6:
            merged[-1] = (pa, max(pb, b))
        else:
            merged.append((a, b))

    return merged


def tiles_from_gutters(img_w: int, gutters: List[Tuple[int, int]], min_tile_w: int) -> List[Tuple[int, int]]:
    """
    Given gutter spans, return tile x-ranges.
    """
    # Use gutters as split boundaries: [0 .. g0], [g0 .. g1], ...
    splits = [0]
    for a, b in gutters:
        mid = (a + b) // 2
        splits.append(mid)
    splits.append(img_w)

    splits = sorted(set(splits))

    tiles: List[Tuple[int, int]] = []
    for i in range(len(splits) - 1):
        x0 = splits[i]
        x1 = splits[i + 1]
        if x1 - x0 >= min_tile_w:
            tiles.append((x0, x1))

    # If we got too many tiles (noise), collapse to max 4 by keeping widest
    if len(tiles) > 4:
        tiles = sorted(tiles, key=lambda t: (t[1] - t[0]), reverse=True)[:4]
        tiles = sorted(tiles, key=lambda t: t[0])

    return tiles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-root", required=True, help=r"...\flyers\NE\whole_foods\wk_YYYYMMDD")
    ap.add_argument("--in-folder", default="raw_png", help="Folder under week-root containing page PNGs (default: raw_png)")
    ap.add_argument("--out-folder", default=r"ocr_work\wf_bands", help="Output folder under week-root (default: ocr_work\\wf_bands)")
    ap.add_argument("--footer-frac", type=float, default=0.42, help="Bottom band height as fraction of tile (default: 0.42)")
    ap.add_argument("--white-thr", type=int, default=245, help="Pixel value considered 'white-ish' (default: 245)")
    ap.add_argument("--min-gutter", type=int, default=18, help="Minimum gutter width in pixels (default: 18)")
    ap.add_argument("--min-tile-w", type=int, default=220, help="Minimum tile width in pixels (default: 220)")
    ap.add_argument("--margin", type=int, default=12, help="Ignore this margin around page (default: 12)")
    args = ap.parse_args()

    week_root = Path(args.week_root)
    in_dir = week_root / args.in_folder
    if not in_dir.exists():
        print(f"[ERROR] input folder not found: {in_dir}")
        return 2

    out_dir = week_root / Path(args.out_folder)
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = sorted(in_dir.glob("*.png"))
    if not pages:
        print(f"[WARN] no PNGs in: {in_dir}")
        return 0

    total_bands = 0
    for p in pages:
        img = Image.open(p).convert("RGB")
        w, h = img.size

        gutters = find_white_gutters(
            img,
            white_thr=args.white_thr,
            min_run_px=args.min_gutter,
            margin_px=args.margin,
        )
        tiles = tiles_from_gutters(w, gutters, min_tile_w=args.min_tile_w)

        # Fallback: if no tiles found, treat whole page as one tile
        if not tiles:
            tiles = [(0, w)]

        # Crop each tile footer band
        page_stem = p.stem
        for ti, (x0, x1) in enumerate(tiles, start=1):
            tile = img.crop((x0, 0, x1, h))
            tw, th = tile.size

            footer_h = int(th * args.footer_frac)
            y0 = max(0, th - footer_h)
            band = tile.crop((0, y0, tw, th))

            out_name = f"{page_stem}_tile{ti:02d}_band.png"
            band.save(out_dir / out_name, optimize=True)
            total_bands += 1

        print(f"[OK] {p.name}: tiles={len(tiles)} gutters={len(gutters)} -> bands saved")

    print("[DONE]")
    print(f"  input:  {in_dir}")
    print(f"  output: {out_dir}")
    print(f"  pages:  {len(pages)}")
    print(f"  bands:  {total_bands}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
