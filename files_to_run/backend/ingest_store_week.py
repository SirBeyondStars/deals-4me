# files_to_run/backend/ingest_store_week.py
# Region-first + wk_YYYYMMDD ingestion wrapper
# - Validates week code
# - Computes canonical folder paths
# - Enumerates inputs in raw_* folders
# - OCR mode: none | auto | full (hook points provided)

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple


WEEK_RE = re.compile(r"^wk_(\d{8})$")


@dataclass(frozen=True)
class WeekContext:
    project_root: Path
    flyers_root: Path
    region: str
    store: str
    week_code: str
    week_start: datetime

    week_root: Path
    raw_pdf: Path
    raw_png: Path
    raw_images: Path
    processed: Path
    ocr: Path
    exports: Path
    logs: Path


def parse_week_code(week_code: str) -> datetime:
    m = WEEK_RE.match(week_code.strip())
    if not m:
        raise ValueError(f"Invalid week code '{week_code}'. Expected format: wk_YYYYMMDD")

    yyyymmdd = m.group(1)
    dt = datetime.strptime(yyyymmdd, "%Y%m%d")
    return dt


def build_context(project_root: Path, region: str, store: str, week_code: str) -> WeekContext:
    region = region.strip().upper()
    store = store.strip()

    week_start = parse_week_code(week_code)
    # Python: Monday=0..Sunday=6
    if week_start.weekday() != 6:
        print(f"[WARN] Week code '{week_code}' is not a Sunday start date. (Proceeding anyway.)")

    flyers_root = project_root / "flyers"
    week_root = flyers_root / region / store / week_code

    return WeekContext(
        project_root=project_root,
        flyers_root=flyers_root,
        region=region,
        store=store,
        week_code=week_code,
        week_start=week_start,
        week_root=week_root,
        raw_pdf=week_root / "raw_pdf",
        raw_png=week_root / "raw_png",
        raw_images=week_root / "raw_images",
        processed=week_root / "processed",
        ocr=week_root / "ocr",
        exports=week_root / "exports",
        logs=week_root / "logs",
    )


def ensure_dirs(ctx: WeekContext) -> None:
    for p in [
        ctx.week_root,
        ctx.raw_pdf, ctx.raw_png, ctx.raw_images,
        ctx.processed, ctx.ocr, ctx.exports, ctx.logs,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def list_inputs(ctx: WeekContext) -> List[Path]:
    exts = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
    inputs: List[Path] = []
    for folder in [ctx.raw_pdf, ctx.raw_png, ctx.raw_images]:
        if not folder.exists():
            continue
        for f in folder.rglob("*"):
            if f.is_file() and f.suffix.lower() in exts:
                inputs.append(f)
    return sorted(inputs)


def ingest_files(ctx: WeekContext, inputs: List[Path], ocr_mode: str) -> None:
    """
    Hook point:
    - This is where your existing pipeline should be called:
      - file normalization
      - image conversion (if needed)
      - OCR passes (none/auto/full)
      - chunking / extraction
      - DB writes (Supabase)
      - export artifacts
    """
    print(f"[INFO] Ingest start: region={ctx.region} store={ctx.store} week={ctx.week_code} ocr={ocr_mode}")
    print(f"[INFO] Week root: {ctx.week_root}")

    if not inputs:
        print("[WARN] No input files found in raw_pdf/raw_png/raw_images.")
        return

    print(f"[INFO] Found {len(inputs)} input files.")
    # For now, just enumerate. Replace this loop with your real ingest calls.
    for f in inputs:
        print(f"  - {f.relative_to(ctx.project_root)}")

    # TODO: call your existing ingestion function(s) here.
    # e.g. pipeline.run(ctx=ctx, files=inputs, ocr_mode=ocr_mode)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True, help="Region code, e.g., NE")
    ap.add_argument("--store", required=True, help="Store slug, e.g., whole_foods")
    ap.add_argument("--week", required=True, help="Week code, e.g., wk_20251228")
    ap.add_argument("--ocr", required=True, choices=["none", "auto", "full"], help="OCR mode")
    ap.add_argument("--project-root", default=None, help="Optional project root override")

    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[2]
    ctx = build_context(project_root=project_root, region=args.region, store=args.store, week_code=args.week)

    if not ctx.week_root.exists():
        print(f"[ERROR] Week folder does not exist: {ctx.week_root}")
        print("        Run: files_to_run/backend/prep_week_flyer_folders.ps1 first.")
        return 2

    ensure_dirs(ctx)
    inputs = list_inputs(ctx)
    ingest_files(ctx, inputs, args.ocr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
