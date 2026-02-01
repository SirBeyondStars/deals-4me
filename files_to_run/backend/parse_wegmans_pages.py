# parse_wegmans_pages.py
# Purpose:
#   Convert Wegmans "Flyer page N" OCR blob rows (stored in flyer_items) into
#   usable item rows with item_name + prices.
#
# Usage:
#   python parse_wegmans_pages.py --week week51 --dry-run
#   python parse_wegmans_pages.py --week week51 --wipe-parsed --limit-pages 13
#
# Required env vars:
#   SUPABASE_URL
#   SUPABASE_SERVICE_ROLE_KEY   (recommended) OR SUPABASE_ANON_KEY

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests


TABLE_FLYER_ITEMS = "flyer_items"
BRAND = "Wegmans"


@dataclass
class PageBlob:
  id: int
  item_name: str
  source_file: Optional[str]
  ocr_text: str


@dataclass
class ParsedItem:
  item_name: str
  sale_price: Optional[float]
  regular_price: Optional[float]
  size: Optional[str]
  unit: Optional[str]
  source_file: Optional[str]
  ocr_text: Optional[str]
  item_key: str


def die(msg: str, code: int = 1) -> None:
  print(msg, file=sys.stderr)
  raise SystemExit(code)


def get_env(name: str) -> str:
  v = os.getenv(name, "").strip()
  if not v:
    die(f"Missing required env var: {name}")
  return v


def sb_headers() -> dict:
  key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_ANON_KEY", "").strip()
  if not key:
    die("Missing SUPABASE_SERVICE_ROLE_KEY (preferred) or SUPABASE_ANON_KEY")
  return {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
    "Accept": "application/json",
  }


def sb_rest_url(path: str) -> str:
  base = get_env("SUPABASE_URL").rstrip("/")
  return f"{base}/rest/v1/{path.lstrip('/')}"


def fetch_page_blobs(week_code: str, limit_pages: int) -> List[PageBlob]:
  # Pull only the page-blob rows
  params = {
    "select": "id,item_name,source_file,ocr_text",
    "brand": f"eq.{BRAND}",
    "week_code": f"eq.{week_code}",
    "item_name": "ilike.Flyer page%",
    "order": "id.asc",
    "limit": str(limit_pages),
  }

  r = requests.get(sb_rest_url(TABLE_FLYER_ITEMS), headers=sb_headers(), params=params, timeout=60)
  if r.status_code >= 300:
    die(f"[fetch] Supabase error {r.status_code}: {r.text}")

  rows = r.json() or []
  blobs: List[PageBlob] = []
  for row in rows:
    blobs.append(
      PageBlob(
        id=int(row["id"]),
        item_name=str(row.get("item_name") or ""),
        source_file=row.get("source_file"),
        ocr_text=str(row.get("ocr_text") or ""),
      )
    )
  return blobs


def wipe_parsed_rows(week_code: str) -> int:
  # Delete previously-parsed rows for the brand/week, but keep the page blobs.
  # "Parsed" rows are anything NOT "Flyer page %".
  params = {
    "brand": f"eq.{BRAND}",
    "week_code": f"eq.{week_code}",
    "item_name": "not.ilike.Flyer page%",
  }
  r = requests.delete(sb_rest_url(TABLE_FLYER_ITEMS), headers=sb_headers(), params=params, timeout=60)
  if r.status_code >= 300:
    die(f"[wipe] Supabase error {r.status_code}: {r.text}")
  return 0


# ---------- Parsing + Confidence heuristics ----------

# Price tokens:
# - $5.79 / 5.79
# - $5 / 5 (optional decimals; filtered by confidence rules later)
PRICE_RE = re.compile(
  r"""
  (?:
    \$\s*(\d{1,3}(?:\.\d{1,2})?)      # $5.79 or $5
    |
    (?<!\d)(\d{1,3}(?:\.\d{1,2})?)(?!\d)   # 5.79 or 5
  )
  """,
  re.VERBOSE,
)

# Multi-buy like 2/$5, 3/$10
MULTIBUY_RE = re.compile(r"(?i)\b(\d+)\s*/\s*\$?\s*(\d{1,3}(?:\.\d{1,2})?)\b")

UNIT_RE = re.compile(r"\b(ea|each|lb|/lb|ct|oz|fl\.?\s*oz)\b", re.IGNORECASE)

BAD_NAME_RE = re.compile(
  r"""
  ^\s*(
    shop\b|holiday\b|ideas\b|bakery\b|seafood\b|cheese\b|charcuterie\b|
    produce\b|floral\b|wine\b|beer\b|spirits\b|new\s+item\b
  )\s*$
  """,
  re.IGNORECASE | re.VERBOSE,
)

JUST_SIZE_RE = re.compile(
  r"^\s*(avg\.\s*)?\d+(\.\d+)?\s*(lb|lbs|oz|ounce|fl\.?\s*oz|ct)\.?\s*$",
  re.IGNORECASE,
)

