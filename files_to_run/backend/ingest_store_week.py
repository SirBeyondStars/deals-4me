# files_to_run/backend/ingest_store_week.py
# Purpose:
#   Ingest a single store/week into Supabase (table: flyer_items).
#   Supports TWO inputs:
#     1) OCR pipeline -> parse_offers_week.py -> parsed_week.csv
#     2) Manual Excel converted to STANDARD offers CSV (same columns as flyer_items)
#
# Key rule:
#   For DB inserts, use None for unknown dates/ints, NOT "".

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

WEEK_RE = re.compile(r"^wk_(\d{8})$")


# -------------------------
# Types / context
# -------------------------
@dataclass(frozen=True)
class WeekContext:
    project_root: Path
    flyers_root: Path
    region: str
    store: str
    week_code: str
    week_start: datetime
    week_root: Path


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x).strip()


def _to_int_or_none(x: Any) -> Optional[int]:
    s = _safe_str(x)
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def _to_price_or_none(x: Any) -> Optional[float]:
    s = _safe_str(x).replace("$", "").replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _to_date_or_none(x: Any) -> Optional[str]:
    """
    Return ISO date string (YYYY-MM-DD) or None.
    Accepts:
      - "" -> None
      - "2026-01-18" -> itself
      - "01/18/2026" -> converted
    """
    s = _safe_str(x)
    if not s:
        return None

    # already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s

    # mm/dd/yyyy
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        mm, dd, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{int(yyyy):04d}-{int(mm):02d}-{int(dd):02d}"

    return None


def parse_week_code(week_code: str) -> datetime:
    m = WEEK_RE.match(week_code.strip())
    if not m:
        raise ValueError(f"Invalid week code '{week_code}'. Expected format: wk_YYYYMMDD")
    return datetime.strptime(m.group(1), "%Y%m%d")


def build_context(project_root: Path, region: str, store: str, week_code: str) -> WeekContext:
    region = region.strip().upper()
    store = store.strip()
    week_start = parse_week_code(week_code)

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
    )


# -------------------------
# Supabase writer (PostgREST)
# -------------------------
def supabase_insert_rows(table: str, rows: List[dict], batch_size: int = 500) -> int:
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.environ.get("SUPABASE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Missing SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) in environment."
        )

    endpoint = supabase_url.rstrip("/") + f"/rest/v1/{table}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    wrote = 0
    i = 0
    while i < len(rows):
        chunk = rows[i : i + batch_size]
        r = requests.post(endpoint, headers=headers, data=json.dumps(chunk))
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase insert failed at batch starting {i}: HTTP {r.status_code}: {r.text}")
        wrote += len(chunk)
        i += batch_size

    return wrote


# -------------------------
# CSV -> flyer_items rows
# -------------------------
FLYER_ITEMS_HEADERS = [
    "item_name",
    "store",
    "region",
    "week_code",
    "promo_start",
    "promo_end",
    "percent_off_prime",
    "percent_off_nonprime",
    "sale_price",
    "manual_review_reason",
    "source_file",
]


def _rows_from_standard_offers_csv(ctx: WeekContext, csv_path: Path) -> List[dict]:
    """
    Reads a CSV that already uses flyer_items headers (or close to it),
    normalizes types, and returns rows ready for Supabase.
    """
    out: List[dict] = []

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)

        for row in r:
            item_name = _safe_str(row.get("item_name"))
            if not item_name:
                continue

            rec = {
                "item_name": item_name,
                "store": _safe_str(row.get("store")) or ctx.store,
                "region": _safe_str(row.get("region")) or ctx.region,
                "week_code": _safe_str(row.get("week_code")) or ctx.week_code,

                "promo_start": _to_date_or_none(row.get("promo_start")),
                "promo_end": _to_date_or_none(row.get("promo_end")),

                "percent_off_prime": _to_int_or_none(row.get("percent_off_prime")),
                "percent_off_nonprime": _to_int_or_none(row.get("percent_off_nonprime")),

                "sale_price": _to_price_or_none(row.get("sale_price")),

                "manual_review_reason": _safe_str(row.get("manual_review_reason")) or None,
                "source_file": _safe_str(row.get("source_file")) or csv_path.name,
            }

            out.append(rec)

    return out


