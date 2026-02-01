from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple


# -----------------------------
# Regex helpers
# -----------------------------
RE_PRICE = re.compile(r"\$\s*(\d{1,3}(?:\.\d{2})?)")  # "$6.99"
RE_RANGE = re.compile(r"\$\s*(\d{1,3}(?:\.\d{2})?)\s*[-–]\s*\$\s*(\d{1,3}(?:\.\d{2})?)")
RE_PERCENT = re.compile(r"(\d{1,2})\s*%")
RE_OFF_WORD = re.compile(r"\boff\b", re.IGNORECASE)
RE_WITH_PRIME = re.compile(r"\bwith\s+prime\b", re.IGNORECASE)

RE_PER_LB = re.compile(r"(/\s*lb\b|\bper\s*lb\b)", re.IGNORECASE)
RE_PER_OZ = re.compile(r"(/\s*oz\b|\bper\s*oz\b)", re.IGNORECASE)

RE_MULTI_BUY = re.compile(r"\b(\d+)\s*(for|/)\s*\$\s*(\d{1,3}(?:\.\d{2})?)\b", re.IGNORECASE)  # "2 for $5.00"

RE_SPLITORS = re.compile(r"\s*(?:,|\bor\b|/|;|\+|\band\b)\s*", re.IGNORECASE)

STOP_PHRASES = [
    "with prime",
    "prime member",
    "member price",
    "save",
    "off",
    "deal",
    "limit",
    "excludes",
    "selected",
    "select varieties",
    "while supplies last",
]

IMAGE_NOISE_PAT = re.compile(r"^[^A-Za-z0-9]*$")


def normalize_text(s: str) -> str:
    s = s.replace("\u2013", "-").replace("\u2014", "-")  # en/em dash
    s = re.sub(r"[ \t]+", " ", s)
    # keep line breaks (they help extraction), but trim extra blank lines
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def looks_like_percent_off(text: str) -> bool:
    return bool(RE_PERCENT.search(text) and (RE_OFF_WORD.search(text) or "%off" in text.lower().replace(" ", "")))


def extract_percent(text: str) -> Optional[int]:
    m = RE_PERCENT.search(text)
    return int(m.group(1)) if m else None


def extract_price_range(text: str) -> Optional[Tuple[float, float]]:
    m = RE_RANGE.search(text)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def extract_prices(text: str) -> List[float]:
    return [float(x) for x in RE_PRICE.findall(text)]


def extract_multibuy(text: str) -> Optional[Tuple[int, float]]:
    m = RE_MULTI_BUY.search(text)
    if not m:
        return None
    qty = int(m.group(1))
    total = float(m.group(3))
    return qty, total


def detect_unit(text: str) -> Optional[str]:
    if RE_PER_LB.search(text):
        return "lb"
    if RE_PER_OZ.search(text):
        return "oz"
    return None


def clean_candidate(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .:-–—|•\t")
    return s


def drop_noise_lines(lines: List[str]) -> List[str]:
    out: List[str] = []
    for ln in lines:
        ln2 = ln.strip()
        if not ln2:
            continue
        if IMAGE_NOISE_PAT.match(ln2):
            continue
        out.append(ln2)
    return out


def extract_candidate_lines(text: str) -> List[str]:
    """
    Prefer the top lines that look like product names.
    Simple heuristics:
      - ignore lines with $ or % (usually pricing lines)
      - ignore lines with common stop phrases
      - prefer lines with letters
    """
    lines = drop_noise_lines(text.splitlines())
    candidates: List[str] = []

    for ln in lines:
        low = ln.lower()
        if "$" in ln or "%" in ln:
            continue
        if any(ph in low for ph in STOP_PHRASES):
            continue
        # must contain at least one letter
        if not re.search(r"[A-Za-z]", ln):
            continue
        candidates.append(clean_candidate(ln))

    return candidates


def split_products_from_line(line: str) -> List[str]:
    """
    Splits a line like:
      "Top Round Roast, Eye of Round Steak or London Broil"
    into candidates. Conservative: only split if we get reasonable chunks.
    """
    parts = [clean_candidate(p) for p in RE_SPLITORS.split(line) if clean_candidate(p)]
    # filter out tiny junk chunks
    parts = [p for p in parts if len(p) >= 4 and re.search(r"[A-Za-z]", p)]
    return parts


def extract_product_candidates(text: str, max_candidates: int = 8) -> List[str]:
    """
    Builds a candidate list from the best non-price lines.
    """
    lines = extract_candidate_lines(text)
    cands: List[str] = []

    for ln in lines:
        # If a line clearly contains multiple items, split it.
        pieces = split_products_from_line(ln)
        if len(pieces) >= 2:
            cands.extend(pieces)
        else:
            cands.append(ln)

        if len(cands) >= max_candidates:
            break

    # de-dupe while preserving order
    seen = set()
    uniq: List[str] = []
    for c in cands:
        key = c.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)

    return uniq[:max_candidates]


