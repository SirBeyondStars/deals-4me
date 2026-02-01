# site/files_to_run/backend/price_select.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


# ----------------------------
# Models
# ----------------------------

@dataclass
class PricePick:
    sale_price: float
    unit: Optional[str] = None          # "lb" or "ea" (best guess)
    is_multibuy: bool = False           # True for 2/$5
    multibuy_qty: Optional[int] = None
    multibuy_total: Optional[float] = None
    raw_token: Optional[str] = None     # token that won
    reason: Optional[str] = None        # debugging: why we chose it


@dataclass
class Candidate:
    kind: str                 # "dollar", "cents", "multibuy"
    value: float              # interpreted sale price (for multibuy: per-item price)
    raw: str                  # raw token like "$1.97" or "97¢" or "2/$5"
    line_index: int
    char_index: int
    has_per_lb: bool
    has_each: bool
    is_junk_context: bool
    qty: Optional[int] = None
    total: Optional[float] = None


@dataclass
class ParsedDeal:
    item_name: str
    sale_price: Optional[float]
    unit: Optional[str]
    is_multibuy: bool
    multibuy_qty: Optional[int]
    multibuy_total: Optional[float]

    # WF-friendly fields
    percent_off: Optional[int] = None
    percent_text: Optional[str] = None

    # meta/debug
    confidence: int = 0
    reject_reason: Optional[str] = None

    # limits (optional metadata)
    limit_qty: Optional[int] = None
    limit_scope: Optional[str] = None   # "per_trip" | "per_day" | "per_customer" | "unknown"
    limit_text: Optional[str] = None


# ----------------------------
# Patterns / heuristics
# ----------------------------

# $399 -> $3.99 (OCR sometimes drops decimal)
DOLLAR_NO_DOT_RE = re.compile(r"\$(\d{1,2})(\d{2})\b")

# prices
DECIMAL_RE = re.compile(r"(?<!\d)(\d{1,3}\.\d{2})(?!\d)")
CENTS_RE = re.compile(r"(?<!\d)(\d{1,3})\s*(?:¢|c)\b", re.IGNORECASE)
MULTIBUY_RE = re.compile(r"(?<!\d)(\d{1,2})\s*/\s*\$?\s*(\d{1,3}(?:\.\d{2})?)(?!\d)")
MONEY_RE = re.compile(r"\$\s*(\d{1,3}(?:\.\d{2})?)")

# percent (robust to OCR spacing/weirdness)
# Supports: "19% off", "19 %off", "I9% off", "19％ off", "19° off"
PCT_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[%％°]\s*(?:off)?\b", re.IGNORECASE)
OFF_RE = re.compile(r"\boff\b", re.IGNORECASE)

# units
PER_LB_RE = re.compile(r"\b(?:/lb|per\s*lb)\b", re.IGNORECASE)
EACH_RE = re.compile(r"\b(?:ea|each)\b", re.IGNORECASE)

# “junk context” cues — numbers near these are often NOT the sale price
JUNK_CUE_RE = re.compile(
    r"\b(?:save|savings|you\s*save|limit|must\s*buy|when\s*you\s*buy|"
    r"mix\s*&\s*match|points|reward|deposit|reg|regular|was|compare\s*at|"
    r"valid|with\s*prime)\b",
    re.IGNORECASE
)

LIMIT_LINE_RE = re.compile(r"\blimit\b", re.IGNORECASE)
NEG_NUM_RE = re.compile(r"(?<!\d)-\s*\d+(?:\.\d{2})?")  # negative savings like "-1.00"

# words that don’t belong in product names (we strip them, not auto-reject)
BAD_NAME_CUE_RE = re.compile(
    r"\b(?:digital|coupon|for\s*u|sale\s*price|price|save|savings|limit|lb|/lb|per\s*lb|"
    r"must\s*buy|mix\s*&\s*match|reg|regular|was|each|ea|valid|with\s*prime|off)\b",
    re.IGNORECASE
)

MOSTLY_NON_ALPHA_RE = re.compile(r"^[^A-Za-z]*$")


# ----------------------------
# Helpers
# ----------------------------

def _normalize_text(text: str) -> str:
    t = text or ""
    t = t.replace("Add to cart", "").replace("add to cart", "")
    # common OCR artifacts cleanup
    t = t.replace("Â", "").replace("â€™", "'").replace("â€˜", "'").replace("â€“", "-")
    return t