# -------------------------
# OCR pipeline hooks (optional)
# -------------------------
def _run_cmd(cmd: List[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n\nSTDOUT:\n{p.stdout}\n\nSTDERR:\n{p.stderr}")


def run_ocr_and_parse(ctx: WeekContext, ocr_mode: str) -> Path:
    """
    Runs your existing OCR pipeline that produces:
      exports/_debug_offers/parsed_week.csv
    Returns that parsed_week.csv path.

    NOTE: This assumes your repo already has:
      - files_to_run/backend/chunk_ocr_to_debug_offers.py
      - files_to_run/backend/parse_offers_week.py
    """
    debug_root = ctx.week_root / "exports" / "_debug_offers"
    debug_root.mkdir(parents=True, exist_ok=True)

    chunk_script = ctx.project_root / "files_to_run" / "backend" / "chunk_ocr_to_debug_offers.py"
    parse_script = ctx.project_root / "files_to_run" / "backend" / "parse_offers_week.py"

    if ocr_mode != "none":
        # chunk_ocr_to_debug_offers.py supports --brand (store) and --week-root
        _run_cmd(
            [
                sys.executable,
                str(chunk_script),
                "--week-root",
                str(ctx.week_root),
                "--brand",
                ctx.store,
            ]
        )

    # parse_offers_week.py -> parsed_week.csv in debug_root
    _run_cmd(
        [
            sys.executable,
            str(parse_script),
            "--debug-root",
            str(debug_root),
            "--brand",
            ctx.store,
            "--week",
            ctx.week_code,
        ]
    )

    parsed_week = debug_root / "parsed_week.csv"
    if not parsed_week.exists():
        raise FileNotFoundError(f"Expected parsed_week.csv not found at: {parsed_week}")

    return parsed_week


# -------------------------
# Main
# -------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--store", required=True)
    ap.add_argument("--week", required=True)

    ap.add_argument("--ocr", choices=["none", "auto", "full"], default="auto")

    # Excel/CSV ingestion inputs
    ap.add_argument("--input-csv", default="", help="Path to a STANDARD offers CSV (flyer_items headers)")
    ap.add_argument("--input-csv-dir", default="", help="Folder of STANDARD offers CSVs (e.g. manual_imports\\csv)")

    ap.add_argument("--write-supabase", action="store_true")
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[2]  # .../files_to_run/backend/ -> project root
    ctx = build_context(project_root, args.region, args.store, args.week)

    print(f"[INFO] Ingest start: region={ctx.region} store={ctx.store} week={ctx.week_code} ocr={args.ocr}")
    print(f"[INFO] Week root: {ctx.week_root}")

    rows_all: List[dict] = []

    # 1) If given CSV(s), ingest them (Excel-converted path)
    if args.input_csv:
        p = Path(args.input_csv)
        if not p.exists():
            raise FileNotFoundError(p)
        rows = _rows_from_standard_offers_csv(ctx, p)
        print(f"[INFO] Loaded {len(rows)} row(s) from CSV: {p}")
        rows_all.extend(rows)

    if args.input_csv_dir:
        d = Path(args.input_csv_dir)
        if not d.exists():
            raise FileNotFoundError(d)
        csvs = sorted(d.glob("*.csv"))
        print(f"[INFO] Found {len(csvs)} CSV(s) in dir: {d}")
        for p in csvs:
            rows = _rows_from_standard_offers_csv(ctx, p)
            print(f"[INFO]   {p.name}: {len(rows)} row(s)")
            rows_all.extend(rows)

    # 2) If OCR mode not none, also run OCR->parse and ingest parsed_week.csv
    parsed_ok = 0
    if args.ocr != "none":
        parsed_csv = run_ocr_and_parse(ctx, args.ocr)
        # parsed_week.csv is NOT the same headers, but your parse script should output item_name/sale_price/etc.
        # If you want OCR rows too, keep using your existing path that already works.
        # For now: we ingest OCR output by reusing the "standard csv" pathway ONLY if it matches.
        #
        # If your parse_offers_week already outputs flyer_items headers, this will work immediately.
        rows = _rows_from_standard_offers_csv(ctx, parsed_csv)
        parsed_ok = len(rows)
        print(f"[INFO] Loaded {len(rows)} row(s) from OCR parsed CSV: {parsed_csv}")
        rows_all.extend(rows)

    if not rows_all:
        print("[WARN] No rows to write.")
        return 0

    if args.write_supabase:
        wrote = supabase_insert_rows("flyer_items", rows_all)
        print(f"[OK] Supabase wrote {wrote}/{len(rows_all)} row(s) into flyer_items")
    else:
        print(f"[INFO] Dry run: would write {len(rows_all)} row(s) into flyer_items")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
