# upload_flyer_weeks.py
from pathlib import Path
import os
from supabase import create_client, Client

# ---- Config (adjust path if yours is different)
FLYERS_ROOT = Path(r"C:\Users\jwein\OneDrive\Desktop\deals-4me\flyers")

# Canonical store folders we care about (add more as you ingest them)
STORES = [
    "stop_and_shop",       # has region.txt per week (MA/CT/RI)
    "shaws",
    "market_basket",
    "aldi",
    "big_y",
    "hannaford",
    "price_chopper_market_32",
    "pricerite",
    "roche_bros",
    "whole_foods",
]

def read_region(week_dir: Path):
    p = week_dir / "region.txt"
    if p.exists():
        val = p.read_text(encoding="utf-8", errors="ignore").strip().upper()
        return val if val in {"MA", "CT", "RI"} else None
    return None

def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE")
    if not url or not key:
        raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE env vars before running.")

    supabase: Client = create_client(url, key)

    if not FLYERS_ROOT.exists():
        raise SystemExit(f"Flyers folder not found: {FLYERS_ROOT}")

    total = 0
    for store in STORES:
        store_dir = FLYERS_ROOT / store
        if not store_dir.exists():
            continue
        week_dirs = [p for p in store_dir.iterdir() if p.is_dir()]
        for w in sorted(week_dirs, key=lambda p: p.name):
            region = read_region(w)  # may be None for chains without regions
            payload = {
                "store_slug": store,
                "week_code": w.name,   # e.g., 101625
                "region": region,      # can be None
            }
            upsert_offers_and_history(supabase, rows_to_insert)

            print(f"Upserted {store}/{w.name} (region={region or 'NULL'})")
            total += 1

    print(f"Done. {total} rows upserted.")
def upsert_offers_and_history(supabase, rows):
    """Insert clean offers and also append to price history."""
    if not rows:
        print("No rows to insert.")
        return

    # 1) Insert normalized offers
    supabase.table("item_offers").insert(rows).execute()

    # 2) Append skinny records to price history
    hist = []
    for r in rows:
        hist.append({
            "canonical_id": r.get("canonical_id"),   # ok if None
            "store_slug": r["store_slug"],
            "week_code": r["week_code"],
            "region": r.get("region"),
            "item_name": r["item_name"],
            "price_cents": int(r["price_cents"]),
        })
    supabase.table("price_history").insert(hist).execute()

    print(f"Inserted {len(rows)} offers and {len(hist)} history records.")


if __name__ == "__main__":
    main()