def _clean_name_line(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.strip("•*-–—|:;.,()[]{}")
    return s


def _strip_trailing_junk(s: str) -> str:
    s = re.sub(r"\bitem\b.*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bsingle\s*price\b.*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bvarieties?\b.*$", "", s, flags=re.IGNORECASE)
    return s.strip()


# ----------------------------
# Candidate extraction
# ----------------------------

def _extract_candidates(lines: List[str]) -> List[Candidate]:
    out: List[Candidate] = []

    for li, raw_line in enumerate(lines):
        line = _normalize_text(raw_line)
        if not line.strip():
            continue

        has_per_lb = bool(PER_LB_RE.search(line))
        has_each = bool(EACH_RE.search(line))
        is_limit_line = bool(LIMIT_LINE_RE.search(line))
        has_pct = bool(PCT_RE.search(line))
        has_neg = bool(NEG_NUM_RE.search(line))

        junk_line = bool(JUNK_CUE_RE.search(line)) or is_limit_line or has_pct or has_neg

        # multibuy like 2/$5
        for m in MULTIBUY_RE.finditer(line):
            qty = int(m.group(1))
            total = float(m.group(2))
            if qty > 0 and total > 0:
                per_item = total / qty
                out.append(
                    Candidate(
                        kind="multibuy",
                        value=per_item,
                        raw=m.group(0).replace(" ", ""),
                        line_index=li,
                        char_index=m.start(),
                        has_per_lb=has_per_lb,
                        has_each=has_each,
                        is_junk_context=junk_line,
                        qty=qty,
                        total=total,
                    )
                )

        # cents like 97¢
        for m in CENTS_RE.finditer(line):
            cents = int(m.group(1))
            if 0 < cents <= 999:
                out.append(
                    Candidate(
                        kind="cents",
                        value=cents / 100.0,
                        raw=f"{cents}¢",
                        line_index=li,
                        char_index=m.start(),
                        has_per_lb=has_per_lb,
                        has_each=has_each,
                        is_junk_context=junk_line,
                    )
                )
        # $399 -> 3.99
        for m in DOLLAR_NO_DOT_RE.finditer(line):
            v = float(f"{m.group(1)}.{m.group(2)}")
            if 0 < v <= 500:
                out.append(
                    Candidate(
                        kind="dollar",
                        value=v,
                        raw=f"${m.group(1)}.{m.group(2)}",
                        line_index=li,
                        char_index=m.start(),
                        has_per_lb=has_per_lb,
                        has_each=has_each,
                        is_junk_context=junk_line,
                    )
                )


        # decimals like 1.97
        for m in DECIMAL_RE.finditer(line):
            v = float(m.group(1))
            if 0 < v <= 500:
                out.append(
                    Candidate(
                        kind="dollar",
                        value=v,
                        raw=m.group(1),
                        line_index=li,
                        char_index=m.start(),
                        has_per_lb=has_per_lb,
                        has_each=has_each,
                        is_junk_context=junk_line,
                    )
                )

        # explicit $ amounts
        for m in MONEY_RE.finditer(line):
            v = float(m.group(1))
            if 0 < v <= 500:
                out.append(
                    Candidate(
                        kind="dollar",
                        value=v,
                        raw=m.group(0).replace(" ", ""),
                        line_index=li,
                        char_index=m.start(),
                        has_per_lb=has_per_lb,
                        has_each=has_each,
                        is_junk_context=junk_line,
                    )
                )

    # de-dupe candidates
    dedup: List[Candidate] = []
    seen = set()
    for c in out:
        k = (c.kind, round(c.value, 3), c.line_index, c.raw)
        if k in seen:
            continue
        seen.add(k)
        dedup.append(c)

    return dedup


# ----------------------------
# Percent / Limit extraction
# ----------------------------

_WORD_NUMS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

def extract_percent_off(clean_text: str) -> Tuple[Optional[int], Optional[str]]:
    if not clean_text:
        return None, None

    t = " ".join(clean_text.split())

    # OCR fixes: I9% -> 19%, l9% -> 19%, O -> 0 when adjacent to digits
    t2 = re.sub(r"(?<=\b)[Il](?=\d)", "1", t)
    t2 = re.sub(r"(?<=\d)O(?=\d)", "0", t2)

    m = PCT_RE.search(t2)
    if not m:
        return None, None

    pct = int(m.group(1))

    # Optional safety: if we saw a percent but NOT the word "off", still accept (WF sometimes drops it)
    # If you want stricter, require OFF_RE.search(t2).
    start = max(0, m.start() - 25)
    end = min(len(t2), m.end() + 35)
    snippet = " ".join(t2[start:end].split()).strip()

    return pct, snippet


def extract_limit(clean_text: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    if not clean_text:
        return None, None, None

    t = " ".join(clean_text.lower().split())

    m = re.search(
        r"\blimit\b\s*[:\-]?\s*(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b"
        r"(?P<trailer>[^.\n\r]{0,40})",
        t,
        flags=re.IGNORECASE,
    )
    if not m:
        return None, None, None

    raw_num = m.group("num").lower()
    qty = int(raw_num) if raw_num.isdigit() else _WORD_NUMS.get(raw_num)
    if qty is None:
        return None, None, None

    trailer = (m.group("trailer") or "").lower()

    if "per day" in trailer or "a day" in trailer:
        scope = "per_day"
    elif "per trip" in trailer or "per transaction" in trailer or "per visit" in trailer:
        scope = "per_trip"
    elif "per customer" in trailer or "per household" in trailer:
        scope = "per_customer"
    else:
        scope = "unknown"

    limit_text = ("limit " + raw_num + trailer).strip()
    return qty, scope, limit_text


# ----------------------------
# Price pick
# ----------------------------

def pick_best_sale_price(blob_text: str) -> Optional[PricePick]:
    if not blob_text or len(blob_text.strip()) < 5:
        return None

    lines = [ln.strip() for ln in blob_text.splitlines() if ln is not None]
    cands = _extract_candidates(lines)
    if not cands:
        return None

    blob_has_per_lb = any(PER_LB_RE.search(ln or "") for ln in lines)

    def score(c: Candidate) -> float:
        s = 0.0

        if c.kind == "dollar":
            s += 40
        elif c.kind == "multibuy":
            s += 35
        elif c.kind == "cents":
            s += 20

        # unit alignment
        if blob_has_per_lb:
            s += 15 if c.has_per_lb else -6
        else:
            if c.kind == "cents":
                s -= 6

        if c.has_each:
            s += 2

        # penalize junk context heavily
        if c.is_junk_context:
            s -= 35

        # sanity
        v = c.value
        if v < 0.10:
            s -= 25
        if v > 100:
            s -= 10

        # slight bias toward later lines (WF price often comes below header)
        s += min(6, c.line_index * 0.3)

        return s

    best = sorted(cands, key=score, reverse=True)[0]

    # unit guess
    if best.has_per_lb or blob_has_per_lb:
        unit = "lb"
    else:
        unit = "ea"

    return PricePick(
        sale_price=round(best.value, 2),
        unit=unit,
        is_multibuy=(best.kind == "multibuy"),
        multibuy_qty=(best.qty if best.kind == "multibuy" else None),
        multibuy_total=(best.total if best.kind == "multibuy" else None),
        raw_token=best.raw,
        reason="top_score",
    )


# ----------------------------
# Name extraction
# ----------------------------

def extract_item_name(blob_text: str, best: Optional[Candidate] = None) -> Optional[str]:
    if not blob_text or len(blob_text.strip()) < 5:
        return None

    raw_lines = [ln.strip() for ln in (blob_text.splitlines() or [])]
    if not any(ln.strip() for ln in raw_lines):
        return None

    VALID_LINE_RE = re.compile(r"^\s*valid\s+\d{1,2}/\d{1,2}\s*-\s*\d{1,2}/\d{1,2}", re.IGNORECASE)

    def normalize_candidate_line(s: str) -> str:
        s = _normalize_text(s)
        s = _clean_name_line(s)
        s = _strip_trailing_junk(s)

        # remove price-ish tokens
        s = DECIMAL_RE.sub("", s)
        s = CENTS_RE.sub("", s)
        s = MULTIBUY_RE.sub("", s)
        s = MONEY_RE.sub("", s)

        # remove percent tokens (WF)
        s = PCT_RE.sub("", s)

        # strip junk words, but keep line
        s = BAD_NAME_CUE_RE.sub("", s)

        if VALID_LINE_RE.search(s):
            return ""

        # remove numeric-only junk
        s = re.sub(r"\b\d{1,3}\s*-\s*\d{1,3}\b", "", s)
        s = re.sub(r"\b\d+\b", "", s)

        s = re.sub(r"\s+", " ", s).strip(" •*-–—|:;.,()[]{}")
        return s.strip()

    def score_cleaned(cleaned: str) -> float:
        if not cleaned:
            return -999
        alpha = sum(ch.isalpha() for ch in cleaned)
        if alpha < 6:
            return -999
        if MOSTLY_NON_ALPHA_RE.match(cleaned):
            return -999

        words = [w for w in re.split(r"\s+", cleaned) if w]
        if len(words) < 2:
            return -50

        s = 0.0
        s += min(24, len(words) * 5)
        s += 10 if 10 <= len(cleaned) <= 70 else 0
        s -= 10 if len(cleaned) > 110 else 0
        return s

    candidates: List[Tuple[float, str]] = []

    # window around price line if known
    if best is not None:
        center = best.line_index
        lo = max(0, center - 4)
        hi = min(len(raw_lines) - 1, center + 4)
        idxs = range(lo, hi + 1)
    else:
        idxs = range(len(raw_lines))

    for i in idxs:
        a = normalize_candidate_line(raw_lines[i])
        if a:
            s = score_cleaned(a)
            if best is not None:
                dist = abs(i - best.line_index)
                s += max(0, 14 - dist * 4)
            candidates.append((s, a))

        if i + 1 < len(raw_lines):
            b = normalize_candidate_line(raw_lines[i + 1])
            if a and b:
                combo = _clean_name_line(f"{a} {b}")
                s2 = score_cleaned(combo)
                if best is not None:
                    dist = abs(i - best.line_index)
                    s2 += max(0, 16 - dist * 3)
                s2 += 6
                candidates.append((s2, combo))

    if not candidates:
        return None

    candidates.sort(reverse=True, key=lambda x: x[0])
    top_score, top_cleaned = candidates[0]
    if top_score < 0:
        return None

    name = _clean_name_line(top_cleaned)
    return name[:90] if name else None


# ----------------------------
# Main parse
# ----------------------------

def parse_offer_blob(blob_text: str) -> Optional[ParsedDeal]:
    MIN_CONFIDENCE = 60

    lines = [ln.strip() for ln in (blob_text.splitlines() or [])]
    clean_text = "\n".join([ln for ln in lines if ln])

    # percent-off detection (WF heavy)
    percent_off, percent_text = extract_percent_off(clean_text)

    has_prime = bool(re.search(r"\bprime\b", clean_text, re.IGNORECASE))

    # price pick (may be None for % off tiles)
    pick = pick_best_sale_price(blob_text)

    # If neither a price nor a percent exists, bail
    if pick is None and percent_off is None and not has_prime:
     return None

    cands = _extract_candidates(lines)

    best_obj: Optional[Candidate] = None
    if pick:
        for c in cands:
            if round(c.value, 2) == round(pick.sale_price, 2) and c.kind in ("dollar", "cents", "multibuy"):
                best_obj = c
                break

    name = extract_item_name(blob_text, best=best_obj)
    if not name:
        return None

    # limits metadata
    limit_qty, limit_scope, limit_text = extract_limit(clean_text)

    confidence = 0
    reasons: List[str] = []

    # deal signal: price OR percent
    if pick is not None and pick.sale_price is not None:
        confidence += 35
    elif percent_off is not None:
        confidence += 35
    else:
        reasons.append("no_price_or_percent")

    if len(name.split()) >= 2:
        confidence += 35
    else:
        confidence += 20
        reasons.append("short_name")

    if pick is not None and pick.unit:
        confidence += 10

    if pick is not None and pick.is_multibuy:
        if pick.multibuy_qty and pick.multibuy_total:
            confidence += 10
        else:
            reasons.append("weak_multibuy")

    confidence = max(0, min(100, confidence))
    if confidence < MIN_CONFIDENCE:
        return None

    return ParsedDeal(
        item_name=name,
        sale_price=(pick.sale_price if pick else None),
        unit=(pick.unit if pick else None),
        is_multibuy=(pick.is_multibuy if pick else False),
        multibuy_qty=(pick.multibuy_qty if pick else None),
        multibuy_total=(pick.multibuy_total if pick else None),
        percent_off=percent_off,
        percent_text=percent_text,
        confidence=confidence,
        reject_reason=";".join(reasons) if reasons else None,
        limit_qty=limit_qty,
        limit_scope=limit_scope,
        limit_text=limit_text,
    )


def parse_offer_blob_with_reason(blob_text: str) -> Tuple[Optional[ParsedDeal], str]:
    if not blob_text or len(blob_text.strip()) < 5:
        return None, "empty_blob"

    pick = pick_best_sale_price(blob_text)
    percent_off, _ = extract_percent_off(" ".join((blob_text or "").split()))

    if pick is None and percent_off is None:
        return None, "no_price_or_percent"

    deal = parse_offer_blob(blob_text)
    if deal:
        return deal, "ok"

    # explain why
    lines = [ln.strip() for ln in (blob_text.splitlines() or [])]
    cands = _extract_candidates(lines)

    best_obj: Optional[Candidate] = None
    if pick:
        for c in cands:
            if round(c.value, 2) == round(pick.sale_price, 2):
                best_obj = c
                break

    name = extract_item_name(blob_text, best=best_obj)
    if not name:
        return None, "no_item_name"

    return None, "low_confidence"
