from __future__ import annotations

print("=== parse_debug_week.py LOADED ===", flush=True)

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple

from price_select import parse_offer_blob_with_reason

SNIP_WS = re.compile(r"\s+")


def looks_like_offer_file(p: Path) -> bool:
    """
    Accept:
      - offer_0001 (no extension)
      - offer_0001.txt
    Reject:
      - *.meta
      - *.json
      - directories
    """
    if not p.is_file():
        return False
    name = p.name.lower()

    if name.endswith(".meta") or name.endswith(".json"):
        return False

    # some folders may contain plain numeric files "1", "2" etc; we can optionally support them later.
    # For now we focus on offer_* because that's what your debug_offers folder shows.
    return name.startswith("offer_")


def find_debug_offer_roots(root: Path) -> List[Path]:
    """
    Find folders named '_debug_offers' anywhere under root.
    If root itself is a _debug_offers folder, return it.
    """
    if root.name.lower() == "_debug_offers":
        return [root]
    return sorted([p for p in root.rglob("_debug_offers") if p.is_dir()])


def find_offer_files_under_debug_root(debug_root: Path) -> List[Path]:
    """
    Find offer files under page_*_offers folders:
      _debug_offers/page_1_offers/offer_0001
      _debug_offers/page_12_offers/offer_0034.txt
    """
    offer_files: List[Path] = []
    for page_dir in sorted([p for p in debug_root.glob("page_*_offers") if p.is_dir()], key=lambda p: p.name):
        for f in sorted(page_dir.iterdir(), key=lambda p: p.name):
            if looks_like_offer_file(f):
                offer_files.append(f)
    return offer_files


def main() -> int:
    print("=== ENTERED main() ===", flush=True)

    ap = argparse.ArgumentParser(
        description="Parse _debug_offers offer blobs into parsed_week.csv with reasons."
    )
    ap.add_argument(
        "--root",
        required=True,
        help="A wk_YYYYMMDD folder OR a store folder OR the _debug_offers folder itself.",
    )
    ap.add_argument(
        "--out",
        default="parsed_week.csv",
        help="Output CSV filename (written into each _debug_offers folder found).",
    )
    ap.add_argument(
        "--snippet-len",
        type=int,
        default=300,
        help="Max characters to keep in snippet column (after whitespace normalization).",
    )

    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Root not found: {root}")

    debug_roots = find_debug_offer_roots(root)
    print(f"[DEBUG] root={root}")
    print(f"[DEBUG] Found {len(debug_roots)} _debug_offers folders")
    for dr in debug_roots:
        print(f"[DEBUG]   {dr}")

    if not debug_roots:
        raise SystemExit(
            f"No _debug_offers folder found under: {root}\n"
            f"Tip: pass your wk_YYYYMMDD folder (e.g. ...\\wk_20251228) or the exports folder."
        )

    fieldnames = [
        "page",
        "file",
        "ok",
        "reason",
        "item_name",
        "sale_price",
        "unit",
        "is_multibuy",
        "multibuy_qty",
        "multibuy_total",
        "confidence",
        "snippet",
    ]

    for debug_root in debug_roots:
        offer_files = find_offer_files_under_debug_root(debug_root)
        print(f"[DEBUG] {debug_root}: offer_files={len(offer_files)}")

        out_path = debug_root / args.out
        rows: List[dict] = []
        total = 0
        ok = 0

        for offer_file in offer_files:
            total += 1
            blob = offer_file.read_text(encoding="utf-8", errors="replace")
            deal, reason = parse_offer_blob_with_reason(blob)

            page_dir = offer_file.parent.name
            file_name = offer_file.name

            snippet = " ".join((blob or "").split())
            if args.snippet_len and args.snippet_len > 0:
                snippet = snippet[: args.snippet_len]

            if deal:
                ok += 1
                rows.append(
                    {
                        "page": page_dir,
                        "file": file_name,
                        "ok": 1,
                        "reason": "ok",
                        "item_name": deal.item_name,
                        "sale_price": f"{deal.sale_price:.2f}",
                        "unit": deal.unit or "",
                        "is_multibuy": int(bool(deal.is_multibuy)),
                        "multibuy_qty": deal.multibuy_qty or "",
                        "multibuy_total": f"{deal.multibuy_total:.2f}" if deal.multibuy_total else "",
                        "confidence": deal.confidence,
                        "snippet": snippet,
                    }
                )
            else:
                rows.append(
                    {
                        "page": page_dir,
                        "file": file_name,
                        "ok": 0,
                        "reason": reason,
                        "item_name": "",
                        "sale_price": "",
                        "unit": "",
                        "is_multibuy": "",
                        "multibuy_qty": "",
                        "multibuy_total": "",
                        "confidence": "",
                        "snippet": snippet,
                    }
                )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

        print(f"Wrote: {out_path}")
        print(f"Total: {total} | OK: {ok} | Failed: {total - ok}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
