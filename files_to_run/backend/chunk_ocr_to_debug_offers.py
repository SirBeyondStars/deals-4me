from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple, Set


# ---------- Tunables ----------
JUNK_EXACT = {
    "add to cart",
    "regular prices vary",
}

VALID_RE = re.compile(r"^\s*valid\s+\d{1,2}/\d{1,2}\s*-\s*\d{1,2}/\d{1,2}", re.IGNORECASE)
WS_RE = re.compile(r"\s+")
DIGIT_RE = re.compile(r"\d")
PCT_OR_PRIME_RE = re.compile(r"(%\s*off|\bprime\b)", re.IGNORECASE)

# Store profiles (store slug based, not region)
ALDI_LIKE_STORES = {"aldi"}

# IMPORTANT:
# Aldi OCR often turns "6.97" into "6 97" or "6 . 97" or "97c"
# We include those variants here.
PRICE_TOKEN_RE = re.compile(
    r"("
    r"\$?\s*\d+\s*\.\s*\d{2}"          # 6.97, 6 . 97, $6.97
    r"|"
    r"\$?\s*\d{1,3}\s+\d{2}\b"         # 6 97  (OCR space вместо dot)
    r"|"
    r"\b\d+\s*(?:¢|c)\b"              # 97¢, 97c
    r"|"
    r"\b\d+\s*/\s*\$?\s*\d+(?:\s*\.\s*\d{2}|\s+\d{2})?\b"  # 2/$5, 2/5, 2/$5.00, 2/5 00
    r"|"
    r"/\s*(?:lb|ib)\b"                # /lb or OCR /ib
    r")",
    re.IGNORECASE,
)


