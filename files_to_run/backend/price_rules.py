# price_rules.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, List, Tuple


# ----------------------------
# Normalization
# ----------------------------

def normalize_ocr_text(text: str) -> str:
    if not text:
        return ""
    t = text.lower()

    # normalize currency symbols / weird OCR
    t = t.replace("usd", "$")
    t = t.replace("£", "$").replace("€", "$")
    t = t.replace("—", "-").replace("–", "-")

    # common OCR artifact: "s 1.99" meaning "$1.99"
    # only replace when it looks like a price follows
    t = re.sub(r"\bs\s+(?=\d{1,3}(?:\.\d{2})\b)", "$", t)

    # normalize whitespace
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*\n\s*", " ", t).strip()
    return t


# ----------------------------
# Extraction
# ----------------------------

_PRICE_RE = re.compile(
    r"""
    (?:
        \$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)   # $6.24, $1.99, $1,299.00
        |
        (?<!\d)(\d{1,3}(?:\.\d{2}))            # 6.24, 1.99 (avoid grabbing 2025 etc)
    )
    """,
    re.VERBOSE,
)

_PERCENT_RE = re.compile(r"(?<!\d)(\d{1,2})\s*%\s*off\b")

_X_FOR_Y_RE = re.compile(
    r"""
    (?:
        (?<!\d)(?P<x>\d+)\s*/\s*\$\s*(?P<y>\d+(?:\.\d{2})?)       # 2/$5 or 2/$5.00
        |
        (?<!\d)(?P<x2>\d+)\s*for\s*\$\s*(?P<y2>\d+(?:\.\d{2})?)   # 2 for $5
    )
    """,
    re.VERBOSE,
)

_RANGE_RE = re.compile(r"\$\s*(\d+(?:\.\d{2})?)\s*-\s*\$\s*(\d+(?:\.\d{2})?)")

_UNIT_RE = re.compile(
    r"\$\s*\d+(?:\.\d{2})?\s*/\s*(lb|lbs|oz|ct|ea|each|gal|qt|pt)\b"
)

# Dedicated "regular price" extraction (Step 2 reliability)
_REG_PRICE_RE = re.compile(r"\b(?:reg\.?|regular|was|list)\s*\$?\s*(\d{1,3}(?:\.\d{2})?)\b")


def extract_prices(text_norm: str) -> List[float]:
    prices: List[float] = []
    for m in _PRICE_RE.finditer(text_norm):
        raw = m.group(1) or m.group(2)
        if not raw:
            continue
        raw = raw.replace(",", "")
        try:
            val = float(raw)
        except ValueError:
            continue

        if 0.0 <= val <= 10000.0:
            prices.append(val)

    # dedupe preserving order
    seen = set()
    out: List[float] = []
    for p in prices:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out


def extract_percent_off(text_norm: str) -> Optional[int]:
    m = _PERCENT_RE.search(text_norm)
    if not m:
        return None
    try:
        pct = int(m.group(1))
    except ValueError:
        return None
    if 1 <= pct <= 95:
        return pct
    return None


def extract_x_for_y(text_norm: str) -> Optional[Tuple[int, float]]:
    m = _X_FOR_Y_RE.search(text_norm)
    if not m:
        return None

    x = m.group("x") or m.group("x2")
    y = m.group("y") or m.group("y2")
    if not x or not y:
        return None

    try:
        xi = int(x)
        yf = float(y)
    except (ValueError, TypeError):
        return None

    if xi > 0 and yf > 0:
        return (xi, yf)
    return None


def extract_range(text_norm: str) -> Optional[Tuple[float, float]]:
    m = _RANGE_RE.search(text_norm)
    if not m:
        return None
    try:
        lo = float(m.group(1))
        hi = float(m.group(2))
    except ValueError:
        return None
    if 0 < lo <= hi:
        return (lo, hi)
    return None


def extract_unit(text_norm: str) -> Optional[str]:
    m = _UNIT_RE.search(text_norm)
    if not m:
        return None
    u = m.group(1)
    if u == "lbs":
        return "lb"
    if u == "each":
        return "ea"
    return u


def extract_regular_price(text_norm: str) -> Optional[float]:
    """
    Pull a regular/list/was price even when generic price extraction misses it.
    Example: 'reg $8.99' -> 8.99
    """
    m = _REG_PRICE_RE.search(text_norm)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


# ----------------------------
# Decisioning
# ----------------------------

