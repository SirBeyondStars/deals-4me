# cleanup_raw_png_excavate.py
# Excavates "real" image files from polluted folders like:
#   1
#   1.ocr
#   1.ocr.ocr
#   1.ocr.ocr.ocr ...
#
# Strategy:
# - Group files by "page id" (everything before repeated ".ocr" chains)
# - Detect true file type by magic bytes (PNG/JPEG/PDF/WEBP/TIFF)
# - Keep the best candidate (largest recognized media file) per id
# - Rename kept file to "<id>.<ext>"
# - Move all other variants into a quarantine folder

from __future__ import annotations

import argparse
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Tuple


MEDIA_EXT_BY_KIND = {
    "png": "png",
    "jpg": "jpg",
    "pdf": "pdf",
    "webp": "webp",
    "tif": "tif",
}


def detect_kind(path: Path) -> Optional[str]:
    """Detect file kind by header bytes (not filename)."""
    try:
        with path.open("rb") as f:
            head = f.read(32)
    except Exception:
        return None

    # PNG
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"

    # JPEG
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"

    # PDF
    if head.startswith(b"%PDF"):
        return "pdf"

    # WEBP (RIFF....WEBP)
    if len(head) >= 12 and head[0:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"

    # TIFF
    if head.startswith(b"II*\x00") or head.startswith(b"MM\x00*"):
        return "tif"

    return None


_ID_RE = re.compile(r"^(\d+)")


# Accept anything that STARTS with digits, ignoring whatever comes after.
# Examples it will accept:
#   "1"
#   "1.ocr"
#   "1.ocr.ocr.ocr"
#   "1.ocr.ocr.ocr.ocr.ocr"
#   "1.OCR.OCR"
#   "1 (1)"
#   "1 - copy"
_ID_RE = re.compile(r"^(\d+)")

def root_id_from_name(name: str) -> Optional[str]:
    s = (name or "").strip()
    m = _ID_RE.match(s)
    if not m:
        return None
    return m.group(1)


@dataclass
class Candidate:
    path: Path
    kind: Optional[str]
    size: int


def ensure_folder(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def safe_move(src: Path, dst_folder: Path) -> Path:
    ensure_folder(dst_folder)
    dst = dst_folder / src.name
    # avoid overwriting
    if dst.exists():
        stem = dst.stem
        suf = dst.suffix
        i = 1
        while True:
            alt = dst_folder / f"{stem}__dup{i}{suf}"
            if not alt.exists():
                dst = alt
                break
            i += 1
    shutil.move(str(src), str(dst))
    return dst


def safe_rename(src: Path, dst: Path) -> None:
    if dst.exists():
        # If the destination exists, don't overwrite. Append suffix.
        stem = dst.stem
        suf = dst.suffix
        i = 1
        while True:
            alt = dst.with_name(f"{stem}__dup{i}{suf}")
            if not alt.exists():
                dst = alt
                break
            i += 1
    src.rename(dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True, help="Folder to excavate (raw_png)")
    ap.add_argument("--dry-run", action="store_true", help="Print actions without changing files")
    ap.add_argument(
        "--quarantine",
        default="_quarantine_ocr_junk",
        help="Subfolder name (inside --folder) to move junk/duplicates into",
    )
    args = ap.parse_args()

    folder = Path(args.folder).resolve()
    if not folder.exists() or not folder.is_dir():
        print(f"[ERROR] Not a folder: {folder}")
        return 1

    quarantine = folder / args.quarantine

    # Collect candidates
    groups: Dict[str, List[Candidate]] = {}
    for p in folder.iterdir():
        if not p.is_file():
            continue

        rid = root_id_from_name(p.name)
        if not rid:
            # Not in the "page id" family; ignore
            continue

        kind = detect_kind(p)
        size = p.stat().st_size
        groups.setdefault(rid, []).append(Candidate(path=p, kind=kind, size=size))

    if not groups:
        print("[INFO] No candidate files matched pattern like '1' or '1.ocr.ocr'")
        return 0

    kept_count = 0
    moved_count = 0
    skipped_unknown = 0

    # Decide per group
    for rid, cands in sorted(groups.items(), key=lambda kv: int(kv[0])):
        # Prefer recognized media kinds; pick the largest recognized media file
        recognized = [c for c in cands if c.kind in MEDIA_EXT_BY_KIND]
        unknown = [c for c in cands if c.kind is None]

        if not recognized:
            # Nothing we can confidently treat as media
            skipped_unknown += 1
            print(f"[SKIP] id={rid} has no recognizable media files. (count={len(cands)})")
            continue

        recognized.sort(key=lambda c: c.size, reverse=True)
        keep = recognized[0]
        keep_ext = MEDIA_EXT_BY_KIND[keep.kind]  # type: ignore[arg-type]
        target_name = f"{rid}.{keep_ext}"
        target_path = folder / target_name

        # Move everything else to quarantine (including other recognized + unknown)
        junk = [c for c in cands if c.path != keep.path]

        print(f"[KEEP] id={rid} -> {keep.path.name} ({keep.kind}, {keep.size} bytes) => {target_name}")
        if junk:
            print(f"       junk: {len(junk)} file(s) -> {quarantine.name}/")

        if args.dry_run:
            continue

        # First, rename kept file to clean name if needed
        if keep.path.name != target_name:
            safe_rename(keep.path, target_path)

        # Move junk to quarantine
        for j in junk:
            safe_move(j.path, quarantine)
            moved_count += 1

        kept_count += 1

    print("")
    print(f"[SUMMARY] groups={len(groups)} kept={kept_count} moved_to_quarantine={moved_count} skipped_unknown_groups={skipped_unknown}")
    if not args.dry_run:
        print(f"[SUMMARY] quarantine folder: {quarantine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