def pick_title(cands: List[str], fallback_text: str) -> str:
    if cands:
        return cands[0]
    # fallback: first non-empty line
    for ln in drop_noise_lines(fallback_text.splitlines()):
        return clean_candidate(ln)[:80]
    return "UNKNOWN"


@dataclass
class ParsedDeal:
    source_txt: str
    promo_type: str  # price | price_range | multibuy | percent_off | percent_off_with_range | unknown
    title: str
    product_candidates: str  # '|' separated
    product_count: int

    price: Optional[float] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    percent_off: Optional[int] = None
    multibuy_qty: Optional[int] = None
    multibuy_total: Optional[float] = None
    unit: Optional[str] = None
    with_prime: bool = False

    raw_text: str = ""


def classify_deal(raw_text: str, source_txt: str) -> ParsedDeal:
    text = normalize_text(raw_text)

    cands = extract_product_candidates(text)
    title = pick_title(cands, text)

    pct = extract_percent(text)
    rng = extract_price_range(text)
    prices = extract_prices(text)
    mb = extract_multibuy(text)
    unit = detect_unit(text)
    with_prime = bool(RE_WITH_PRIME.search(text))

    # percent off + range
    if looks_like_percent_off(text) and rng:
        return ParsedDeal(
            source_txt=source_txt,
            promo_type="percent_off_with_range",
            title=title,
            product_candidates="|".join(cands),
            product_count=len(cands),
            percent_off=pct,
            price_min=rng[0],
            price_max=rng[1],
            unit=unit,
            with_prime=with_prime,
            raw_text=text,
        )

    # percent off only
    if looks_like_percent_off(text):
        return ParsedDeal(
            source_txt=source_txt,
            promo_type="percent_off",
            title=title,
            product_candidates="|".join(cands),
            product_count=len(cands),
            percent_off=pct,
            unit=unit,
            with_prime=with_prime,
            raw_text=text,
        )

    # multibuy (2 for $5)
    if mb:
        qty, total = mb
        return ParsedDeal(
            source_txt=source_txt,
            promo_type="multibuy",
            title=title,
            product_candidates="|".join(cands),
            product_count=len(cands),
            multibuy_qty=qty,
            multibuy_total=total,
            unit=unit,
            with_prime=with_prime,
            raw_text=text,
        )

    # range only
    if rng:
        return ParsedDeal(
            source_txt=source_txt,
            promo_type="price_range",
            title=title,
            product_candidates="|".join(cands),
            product_count=len(cands),
            price_min=rng[0],
            price_max=rng[1],
            unit=unit,
            with_prime=with_prime,
            raw_text=text,
        )

    # single price (choose best candidate: smallest price tends to be sale price)
    if prices:
        best = min(prices)
        return ParsedDeal(
            source_txt=source_txt,
            promo_type="price",
            title=title,
            product_candidates="|".join(cands),
            product_count=len(cands),
            price=best,
            unit=unit,
            with_prime=with_prime,
            raw_text=text,
        )

    return ParsedDeal(
        source_txt=source_txt,
        promo_type="unknown",
        title=title,
        product_candidates="|".join(cands),
        product_count=len(cands),
        unit=unit,
        with_prime=with_prime,
        raw_text=text,
    )


def iter_txt_files(in_dir: Path) -> List[Path]:
    return sorted([p for p in in_dir.glob("*.txt") if p.is_file()])


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def write_csv(out_csv: Path, rows: List[ParsedDeal]) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_txt",
        "promo_type",
        "title",
        "product_count",
        "product_candidates",
        "price",
        "price_min",
        "price_max",
        "percent_off",
        "multibuy_qty",
        "multibuy_total",
        "unit",
        "with_prime",
        "raw_text",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))


def write_jsonl(out_jsonl: Path, rows: List[ParsedDeal]) -> None:
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(prog="parse_ocr_text_deals.py")
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--min-chars", type=int, default=30)
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)

    if not in_dir.exists():
        print(f"[FATAL] in-dir not found: {in_dir}")
        return 2

    txt_files = iter_txt_files(in_dir)
    print(f"[INFO] Found {len(txt_files)} txt files in {in_dir}")

    parsed: List[ParsedDeal] = []
    skipped_short = 0

    for p in txt_files:
        raw = read_text(p)
        raw_norm = normalize_text(raw)
        if len(raw_norm) < args.min_chars:
            skipped_short += 1
            continue

        deal = classify_deal(raw_norm, source_txt=p.name)
        parsed.append(deal)

    out_csv = out_dir / "parsed_deals.csv"
    out_jsonl = out_dir / "parsed_deals.jsonl"
    write_csv(out_csv, parsed)
    write_jsonl(out_jsonl, parsed)

    counts = {}
    total_products = 0
    for d in parsed:
        counts[d.promo_type] = counts.get(d.promo_type, 0) + 1
        total_products += d.product_count

    print(f"[OK] Parsed {len(parsed)} blobs (skipped_short={skipped_short})")
    for k in sorted(counts.keys()):
        print(f"     {k}: {counts[k]}")
    print(f"[INFO] product_candidates_total: {total_products}")
    print(f"[OUT] {out_csv}")
    print(f"[OUT] {out_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