@dataclass
class PriceDecision:
    sale_price: Optional[float]
    regular_price: Optional[float]
    promo_type: Optional[str]              # 'x_for_y', 'bogo', 'percent_off', 'range', ...
    promo_text: Optional[str]              # human-friendly snippet
    effective_unit_price: Optional[float]  # computed for x_for_y
    promo_percent: Optional[int]
    confidence: float
    confidence_reason: str
    parse_status: str                      # 'ok', 'promo_only', 'failed'


_EXPLICIT_PAY_WORDS = re.compile(r"\b(pay|now|your price|only)\b")
_REGULAR_WORDS = re.compile(r"\b(regular|reg\.|was|list)\b")
_SALE_WORDS = re.compile(r"\b(sale|now|only|price)\b")
_BOGO_WORDS = re.compile(r"\b(bogo|buy\s*one\s*get\s*one|buy\s*1\s*get\s*1)\b")
_BOGO_HALF_WORDS = re.compile(r"\b(buy\s*one\s*get\s*one\s*50%|bogo\s*50)\b")


# ----------------------------
# Confidence calibration (Step 1)
# ----------------------------

def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _finalize_decision(
    d: PriceDecision,
    t_norm: str,
    prices: List[float],
    pct: Optional[int],
    unit: Optional[str],
) -> PriceDecision:
    """
    Post-pass confidence calibration.
    Does NOT change sale/regular/promo decisions — only nudges confidence.
    """
    conf = float(d.confidence)
    reasons: List[str] = []

    if len(t_norm) < 20 or len(t_norm.split()) < 4:
        conf -= 0.08
        reasons.append("short_text")

    if d.parse_status == "ok" and d.sale_price is not None:
        conf += 0.03
        reasons.append("has_sale_price")

    if d.parse_status == "ok" and d.sale_price is not None and pct is not None:
        conf += 0.04
        reasons.append("pct_plus_price")

    if d.parse_status == "ok" and unit:
        conf += 0.02
        reasons.append("unit_present")

    if len(prices) >= 4 and d.confidence_reason not in ("labeled_sale_vs_regular",):
        conf -= 0.06
        reasons.append("many_prices")

    if d.parse_status == "promo_only":
        conf = min(conf, 0.85)

    conf = _clamp01(conf)

    reason = d.confidence_reason
    if reasons:
        reason = f"{reason}+cal(" + ",".join(reasons) + ")"

    return PriceDecision(
        sale_price=d.sale_price,
        regular_price=d.regular_price,
        promo_type=d.promo_type,
        promo_text=d.promo_text,
        effective_unit_price=d.effective_unit_price,
        promo_percent=d.promo_percent,
        confidence=conf,
        confidence_reason=reason,
        parse_status=d.parse_status,
    )


