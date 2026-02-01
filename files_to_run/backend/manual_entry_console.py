from __future__ import annotations

import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MANUAL_NEEDED = BASE_DIR / "manual_ocr_needed.csv"
MANUAL_ITEMS_OUT = BASE_DIR / "manual_item_entries.csv"


def read_manual_needed():
    if not MANUAL_NEEDED.exists():
        print(f"[manual] Not found: {MANUAL_NEEDED}")
        return []
    with MANUAL_NEEDED.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_manual_item(row: dict, item_name: str, price_text: str):
    new_file = not MANUAL_ITEMS_OUT.exists()
    out_row = {
        "timestamp_utc": row.get("timestamp_utc", ""),
        "store_id": row.get("store_id", ""),
        "week_code": row.get("week_code", ""),
        "source_file": row.get("source_file", ""),
        "item_name": item_name.strip(),
        "price_text": price_text.strip(),  # allows "2/$5", "$1.99/lb", etc.
        "notes": row.get("reason", ""),
    }

    with MANUAL_ITEMS_OUT.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_row.keys()))
        if new_file:
            w.writeheader()
        w.writerow(out_row)


def main():
    rows = read_manual_needed()
    if not rows:
        print("[manual] Nothing in manual_ocr_needed.csv yet.")
        return

    print("\nManual OCR Needed Queue:\n")
    for i, r in enumerate(rows, start=1):
        store = r.get("store_id", "?")
        week = r.get("week_code", "?")
        src = Path(r.get("source_file", "")).name
        print(f"{i:>3}. {store} | {week} | {src}")

    sel = input("\nPick a row number to enter manually (or blank to exit): ").strip()
    if not sel:
        return

    idx = int(sel) - 1
    if idx < 0 or idx >= len(rows):
        print("[manual] Invalid selection.")
        return

    chosen = rows[idx]
    print("\nSelected:")
    print(f"  store_id:   {chosen.get('store_id')}")
    print(f"  week_code:  {chosen.get('week_code')}")
    print(f"  source_file:{chosen.get('source_file')}\n")

    item_name = input("Item name (e.g., Dragonfruit): ").strip()
    price_text = input("Price (e.g., 2/$5 or 1.99): ").strip()

    if not item_name or not price_text:
        print("[manual] Item name and price are required.")
        return

    append_manual_item(chosen, item_name, price_text)
    print(f"\n✅ Saved manual entry to: {MANUAL_ITEMS_OUT}")


if __name__ == "__main__":
    main()