HEADERISH_PATTERNS = [
  r"^\s*shop\s+holiday",
  r"^\s*wegmans\s*(ultimate)?\s*$",
  r"^\s*(bakery|produce|seafood|meat|deli|floral|frozen|pantry|beverages?)\s*$",
  r"^\s*(new|sale|specials?)\s*$",
  r"^\s*(price|prices?)\s*$",
]

BAD_NAME_TOKENS = {
  "wegmans", "ultimate", "shop", "holiday", "save", "special", "specials",
  "club", "member", "members", "digital", "coupon", "coupons",
  "limited", "time", "offer", "offers",
}

PER_LB_HINTS = [
  "/lb", "per lb", "lb.", "lb ", "lbs", "pound", "per pound", "avg", "avg.",
  "price per lb", "price/lb"
]


def normalize_space(s: str) -> str:
  return re.sub(r"\s+", " ", (s or "").strip())


def _looks_like_header(name: str) -> bool:
  s = normalize_space(name).lower()
  if not s:
    return True
  if BAD_NAME_RE.match(s):
    return True
  for pat in HEADERISH_PATTERNS:
    if re.search(pat, s):
      return True
  return False


def _name_quality(name: str) -> Tuple[bool, str]:
  raw = normalize_space(name)
  if not raw:
    return False, "empty_name"
  if _looks_like_header(raw):
    return False, "headerish_name"
  if JUST_SIZE_RE.match(raw):
    return False, "just_size_line"

  letters = sum(ch.isalpha() for ch in raw)
  if letters < 6:
    return False, "too_few_letters"

  words = [w for w in re.split(r"\s+", raw.lower()) if w]
  if len(words) < 2 and letters < 10:
    return False, "too_short_single_word"

  nonspace = [ch for ch in raw if not ch.isspace()]
  if nonspace:
    alpha_ratio = sum(ch.isalpha() for ch in nonspace) / max(1, len(nonspace))
    if alpha_ratio < 0.35:
      return False, "low_alpha_ratio"

  toks = re.findall(r"[a-z]+", raw.lower())
  if toks:
    bad = sum(1 for t in toks if t in BAD_NAME_TOKENS)
    if bad / len(toks) >= 0.6:
      return False, "mostly_bad_tokens"

  return True, "ok"


def _extract_first_price_value(text: str) -> Optional[float]:
  if not text:
    return None
  t = text.replace(",", "").strip()
  m = PRICE_RE.search(t)
  if not m:
    return None
  s = m.group(1) or m.group(2)
  try:
    return float(s)
  except Exception:
    return None


def _has_per_lb_context(name: str, line: str) -> bool:
  blob = f"{name} {line}".lower()
  return any(h in blob for h in PER_LB_HINTS)


def _has_multibuy_context(line: str) -> bool:
  return bool(MULTIBUY_RE.search(line or ""))


def _price_quality(name: str, line: str, price_val: Optional[float]) -> Tuple[bool, str]:
  if _has_multibuy_context(line):
    # Multi-buy is allowed even if the number looks “weird” — it's usually legit promo text.
    return True, "multibuy"

  if price_val is None:
    return False, "no_price_value"

  # Hard reject tiny junk like 0.01
  if price_val <= 0.05:
    return False, "price_too_small"

  per_lb = _has_per_lb_context(name, line)

  # Very large values are nearly always OCR junk, unless per-lb context exists
  if price_val >= 200:
    if per_lb:
      return True, "high_price_allowed_per_lb"
    return False, "price_too_large"

  # Without per-lb context, $50+ is usually not a flyer item (party trays exist, but rare).
  if price_val >= 50 and not per_lb:
    return False, "price_implausible_without_context"

  return True, "ok"


def pick_name(window_lines: List[str]) -> Optional[str]:
  # pick the best line that looks like a product name (not just size/category)
  candidates = []
  for raw in window_lines:
    t = normalize_space(raw)
    if not t:
      continue
    if BAD_NAME_RE.match(t):
      continue
    if JUST_SIZE_RE.match(t):
      continue
    alpha = sum(ch.isalpha() for ch in t)
    if alpha < 3:
      continue
    candidates.append(t)

  if not candidates:
    return None

  candidates.sort(key=len, reverse=True)
  return candidates[0][:120]