def decide_price_and_promo(raw_text: str) -> PriceDecision:
    t = normalize_ocr_text(raw_text)

    if not t:
        return PriceDecision(
            sale_price=None,
            regular_price=None,
            promo_type=None,
            promo_text=None,
            effective_unit_price=None,
            promo_percent=None,
            confidence=0.0,
            confidence_reason="empty_text",
            parse_status="failed",
        )

    prices = extract_prices(t)
    pct = extract_percent_off(t)
    xfy = extract_x_for_y(t)
    rng = extract_range(t)
    unit = extract_unit(t)

    # 1) BOGO detection
    if _BOGO_WORDS.search(t):
        promo_type = "bogo"
        promo_text = "BOGO" if "bogo" in t else "Buy 1 Get 1"
        if _BOGO_HALF_WORDS.search(t):
            promo_text = "BOGO 50%"

        if prices and _EXPLICIT_PAY_WORDS.search(t):
            return _finalize_decision(
                PriceDecision(
                    sale_price=prices[0],
                    regular_price=None,
                    promo_type=promo_type,
                    promo_text=promo_text,
                    effective_unit_price=None,
                    promo_percent=pct,
                    confidence=0.98,
                    confidence_reason="explicit_pay_price_with_bogo",
                    parse_status="ok",
                ),
                t, prices, pct, unit
            )

        return _finalize_decision(
            PriceDecision(
                sale_price=None,
                regular_price=None,
                promo_type=promo_type,
                promo_text=promo_text,
                effective_unit_price=None,
                promo_percent=pct,
                confidence=0.70,
                confidence_reason="promo_only_bogo",
                parse_status="promo_only",
            ),
            t, prices, pct, unit
        )

    # 2) X/Y deals (2/$5, 3 for $10)
    if xfy:
        x, y = xfy
        eff = round(y / x, 4) if x else None
        promo_text = f"{x}/$" + (f"{y:.2f}".rstrip("0").rstrip("."))

        return _finalize_decision(
            PriceDecision(
                # Option A: treat computed unit price as the sale price for comparison
                sale_price=eff,
                regular_price=None,
                promo_type="x_for_y",
                promo_text=promo_text,
                effective_unit_price=eff,
                promo_percent=pct,
                confidence=0.82,
                confidence_reason="x_for_y_unit_price_as_sale",
                parse_status="ok",
            ),
            t, prices, pct, unit
        )

    # 3) Price ranges ($5-$7)
    if rng:
        lo, hi = rng
        promo_text = f"${lo:.2f}-${hi:.2f}".replace(".00", "")
        return _finalize_decision(
            PriceDecision(
                sale_price=None,
                regular_price=None,
                promo_type="range",
                promo_text=promo_text,
                effective_unit_price=None,
                promo_percent=pct,
                confidence=0.55,
                confidence_reason="promo_only_range",
                parse_status="promo_only",
            ),
            t, prices, pct, unit
        )

    # 4) Percent off only (no price)
    if pct is not None and not prices:
        return _finalize_decision(
            PriceDecision(
                sale_price=None,
                regular_price=None,
                promo_type="percent_off",
                promo_text=f"{pct}% off",
                effective_unit_price=None,
                promo_percent=pct,
                confidence=0.40,
                confidence_reason="promo_only_percent",
                parse_status="promo_only",
            ),
            t, prices, pct, unit
        )

    # 5) Explicit "pay/now/your price" + a price (Step 2: capture reg price reliably)
    if prices and _EXPLICIT_PAY_WORDS.search(t):
        sale = prices[0]
        reg = extract_regular_price(t)

        # If we found a regular price, sale should generally be the lower number
        if reg is not None:
            sale = min([sale, reg] + prices)

        return _finalize_decision(
            PriceDecision(
                sale_price=sale,
                regular_price=reg,
                promo_type=("percent_off" if pct is not None else None),
                promo_text=(f"{pct}% off" if pct is not None else None),
                effective_unit_price=None,
                promo_percent=pct,
                confidence=0.98,
                confidence_reason=(
                    "explicit_pay_price_with_regular"
                    if reg is not None
                    else "explicit_pay_price"
                ),
                parse_status="ok",
            ),
            t, prices, pct, unit
        )

    # 6) Two prices
    if len(prices) >= 2:
        if _REGULAR_WORDS.search(t) and _SALE_WORDS.search(t):
            reg = max(prices)
            sale = min(prices)
            return _finalize_decision(
                PriceDecision(
                    sale_price=sale,
                    regular_price=reg,
                    promo_type=("percent_off" if pct is not None else None),
                    promo_text=(f"{pct}% off" if pct is not None else None),
                    effective_unit_price=None,
                    promo_percent=pct,
                    confidence=0.92,
                    confidence_reason="labeled_sale_vs_regular",
                    parse_status="ok",
                ),
                t, prices, pct, unit
            )

        return _finalize_decision(
            PriceDecision(
                sale_price=min(prices),
                regular_price=max(prices),
                promo_type=("percent_off" if pct is not None else None),
                promo_text=(f"{pct}% off" if pct is not None else None),
                effective_unit_price=None,
                promo_percent=pct,
                confidence=0.75,
                confidence_reason="two_prices_guess_low_is_sale",
                parse_status="ok",
            ),
            t, prices, pct, unit
        )

    # 7) Single price
    if len(prices) == 1:
        return _finalize_decision(
            PriceDecision(
                sale_price=prices[0],
                regular_price=None,
                promo_type=("percent_off" if pct is not None else None),
                promo_text=(f"{pct}% off" if pct is not None else None),
                effective_unit_price=None,
                promo_percent=pct,
                confidence=0.84,
                confidence_reason=("single_price_with_unit" if unit else "single_price"),
                parse_status="ok",
            ),
            t, prices, pct, unit
        )

    # 8) Nothing usable
    return _finalize_decision(
        PriceDecision(
            sale_price=None,
            regular_price=None,
            promo_type=None,
            promo_text=None,
            effective_unit_price=None,
            promo_percent=pct,
            confidence=0.15,
            confidence_reason="no_price_no_promo",
            parse_status="failed",
        ),
        t, prices, pct, unit
    )