def norm_line(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = s.strip()
    s = WS_RE.sub(" ", s)
    return s


def clean_lines(text: str) -> List[str]:
    out: List[str] = []
    for raw in text.splitlines():
        t = norm_line(raw)
        if not t:
            out.append("")  # keep blanks for chunking
            continue
        if t.lower() in JUNK_EXACT:
            continue
        out.append(t)

    # collapse multiple blanks
    collapsed: List[str] = []
    blank = 0
    for t in out:
        if t == "":
            blank += 1
            if blank <= 1:
                collapsed.append("")
        else:
            blank = 0
            collapsed.append(t)

    # trim leading/trailing blanks
    while collapsed and collapsed[0] == "":
        collapsed.pop(0)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()

    return collapsed


def split_blocks(lines: List[str]) -> List[List[str]]:
    blocks: List[List[str]] = []
    cur: List[str] = []
    for t in lines:
        if t == "":
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append(t)
    if cur:
        blocks.append(cur)
    return blocks


def block_text(block: List[str]) -> str:
    return " ".join(block).strip()


def has_price_token(text: str) -> bool:
    return bool(PRICE_TOKEN_RE.search((text or "").strip()))


def has_any_digits(text: str) -> bool:
    return bool(DIGIT_RE.search(text or ""))


def has_pct_or_prime(text: str) -> bool:
    return bool(PCT_OR_PRIME_RE.search(text or ""))


def should_keep_block(block: List[str], min_len: int) -> bool:
    joined = block_text(block)

    # drop blocks that are basically only "Valid ..." repeated
    non_valid = [x for x in block if not VALID_RE.match(x)]
    if len(non_valid) == 0:
        return has_price_token(joined)

    if len(joined) < min_len:
        return False

    return True


def is_merge_target(block: List[str]) -> bool:
    txt = block_text(block)
    if not txt:
        return False
    if has_price_token(txt):
        return True
    return has_any_digits(txt)


def needs_price_rescue(block: List[str]) -> bool:
    txt = block_text(block)
    if not txt:
        return True
    if has_price_token(txt):
        return False
    return has_pct_or_prime(txt)


def page_sort_key(p: Path) -> Tuple[int, str]:
    if p.stem.isdigit():
        return (0, f"{int(p.stem):06d}")
    return (1, p.stem)


def _clear_offer_files(page_dir: Path) -> None:
    for old in page_dir.glob("offer_*.txt"):
        try:
            old.unlink()
        except Exception:
            pass


def _write_offer_files(page_dir: Path, chunks: List[str]) -> int:
    _clear_offer_files(page_dir)

    kept = 0
    for chunk in chunks:
        kept += 1
        out_txt = page_dir / f"offer_{kept:04d}.txt"
        out_txt.write_text(chunk.strip() + "\n", encoding="utf-8")
    return kept


def _fallback_price_windows(text: str, before: int, after: int) -> List[str]:
    """
    Build chunks by taking windows around each PRICE_TOKEN_RE hit.
    Robust for Aldi-like OCR where blank lines don't segment offers.
    """
    if not text:
        return []

    t = text.replace("\u00a0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    hits = list(PRICE_TOKEN_RE.finditer(t))
    if not hits:
        return []

    windows: List[Tuple[int, int]] = []
    for m in hits:
        s = max(0, m.start() - before)
        e = min(len(t), m.end() + after)
        windows.append((s, e))

    # Merge overlapping windows (reduce duplicates)
    windows.sort()
    merged: List[Tuple[int, int]] = []
    for s, e in windows:
        if not merged:
            merged.append((s, e))
            continue
        ps, pe = merged[-1]
        if s <= pe + 30:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))

    chunks: List[str] = []
    for s, e in merged:
        chunk = t[s:e].strip()
        if len(chunk) < 18:
            continue
        chunks.append(chunk)

    return chunks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-root", required=True, help=r"Path like flyers\NE\whole_foods\wk_20251228")
    ap.add_argument("--brand", default="", help="Store slug (e.g. aldi). Used for chunking profile selection.")
    ap.add_argument("--out-debug-root", default="", help=r"Default: <week-root>\exports\_debug_offers")

    # default chunking controls
    ap.add_argument("--min-block-len", type=int, default=25)
    ap.add_argument("--merge-lookahead", type=int, default=2)

    # fallback controls
    ap.add_argument("--fallback-min-offers", type=int, default=10)
    ap.add_argument("--fallback-before", type=int, default=160)
    ap.add_argument("--fallback-after", type=int, default=260)

    args = ap.parse_args()

    week_root = Path(args.week_root)
    if not week_root.exists():
        print(f"[ERROR] week-root not found: {week_root}")
        return 2

    brand = (args.brand or "").strip().lower()

    ocr_dir = week_root / "ocr"
    if not ocr_dir.exists():
        print(f"[ERROR] OCR dir not found: {ocr_dir}")
        return 2

    exports = week_root / "exports"
    exports.mkdir(parents=True, exist_ok=True)

    debug_root = Path(args.out_debug_root) if args.out_debug_root else (exports / "_debug_offers")
    debug_root.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(ocr_dir.glob("*.txt"), key=page_sort_key)
    if not txt_files:
        print(f"[WARN] No OCR txt files in: {ocr_dir}")
        return 0

    pages = 0
    offers = 0

    for txt in txt_files:
        pages += 1
        page_id = txt.stem if txt.stem else "page"
        page_dir = debug_root / f"page_{page_id}_offers"
        page_dir.mkdir(parents=True, exist_ok=True)

        raw_text = txt.read_text(encoding="utf-8", errors="replace")
        lines = clean_lines(raw_text)
        blocks = split_blocks(lines)

        used: Set[int] = set()
        chunks_normal: List[str] = []

        # ---- NORMAL mode: blank-line blocks + rescue merge ----
        for i, b in enumerate(blocks):
            if i in used:
                continue

            if not should_keep_block(b, args.min_block_len):
                continue

            merged_lines = list(b)

            # Rescue merge if promo-ish and lacks a price token
            if needs_price_rescue(b):
                for k in range(1, args.merge_lookahead + 1):
                    j = i + k
                    if j >= len(blocks) or j in used:
                        continue
                    nb = blocks[j]
                    if not is_merge_target(nb):
                        continue

                    merged_lines.append("")
                    merged_lines.extend(nb)
                    used.add(j)

                    merged_txt = block_text([ln for ln in merged_lines if ln != ""])
                    if has_price_token(merged_txt):
                        break

            chunk = "\n".join([ln for ln in merged_lines if ln is not None]).strip()
            if chunk:
                chunks_normal.append(chunk)

            used.add(i)

        kept_normal = _write_offer_files(page_dir, chunks_normal)

        # ---- FALLBACK mode: price-token windows (Aldi-like) ----
        if brand in ALDI_LIKE_STORES and kept_normal < args.fallback_min_offers:
            chunks_fb = _fallback_price_windows(
                raw_text,
                before=args.fallback_before,
                after=args.fallback_after,
            )
            if chunks_fb:
                kept_fb = _write_offer_files(page_dir, chunks_fb)
                offers += kept_fb
                print(
                    f"[OK] page {page_id}: blocks={len(blocks)} normal={kept_normal} "
                    f"fallback={kept_fb} brand={brand} -> {page_dir}"
                )
                continue

        offers += kept_normal
        print(
            f"[OK] page {page_id}: blocks={len(blocks)} kept={kept_normal} mode=normal brand={brand} -> {page_dir}"
        )

    print("[DONE]")
    print(f"  week_root:   {week_root}")
    print(f"  debug_root:  {debug_root}")
    print(f"  brand:       {brand}")
    print(f"  pages:       {pages}")
    print(f"  offers:      {offers}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