def parse_page_blob(blob: PageBlob, skip_reasons: Dict[str, int]) -> List[ParsedItem]:
  text = blob.ocr_text or ""
  if len(text.strip()) < 20:
    return []

  lines = [l.strip() for l in text.splitlines()]
  out: List[ParsedItem] = []

  for i, line in enumerate(lines):
    if not line:
      continue

    # Find either a normal price or a multibuy token on this line
    multibuy_m = MULTIBUY_RE.search(line)
    price_m = PRICE_RE.search(line)

    if not multibuy_m and not price_m:
      continue

    # Determine sale_price:
    # - for multibuy: store the total promo price (e.g., 2/$5 -> 5.00)
    # - else: store the parsed numeric
    sale_price: Optional[float] = None
    if multibuy_m:
      try:
        sale_price = float(multibuy_m.group(2))
      except Exception:
        sale_price = None
    else:
      sale_price = _extract_first_price_value(line)

    # unit + size guess from same line
    unit = None
    um = UNIT_RE.search(line)
    if um:
      unit = um.group(1).lower().replace("each", "ea")

    size = None
    size_m = re.search(r"\b(avg\.\s*)?\d+(\.\d+)?\s*(lb|lbs|oz|ct|fl\.?\s*oz)\b", line, re.IGNORECASE)
    if size_m:
      size = normalize_space(size_m.group(0))

    # name comes from nearby lines (1-3 lines above, plus same line)
    window = []
    for j in range(max(0, i - 3), i + 1):
      window.append(lines[j])

    name = pick_name(window)
    if not name:
      skip_reasons["no_name"] = skip_reasons.get("no_name", 0) + 1
      continue

    # ---------- CONFIDENCE FILTER ----------
    ok_name, r1 = _name_quality(name)
    if not ok_name:
      skip_reasons[r1] = skip_reasons.get(r1, 0) + 1
      continue

    ok_price, r2 = _price_quality(name, line, sale_price)
    if not ok_price:
      skip_reasons[r2] = skip_reasons.get(r2, 0) + 1
      continue
    # ---------------------------------------

    # Create item_key for de-dupe
    key_src = f"{BRAND}|{name}|{(sale_price or 0.0):.2f}|{blob.source_file or ''}"
    item_key = hashlib.md5(key_src.encode("utf-8")).hexdigest()

    # Keep a short OCR snippet for debugging
    snippet = "\n".join(window[-4:])[:500]

    out.append(
      ParsedItem(
        item_name=name,
        sale_price=sale_price,
        regular_price=None,
        size=size,
        unit=unit,
        source_file=blob.source_file,
        ocr_text=snippet,
        item_key=item_key,
      )
    )

  # basic de-dupe within a page blob
  seen = set()
  deduped: List[ParsedItem] = []
  for it in out:
    if it.item_key in seen:
      continue
    seen.add(it.item_key)
    deduped.append(it)

  return deduped


def insert_items(week_code: str, items: List[ParsedItem], dry_run: bool) -> int:
  if not items:
    return 0

  payload = []
  for it in items:
    payload.append(
      {
        "brand": BRAND,
        "week_code": week_code,
        "item_name": it.item_name,
        "sale_price": it.sale_price,
        "regular_price": it.regular_price,
        "size": it.size,
        "unit": it.unit,
        "source_file": it.source_file,
        "ocr_text": it.ocr_text,
        "item_key": it.item_key,
      }
    )

  if dry_run:
    return len(payload)

  r = requests.post(sb_rest_url(TABLE_FLYER_ITEMS), headers=sb_headers(), json=payload, timeout=120)
  if r.status_code >= 300:
    die(f"[insert] Supabase error {r.status_code}: {r.text}")

  return len(payload)


def main() -> None:
  ap = argparse.ArgumentParser()
  ap.add_argument("--week", required=True, help="week code, e.g. week51")
  ap.add_argument("--dry-run", action="store_true", help="don’t insert, just report")
  ap.add_argument("--wipe-parsed", action="store_true", help="delete prior parsed rows for this brand/week (keeps Flyer page blobs)")
  ap.add_argument("--limit-pages", type=int, default=50, help="max Flyer page blobs to read")
  args = ap.parse_args()

  week_code = args.week.strip()
  if not week_code:
    die("Invalid --week")

  print(f"[parse] Fetching {BRAND} flyer page blobs for week_code={week_code}...")

  if args.wipe_parsed:
    print("[wipe] Deleting prior parsed rows (keeping Flyer page blobs)...")
    wipe_parsed_rows(week_code)

  blobs = fetch_page_blobs(week_code, args.limit_pages)
  if not blobs:
    print("[parse] No flyer page rows found. Nothing to do.")
    return

  print(f"[parse] Found {len(blobs)} flyer page rows.")

  total_candidates = 0
  total_inserted = 0
  skip_reasons: Dict[str, int] = {}

  for blob in blobs:
    items = parse_page_blob(blob, skip_reasons)
    total_candidates += len(items)

    inserted = insert_items(week_code, items, args.dry_run)
    total_inserted += inserted

    label = "[dry-run]" if args.dry_run else "[insert]"
    sf = blob.source_file or "(no source_file)"
    print(f"{label} page_id={blob.id} source_file={os.path.basename(sf)} -> {inserted} items")

  print("\n[done] Summary")
  print(f"  pages_scanned:      {len(blobs)}")
  print(f"  candidates_found:   {total_candidates}")
  print(f"  inserted_rows:      {0 if args.dry_run else total_inserted} ({total_inserted} planned)")

  if skip_reasons:
    print("\n[filter] Skipped rows by reason (top 15):")
    top = sorted(skip_reasons.items(), key=lambda kv: kv[1], reverse=True)[:15]
    for k, v in top:
      print(f"  {k:30s} {v}")


if __name__ == "__main__":
  main()
