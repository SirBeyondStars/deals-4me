# files_to_run/backend/convert_manual_excel_to_csv.py
# Convert a manual Whole Foods (or any store) .xlsx into a CSV inside manual_imports/csv
# Designed to be resilient to "messy" headers.

import argparse
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

import pandas as pd


STD_HEADERS = [
    "item_name",
    "week_code",
    "percent_off_prime",
    "percent_off_nonprime",
    "promo_start",
    "promo_end",
    "manual_review_reason",
    "source_file",
    # optional debug-ish fields (kept if present)
    "raw_text",
]


def _clean_col(c: str) -> str:
    c = str(c or "").strip().lower()
    c = re.sub(r"\s+", "_", c)
    c = re.sub(r"[^a-z0-9_]+", "", c)
    return c


def _find_col(cols: List[str], patterns: List[str]) -> Optional[str]:
    for p in patterns:
        rx = re.compile(p)
        for c in cols:
            if rx.search(c):
                return c
    return None


def _to_date(v) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.date().isoformat()
    s = str(v).strip()
    if not s:
        return None
    # try common formats
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%b %d %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True, help="Path to .xlsx file")
    ap.add_argument("--region", required=True, help="Region code, e.g. ne")
    ap.add_argument("--store", required=True, help="Store slug, e.g. whole_foods")
    ap.add_argument("--week", required=True, help="Week code, e.g. wk_20260118")
    ap.add_argument("--outdir", required=True, help="Output directory (manual_imports/csv)")
    args = ap.parse_args()

    xlsx_path = args.xlsx
    week_code = args.week
    outdir = args.outdir

    os.makedirs(outdir, exist_ok=True)

    # Read first sheet by default
    df = pd.read_excel(xlsx_path, sheet_name=0, engine="openpyxl")

    # Normalize column names
    df.columns = [_clean_col(c) for c in df.columns]

    cols = list(df.columns)

    # Heuristic mappings
    col_item = _find_col(cols, [r"^item$", r"item_name", r"product", r"description", r"^name$"])
    col_prime = _find_col(cols, [r"prime", r"percent_off_prime", r"prime_discount"])
    col_nonprime = _find_col(cols, [r"nonprime", r"percent_off_nonprime", r"non_prime"])
    col_start = _find_col(cols, [r"promo_start", r"start_date", r"^start$", r"begins"])
    col_end = _find_col(cols, [r"promo_end", r"end_date", r"^end$", r"expires"])
    col_raw = _find_col(cols, [r"raw_text", r"raw", r"notes", r"details", r"offer", r"deal"])

    out = pd.DataFrame()

    # Always produce something usable
    if col_item:
        out["item_name"] = df[col_item].astype(str).str.strip()
    else:
        # fallback: combine first non-empty text-ish columns
        text_cols = [c for c in cols if "price" not in c and "cost" not in c and "qty" not in c]
        use = text_cols[:2] if text_cols else cols[:1]
        out["item_name"] = df[use].astype(str).agg(" ".join, axis=1).str.strip()

    out["week_code"] = week_code

    def coerce_pct(series):
        # allow "10", "10%", 0.10, etc.
        s = series.copy()
        s = s.apply(lambda v: None if pd.isna(v) else v)
        def one(v):
            if v is None:
                return None
            if isinstance(v, (int, float)) and pd.notna(v):
                # if it's 0-1 treat as fraction
                if 0 <= float(v) <= 1:
                    return int(round(float(v) * 100))
                return int(round(float(v)))
            t = str(v).strip().replace("%", "")
            if not t:
                return None
            try:
                f = float(t)
                if 0 <= f <= 1:
                    return int(round(f * 100))
                return int(round(f))
            except Exception:
                return None
        return s.apply(one)

    out["percent_off_prime"] = coerce_pct(df[col_prime]) if col_prime else None
    out["percent_off_nonprime"] = coerce_pct(df[col_nonprime]) if col_nonprime else None

    out["promo_start"] = df[col_start].apply(_to_date) if col_start else None
    out["promo_end"] = df[col_end].apply(_to_date) if col_end else None

    out["manual_review_reason"] = "manual_excel_import"
    out["source_file"] = os.path.basename(xlsx_path)

    if col_raw:
        out["raw_text"] = df[col_raw].astype(str).str.strip()

    # Drop empty item_name rows
    out["item_name"] = out["item_name"].fillna("").astype(str).str.strip()
    out = out[out["item_name"] != ""].copy()

    # Write CSV
    base = os.path.splitext(os.path.basename(xlsx_path))[0]
    out_csv = os.path.join(outdir, f"{base}.csv")
    out.to_csv(out_csv, index=False, encoding="utf-8")

    print(f"[OK] Wrote: {out_csv} ({len(out)} rows)")


if __name__ == "__main__":
    main()
