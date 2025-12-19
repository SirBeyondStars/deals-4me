"""
verify_week.py
Deals-4Me – Verify raw flyer files vs DB ingestion for a given week.

- Counts raw media files in flyers/<store>/<weekXX> (raw_pdf/raw_png/snips + loose images/pdfs)
- Counts DB rows in flyer_items for week_code
- Attempts per-store DB counts via flyer_store_id and flyer_stores mapping (store_slug/slug)

Requires env vars:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY  (preferred)
    OR SUPABASE_ANON_KEY

Usage (PowerShell, one line):
  python verify_week.py --flyers-root "C:\...\files_to_run\flyers" --week week50
"""

import argparse
import os
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from supabase import create_client, Client
except Exception as e:
    raise SystemExit(
        "Missing dependency: supabase-py. Install with:\n"
        "  pip install supabase\n"
        f"Details: {e}"
    )

MEDIA_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def get_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    return v


def make_supabase() -> "Client":
    url = get_env("SUPABASE_URL")
    key = get_env("SUPABASE_SERVICE_ROLE_KEY") or get_env("SUPABASE_ANON_KEY")

    if not url or not key:
        raise SystemExit(
            "Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY).\n"
            "Set them in your environment before running verify_week.py."
        )

    return create_client(url, key)


def list_store_dirs(flyers_root: Path) -> List[Path]:
    if not flyers_root.exists():
        raise SystemExit(f"[FATAL] Flyers root does not exist: {flyers_root}")
    return sorted([p for p in flyers_root.iterdir() if p.is_dir() and not p.name.startswith("_")])


def count_raw_files(week_path: Path) -> int:
    """
    Counts raw inputs we consider “ingestable”:
      - any pdf/png/jpg in:
          raw_pdf, raw_png, snips
      - also any pdf/png/jpg directly inside week_path (some stores drop files there)
    """
    if not week_path.exists():
        return 0

    buckets = ["raw_pdf", "raw_png", "snips"]
    candidates: List[Path] = []

    for b in buckets:
        bp = week_path / b
        if bp.exists() and bp.is_dir():
            candidates.extend([p for p in bp.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXTS])

    # loose files directly in week folder
    candidates.extend([p for p in week_path.iterdir() if p.is_file() and p.suffix.lower() in MEDIA_EXTS])

    # de-dupe
    seen = set()
    uniq = []
    for p in candidates:
        rp = str(p.resolve())
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)

    return len(uniq)


def try_load_store_map(sb: "Client") -> Tuple[Dict[int, str], str]:
    """
    Returns (id -> slug/name, note)

    We try:
      flyer_stores(id, store_slug)
      flyer_stores(id, slug)
      flyer_stores(id, name)  (fallback)
    """
    tries = [
        ("store_slug", "flyer_stores(id,store_slug)"),
        ("slug", "flyer_stores(id,slug)"),
        ("name", "flyer_stores(id,name)"),
    ]

    last_err = None
    for col, sel in tries:
        try:
            res = sb.table("flyer_stores").select(f"id,{col}").execute()
            data = res.data or []
            m = {}
            for r in data:
                if r.get("id") is None:
                    continue
                label = r.get(col) or f"id_{r.get('id')}"
                m[int(r["id"])] = str(label)
            if m:
                return m, f"mapped using flyer_stores.{col}"
            return m, f"flyer_stores.{col} returned 0 rows"
        except Exception as e:
            last_err = e

    return {}, f"could not read flyer_stores mapping ({last_err})"


def db_count_total(sb: "Client", week_code: str) -> int:
    """
    Uses count='exact' so we don’t need any columns like created_at.
    """
    res = sb.table("flyer_items").select("id", count="exact").eq("week_code", week_code).execute()
    return int(res.count or 0)


def db_count_by_store_id(sb: "Client", week_code: str) -> Dict[int, int]:
    """
    Pulls flyer_store_id values for the given week and counts in Python.
    (This avoids SQL editor differences + keeps it simple/robust.)
    """
    # If your dataset ever gets huge, we can paginate; for now this is fine for weekly loads.
    res = sb.table("flyer_items").select("flyer_store_id").eq("week_code", week_code).execute()
    rows = res.data or []

    counts: Dict[int, int] = {}
    for r in rows:
        sid = r.get("flyer_store_id")
        if sid is None:
            continue
        sid = int(sid)
        counts[sid] = counts.get(sid, 0) + 1
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flyers-root", required=True, help="Path to flyers root folder")
    ap.add_argument("--week", required=True, help="Week code like week50")
    ap.add_argument("--region", default="NE", help="Region label (for display only)")
    args = ap.parse_args()

    flyers_root = Path(args.flyers_root)
    week_code = args.week.strip()
    region = args.region.strip()

    sb = make_supabase()

    print(f"[INFO] Flyers root: {flyers_root}")
    print(f"[INFO] Region:     {region}")
    print(f"[INFO] Week code:   {week_code}")
    print("")

    store_dirs = list_store_dirs(flyers_root)

    store_id_to_slug, map_note = try_load_store_map(sb)
    print(f"[INFO] Store mapping: {map_note}")
    print("")

    try:
        total_db = db_count_total(sb, week_code)
    except Exception as e:
        print(f"[WARN] Could not count DB total for {week_code}: {e}")
        total_db = -1

    try:
        db_by_sid = db_count_by_store_id(sb, week_code)
    except Exception as e:
        print(f"[WARN] Could not count DB by store for {week_code}: {e}")
        db_by_sid = {}

    print(f"{'Store':<24} {'RawFiles':>8} {'DBRows':>8}  Status")
    print("-" * 70)

    flags = 0
    raw_total = 0
    db_total_from_stores = 0

    for store_dir in store_dirs:
        store = store_dir.name
        week_path = store_dir / week_code

        raw = count_raw_files(week_path)
        raw_total += raw

        # find DB rows for this store (by matching store slug through mapping if possible)
        db_rows = 0
        note = ""

        # If we have mapping, try to reverse-match store name => store_id
        # store_dir is already a slug like "roche_bros"
        store_id = None
        if store_id_to_slug:
            for sid, slug in store_id_to_slug.items():
                if str(slug) == store:
                    store_id = sid
                    break

        if store_id is not None:
            db_rows = db_by_sid.get(store_id, 0)
            db_total_from_stores += db_rows
        else:
            # We can’t map this store => store_id, so we can’t do per-store DB count safely.
            db_rows = 0
            note = "INFO (no store_id match in flyer_stores)"

        status = "OK" if raw > 0 else "NO FILES"
        if raw > 0 and db_rows == 0 and total_db != 0:
            # raw exists but DB shows 0 for this store (or we couldn't map)
            flags += 1
            status = f"{status} ⚠ CHECK"

        print(f"{store:<24} {raw:>8} {db_rows:>8}  {status}{(' | ' + note) if note else ''}")

    print("-" * 70)
    print(f"[TOTAL] Raw files found: {raw_total}")
    if total_db >= 0:
        print(f"[TOTAL] DB rows (week):   {total_db}")
    if db_total_from_stores > 0:
        print(f"[TOTAL] DB rows (sum by store_id matches): {db_total_from_stores}")
    if flags:
        print(f"[TOTAL] RED FLAGS: {flags} store(s) need attention.")
    else:
        print("[TOTAL] No red flags detected based on raw-file presence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
oo