from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import os, sys
from pathlib import Path

print("\n=== ARG DEBUG ===")
print("sys.argv:", sys.argv)
print("cwd:", os.getcwd())
print("__file__:", __file__)
print("resolved file:", Path(__file__).resolve())
print("==============\n")


# ============================================================
# OCR ORCHESTRATOR (AUTO MODE DEFAULT)
#
# This file is the "brain" of the weekly OCR pipeline.
# It decides:
#   - which week is locked
#   - which region/stores are eligible
#   - whether OCR runs at all
#   - which OCR mode is used (AUTO vs FULL)
#
# IMPORTANT:
# - This file does NOT implement OCR logic itself.
# - It orchestrates and calls the underlying OCR helpers.
# - Running this script with default options = OCR AUTO.
#
# If OCR behavior seems wrong, start debugging HERE first.
# ============================================================

# -----------------------------
# Stores / mapping
# -----------------------------
STORE_SLUGS = [
    "aldi",
    "big_y",
    "hannaford",
    "market_basket",
    "price_chopper_market_32",
    "pricerite",
    "roche_bros",
    "shaws",
    "stop_and_shop_ct",
    "stop_and_shop_mari",
    "trucchis",
    "wegmans",
    "whole_foods",
]

STORE_DIR_OVERRIDE: Dict[str, str] = {
    # "price_chopper_market_32": "price_chopper",
    # "stop_and_shop_mari": "stop_and_shop_ri_ma",
}

DEFAULT_REGION = "NE"


# -----------------------------
# Path helpers
# -----------------------------
def project_root() -> Path:
    # <project_root>/files_to_run/backend/run_weekly_pipeline.py
    return Path(__file__).resolve().parents[2]


def flyers_region_root(region: str) -> Path:
    return project_root() / "flyers" / region


def normalize_week_code(raw: str) -> str:
    s = (raw or "").strip().lower().replace(" ", "")
    if not s:
        return s

    if s.startswith("week"):
        return s

    if s.startswith("wk_") and s[3:].isdigit() and len(s[3:]) == 8:
        return s
    if s.startswith("wk") and s[2:].isdigit() and len(s[2:]) == 8:
        return "wk_" + s[2:]

    if s.isdigit() and len(s) == 8:
        return "wk_" + s

    if s.isdigit():
        return f"week{int(s)}"

    return s


def store_folder_name(slug: str) -> str:
    return STORE_DIR_OVERRIDE.get(slug, slug)


def week_dir(region: str, slug: str, week_code: str) -> Path:
    return flyers_region_root(region) / store_folder_name(slug) / week_code


def ensure_task_log_dir(region: str) -> Path:
    d = flyers_region_root(region) / "logs" / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    return d


# -----------------------------
# Tool discovery (so you don't have to remember script names)
# -----------------------------
def list_backend_files() -> List[Path]:
    backend = project_root() / "files_to_run" / "backend"
    if not backend.exists():
        return []
    return [p for p in backend.iterdir() if p.is_file()]


def pick_best_candidate(cands: List[Path]) -> Optional[Path]:
    if not cands:
        return None
    # Prefer newest modified
    cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0]


def find_tool(keyword_groups: List[List[str]], exts: Tuple[str, ...] = (".py", ".ps1")) -> Optional[Path]:
    """
    Finds a script in files_to_run/backend whose filename contains ALL words in one group.
    keyword_groups: e.g. [["ocr","auto"], ["ocr","week","auto"]]
    """
    files = [p for p in list_backend_files() if p.suffix.lower() in exts]
    matches: List[Path] = []

    for p in files:
        name = p.name.lower()
        for group in keyword_groups:
            if all(k.lower() in name for k in group):
                matches.append(p)
                break

    return pick_best_candidate(matches)


def resolve_ocr_auto_tool() -> Optional[Path]:
    return find_tool([["ocr", "auto"], ["ocr", "week", "auto"], ["run", "ocr", "auto"]])


def resolve_ocr_full_tool() -> Optional[Path]:
    return find_tool([["ocr", "full"], ["ocr", "week", "full"], ["run", "ocr", "full"], ["ocr", "passes"]])


# -----------------------------
# Execution helpers
# -----------------------------
def has_any_inputs(wk_dir: Path) -> bool:
    # Consider "ready for OCR" if any PDFs or PNG/JPGs exist in raw_pdf/raw_png
    raw_pdf = wk_dir / "raw_pdf"
    raw_png = wk_dir / "raw_png"
    exts = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}

    for folder in (raw_pdf, raw_png):
        if folder.exists():
            for p in folder.iterdir():
                if p.is_file() and p.suffix.lower() in exts:
                    return True
    return False


def run_cmd(cmd: List[str], log_file: Path, dry_run: bool) -> int:
    cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    print(f"[RUN] {cmd_str}")
    print(f"[LOG] {log_file}")

    if dry_run:
        return 0

    with log_file.open("w", encoding="utf-8", errors="ignore") as f:
        f.write(f"COMMAND: {cmd_str}\n")
        f.write(f"START:   {datetime.now().isoformat()}\n\n")
        f.flush()

        p = subprocess.run(
            cmd,
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(project_root()),
        )

        f.write(f"\nEND:     {datetime.now().isoformat()}\n")
        f.write(f"RC:      {p.returncode}\n")

    return p.returncode


def build_tool_command(tool: Path, slug: str, region: str, week_code: str) -> List[str]:
    """
    We don't know each script's CLI, so we support the two most common patterns:
      - Python script: python <tool> <store> --week <week> --region <region>
      - PowerShell script: pwsh -File <tool> -Store <store> -Week <week> -Region <region>
    If your script uses different flags, we can adjust once we see its help output.
    """
    if tool.suffix.lower() == ".py":
        return [sys.executable, str(tool), slug, "--week", week_code, "--region", region]
    else:
        return ["pwsh", "-File", str(tool), "-Store", slug, "-Week", week_code, "-Region", region]


