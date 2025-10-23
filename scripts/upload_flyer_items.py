import os
import re
import csv
import json
import time
from pathlib import Path
import requests

# Reads CSVs under flyers/<store>/<week_code>/parsed/*.csv and uploads to Supabase REST
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE = os.environ.get("SUPABASE_SERVICE_ROLE")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE env vars before running.")

REST = SUPABASE_URL.rstrip("/") + "/rest/v1"
HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"  # idempotent-ish inserts
}

ROOT = Path(__file__).resolve().parents[1]  # repo root (deals-4me)
FLYERS = ROOT / "flyers"                    # your actual tree (per your screenshot)

PRICE_PAT = re.compile(r"\$?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d{1,2}))?")
CENTS_PAT = re.compile(r"\b(\d+)\s*¢")

def dollars_to_cents(text: str):
    text = text or ""
    # First see explicit cents like "99¢"
    m = CENTS_PAT.search(text)
    if m:
        try:
            return int(m.group(1))
        except:
            pass
    # Then dollars like $1.99 or 1.99
    m = PRICE_PAT.search(text.replace(",", ""))
    if m:
        try:
            dollars = int(m.group(1))
            cents = int(m.group(2) or 0)
            return dollars * 100 + cents
        except:
            pass
    return None

def row_to_text(row: dict) -> str:
    # Try common text-ish columns and join what we find
    candidates = []
    for key in row.keys():
        lk = key.lower()
        if lk in ("text","raw","line","desc","description","item","name","product","title"):
            v = str(row[key]).strip()
            if v and v.lower() != "nan":
                candidates.append(v)
    if not candidates:
        # fall back to joining all columns
        candidates = [str(v) for v in row.values() if str(v).strip()]
    return " | ".join(candidates)[:2000]  # keep it sane

def row_to_price_cents(row: dict):
    # Prefer explicit numeric price fields if present
    for k in row.keys():
        lk = k.lower()
        if lk in ("price_cents","price_in_cents"):
            try:
                return int(float(row[k]))
            except:
                pass
        if lk in ("price","sale_price","unit_price","final_price"):
            try:
                # could be "1.99" or "$1.99"
                txt = str(row[k]).strip().replace("$","")
                return int(round(float(txt) * 100))
            except:
                pass
    # Otherwise parse any text fields
    joined = " ".join([str(v) for v in row.values() if v is not None])
    return dollars_to_cents(joined)

def collect_csv_files():
    files = []
    if not FLYERS.exists():
        print(f"Folder not found: {FLYERS}")
        return files
    for store_dir in FLYERS.iterdir():
        if not store_dir.is_dir():
            continue
        for week_dir in store_dir.iterdir():
            if not week_dir.is_dir():
                continue
            parsed_dir = week_dir / "parsed"
            if parsed_dir.is_dir():
                for f in parsed_dir.glob("*.csv"):
                    files.append((store_dir.name, week_dir.name, f))
    return files

def upload_rows(table: str, rows: list):
    if not rows:
        return
    url = f"{REST}/{table}"
    # chunk to avoid big payloads
    for i in range(0, len(rows), 500):
        chunk = rows[i:i+500]
        r = requests.post(url, headers=HEADERS, data=json.dumps(chunk))
        if not r.ok:
            print(f"POST {table} failed ({r.status_code}): {r.text[:300]}")
            # brief pause, then try one-by-one to identify bad row
            time.sleep(0.2)
            for row in chunk:
                rr = requests.post(url, headers=HEADERS, data=json.dumps([row]))
                if not rr.ok:
                    print("  Bad row:", row)
                    print("  Error:", rr.status_code, rr.text[:300])
        time.sleep(0.05)

def main():
    files = collect_csv_files()
    if not files:
        print("No CSVs found under flyers/<store>/<week>/parsed/*.csv")
        return

    print(f"Found {len(files)} CSV files.")
    offer_rows = []
    price_rows = []

    for store_slug, week_code, path in files:
        with open(path, newline="", encoding="utf-8", errors="ignore") as fh:
            reader = csv.DictReader(fh)
            # If headerless, wrap using simple reader
            if reader.fieldnames is None:
                fh.seek(0)
                reader = csv.reader(fh)
                for row in reader:
                    text = " | ".join([c for c in row if c])
                    price = dollars_to_cents(text)
                    offer_rows.append({
                        "store_slug": store_slug,
                        "week_code": week_code,
                        "raw_text": text,
                        "price_cents": price
                    })
                    if price is not None:
                        price_rows.append({
                            "canonical_id": None,
                            "store_slug": store_slug,
                            "week_code": week_code,
                            "price_cents": price
                        })
            else:
                for row in reader:
                    text = row_to_text(row)
                    price = row_to_price_cents(row)
                    offer_rows.append({
                        "store_slug": store_slug,
                        "week_code": week_code,
                        "raw_text": text,
                        "price_cents": price
                    })
                    if price is not None:
                        price_rows.append({
                            "canonical_id": None,
                            "store_slug": store_slug,
                            "week_code": week_code,
                            "price_cents": price
                        })

    print(f"Prepared {len(offer_rows)} item_offers rows, {len(price_rows)} price_history rows.")
    upload_rows("item_offers", offer_rows)
    upload_rows("price_history", price_rows)
    print("Done.")
    
if __name__ == "__main__":
    main()
