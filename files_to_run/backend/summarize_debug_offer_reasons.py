from __future__ import annotations

from pathlib import Path
from collections import Counter

# IMPORTANT: adjust this import to match where parse_offer_blob_with_reason lives.
# In your repo it should be in files_to_run/backend/price_select.py
from price_select import parse_offer_blob_with_reason  # type: ignore


def main():
    week_root = Path(r".\flyers\NE\whole_foods\wk_20251228")
    debug_root = week_root / "exports" / "_debug_offers"

    if not debug_root.exists():
        print(f"[ERROR] Debug root not found: {debug_root}")
        return

    txts = list(debug_root.rglob("*.txt"))
    print(f"[INFO] Found {len(txts)} offer txt files under {debug_root}")

    reasons = Counter()
    examples = {}

    for p in txts:
        try:
            blob = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            blob = ""

        deal, reason = parse_offer_blob_with_reason(blob)
        reasons[reason] += 1

        # keep 1 example per reason
        if reason not in examples:
            examples[reason] = p.as_posix()

    print("\n=== Reason counts ===")
    for k, v in reasons.most_common():
        print(f"{v:5d}  {k}")

    print("\n=== One example file per reason ===")
    for k, v in sorted(examples.items(), key=lambda kv: (-reasons[kv[0]], kv[0])):
        print(f"{k:20s}  {v}")


if __name__ == "__main__":
    main()