# -----------------------------
# Main# Entry point for weekly OCR AUTO runs
# -----------------------------
def main() -> int:
    ap = argparse.ArgumentParser(prog="run_weekly_pipeline.py")
    ap.add_argument("store", nargs="?", default="all", help='Store slug (e.g. whole_foods) or "all".')
    ap.add_argument("--week", required=True, help="week51 | 51 | wk_YYYYMMDD | YYYYMMDD")
    ap.add_argument("--region", default=DEFAULT_REGION, help='Region folder under flyers (e.g. NE, MidAtl).')

    ap.add_argument("--verify-only", action="store_true", help="Only verify folder presence / inputs (no OCR).")
    ap.add_argument("--dry-run", action="store_true", help="Print commands but do not execute.")

    ap.add_argument("--ocr-auto", action="store_true", help="Run OCR AUTO stage for selected stores.")
    ap.add_argument("--ocr-full", action="store_true", help="Run OCR FULL/PASSES stage for selected stores.")

    args = ap.parse_args()

    store = (args.store or "all").strip().lower()
    region = (args.region or DEFAULT_REGION).strip()
    week_code = normalize_week_code(args.week)

    if store != "all" and store not in STORE_SLUGS:
        print(f"[FATAL] Unknown store slug: {store}")
        print(f"        Valid: {', '.join(STORE_SLUGS)}")
        return 2

    slugs: List[str] = STORE_SLUGS if store == "all" else [store]

    region_root = flyers_region_root(region).resolve()
    if not region_root.exists():
        print(f"[FATAL] Region folder not found: {region_root}")
        print(f"        Expected: <project_root>/flyers/{region}/")
        return 2

    print(f"[INFO] project_root: {project_root()}")
    print(f"[INFO] region_root:  {region_root}")
    print(f"[INFO] region:       {region}")
    print(f"[INFO] week:         {week_code}")
    print(f"[INFO] store(s):     {('ALL' if store == 'all' else store)}")
    print(f"[INFO] dry_run:      {args.dry_run}")
    print()

    # Verify stage: show folder + input readiness
    print(f"{'store':<22} {'week_dir':<4} {'has_inputs':<9}  week_dir_path")
    print("-" * 100)

    wk_dirs: Dict[str, Path] = {}
    missing: List[str] = []
    no_inputs: List[str] = []

    for slug in slugs:
        d = week_dir(region, slug, week_code)
        wk_dirs[slug] = d
        exists = d.exists()
        inputs = has_any_inputs(d) if exists else False

        if not exists:
            missing.append(slug)
        elif not inputs:
            no_inputs.append(slug)

        print(f"{slug:<22} {('YES' if exists else 'NO'):<4} {('YES' if inputs else 'NO'):<9}  {d}")

    print("-" * 100)
    print(f"[SUMMARY] missing_week_dirs={len(missing)}  no_inputs={len(no_inputs)}  total={len(slugs)}")
    if missing:
        print(f"[SUMMARY] missing: {', '.join(missing)}")
    if no_inputs:
        print(f"[SUMMARY] no_inputs: {', '.join(no_inputs)}")
    print()

    if args.verify_only:
        print("[OK] verify-only complete.")
        return 0

    # OCR tool resolution
    if args.ocr_auto:
        tool = resolve_ocr_auto_tool()
        if not tool:
            print("[FATAL] Could not auto-find an OCR AUTO script in files_to_run/backend.")
            print('        Expected filename to include something like "ocr" + "auto".')
            return 2
        print(f"[INFO] OCR AUTO tool: {tool}")
        print()

        log_dir = ensure_task_log_dir(region)
        for slug in slugs:
            d = wk_dirs[slug]
            if not d.exists():
                print(f"[SKIP] {slug}: week dir missing")
                continue
            if not has_any_inputs(d):
                print(f"[SKIP] {slug}: no inputs in raw_pdf/raw_png")
                continue

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"ocr_auto__{region}__{slug}__{week_code}__{ts}.log"
            cmd = build_tool_command(tool, slug, region, week_code)
            rc = run_cmd(cmd, log_file, args.dry_run)
            if rc != 0:
                print(f"[ERROR] {slug}: OCR AUTO failed (rc={rc}). See log: {log_file}")
                return rc

        print("[OK] OCR AUTO complete.")
        print()

    if args.ocr_full:
        tool = resolve_ocr_full_tool()
        if not tool:
            print("[FATAL] Could not auto-find an OCR FULL script in files_to_run/backend.")
            print('        Expected filename to include something like "ocr" + "full" or "passes".')
            return 2
        print(f"[INFO] OCR FULL tool: {tool}")
        print()

        log_dir = ensure_task_log_dir(region)
        for slug in slugs:
            d = wk_dirs[slug]
            if not d.exists():
                print(f"[SKIP] {slug}: week dir missing")
                continue
            if not has_any_inputs(d):
                print(f"[SKIP] {slug}: no inputs in raw_pdf/raw_png")
                continue

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"ocr_full__{region}__{slug}__{week_code}__{ts}.log"
            cmd = build_tool_command(tool, slug, region, week_code)
            rc = run_cmd(cmd, log_file, args.dry_run)
            if rc != 0:
                print(f"[ERROR] {slug}: OCR FULL failed (rc={rc}). See log: {log_file}")
                return rc

        print("[OK] OCR FULL complete.")
        print()

    if not args.ocr_auto and not args.ocr_full:
        print("[NOTE] No OCR flags provided. Use --ocr-auto and/or --ocr-full.")
        print("       Tip: use --dry-run first to see exactly what would execute.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
