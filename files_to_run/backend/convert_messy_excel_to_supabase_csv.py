import re
import sys
import os
from typing import Optional, Tuple, Dict, Any, List

import pandas as pd


# -------------------------
# Output schema
# -------------------------
STD_HEADERS = [
    "item_name",
    "week_code",
    "percent_off_prime",
    "percent_off_nonprime",
    "price_text",          # NEW
    "unit_price",          # NEW (numeric-ish string)
    "promo_start",
    "promo_end",
    "manual_review_reason",
    "source_file",
]

# Debug adds raw_text
DEBUG_EXTRA = ["raw_text"]

# -------------------------
# Regex helpers
# -------------------------
PCT_RE = re.compile(r"(\d{1,3})\s*%")
# Matches $1.99, $12.00, etc.
PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d{2})?)")
# Matches 2/$5, 3 / $10, etc.
X_FOR_Y_RE = re.compile(r"\b(\d+)\s*/\s*\$\s*(\d+(?:\.\d{2})?)\b")
# Matches "2 for $5" style
X_FOR_Y_WORD_RE = re.compile(r"\b(\d+)\s*for\s*\$\s*(\d+(?:\.\d{2})?)\b", re.IGNORECASE)
# Common deal words
BOGO_RE = re.compile(r"\b(bogo|buy\s*one\s*get\s*one|buy\s*1\s*get\s*1|buy\s*one\s*&\s*get\s*one)\b", re.IGNORECASE)
MIX_MATCH_RE = re.compile(r"\b(mix\s*&\s*match|mix\s*and\s*match|any\s*\d+|when\s*you\s*buy|must\s*buy)\b", re.IGNORECASE)
LIMIT_RE = re.compile(r"\b(limit\s*\d+)\b", re.IGNORECASE)
# Unit indicators
PER_LB_RE = re.compile(r"\b(/\s*lb|per\s*lb|lb\.)\b", re.IGNORECASE)
EACH_RE = re.compile(r"\b(ea\.?|each)\b", re.IGNORECASE)

PRIME_RE = re.compile(r"\bprime\b", re.IGNORECASE)
NONPRIME_RE = re.compile(r"\b(non[-\s]?prime|nonmembers?|regular)\b", re.IGNORECASE)
JUNK_ROW_RE = re.compile(
    r"(hot zone item|see store associate|out of 5 stars|reviews\b|unit price is|original price was|loyalty discount price is)",
    re.IGNORECASE
)



def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def guess_percent_off(text: str) -> Optional[int]:
    m = PCT_RE.search(text)
    if not m:
        return None
    try:
        v = int(m.group(1))
        if 0 <= v <= 100:
            return v
    except ValueError:
        return None
    return None


def guess_item_name(text: str) -> Tuple[str, str]:
    """
    Returns (item_name, reason_if_any).
    Heuristics:
      - Strip obvious percent/price tokens
      - Strip common promo noise
      - Keep remaining descriptive text
    """
    t = text

    # remove percent + prices (they're not the name)
    t = PCT_RE.sub(" ", t)
    t = X_FOR_Y_RE.sub(" ", t)
    t = X_FOR_Y_WORD_RE.sub(" ", t)
    t = PRICE_RE.sub(" ", t)

    # remove promo noise
    t = re.sub(r"\b(with\s+card|digital\s+coupon|coupon|save\s*\$\s*\d+(?:\.\d{2})?)\b", " ", t, flags=re.I)
    t = re.sub(r"\bprime\b|\bnon[-\s]?prime\b|\bmembers?\b|\bregular\b", " ", t, flags=re.I)
    t = re.sub(r"\b(limit\s*\d+)\b", " ", t, flags=re.I)
    t = re.sub(r"(see store associate|out of 5 stars|reviews\b|unit price is|original price was|loyalty discount price is)", " ", t, flags=re.I)
    t = norm_ws(t)

    if len(t) < 3:
        fallback = norm_ws(text)
        return (fallback[:200], "item_name_low_confidence_used_raw_text")

    return (t[:200], "")


def extract_price_text_and_unit(text: str) -> Tuple[str, str, str]:
    """
    Returns (price_text, unit_price, reason_if_any)

    - price_text captures complex deal formats: BOGO, 2/$5, 2 for $5, $1.99/lb, etc.
    - unit_price is only set when a clean $X.XX appears and there is no obvious multi-buy.
    """
    t = text
    reasons: List[str] = []

    # 1) Explicit BOGO
    if BOGO_RE.search(t):
        reasons.append("price_bogo")
        return ("BOGO", "", ";".join(reasons))

    # 2) Multi-buy formats
    m = X_FOR_Y_RE.search(t)
    if m:
        x = m.group(1)
        y = m.group(2)
        reasons.append("price_multibuy")
        return (f"{x}/$${y}".replace("$$", "$"), "", ";".join(reasons))

    m = X_FOR_Y_WORD_RE.search(t)
    if m:
        x = m.group(1)
        y = m.group(2)
        reasons.append("price_multibuy")
        return (f"{x} for ${y}", "", ";".join(reasons))

    # 3) Look for a plain $X.XX price
    price_matches = list(PRICE_RE.finditer(t))
    if price_matches:
        # pick first price
        p = price_matches[0].group(1)

        # If there's obvious complexity around it, keep as text
        per_lb = bool(PER_LB_RE.search(t))
        each = bool(EACH_RE.search(t))
        mixmatch = bool(MIX_MATCH_RE.search(t))
        limit = bool(LIMIT_RE.search(t))

        if per_lb:
            reasons.append("price_per_lb")
            return (f"${p}/lb", "", ";".join(reasons))

        if mixmatch:
            reasons.append("price_mix_match")
            return (f"${p}", "", ";".join(reasons))

        if limit:
            reasons.append("price_limit_present")
            # still okay to keep unit_price, but flag it
            return (f"${p}", p, ";".join(reasons))

        # clean unit price
        return (f"${p}" + (" each" if each else ""), p, "")

    # 4) No detectable price
    return ("", "", "")


def classify_wf_prime_fields(text: str, pct: Optional[int]) -> Tuple[Optional[int], Optional[int], str]:
    """
    Whole Foods special handling: try to decide if percent applies to prime or nonprime.
    """
    if pct is None:
        return (None, None, "")

    has_prime = bool(PRIME_RE.search(text))
    has_nonprime = bool(NONPRIME_RE.search(text))

    if has_prime and not has_nonprime:
        return (pct, None, "")
    if has_nonprime and not has_prime:
        return (None, pct, "")
    if has_prime and has_nonprime:
        return (None, None, "prime_nonprime_ambiguous")

    return (None, pct, "percent_found_no_prime_signal_assumed_nonprime")


def excel_to_rows(xlsx_path: str) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path, dtype=str)  # read all as strings
    df = df.fillna("")
    return df


def build_output(
    df: pd.DataFrame,
    week_code: str,
    promo_start: str,
    promo_end: str,
    source_file: str,
    store: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:

    out: List[Dict[str, Any]] = []
    debug: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        cells = [str(v) for v in row.values.tolist() if str(v).strip() != ""]
        if not cells:
            continue

        # Preserve everything
        raw_text = norm_ws(" | ".join(cells))
        if JUNK_ROW_RE.search(raw_text):
         continue

        pct = guess_percent_off(raw_text)
        item_name, name_reason = guess_item_name(raw_text)

        price_text, unit_price, price_reason = extract_price_text_and_unit(raw_text)

        percent_off_prime = None
        percent_off_nonprime = None
        wf_reason = ""

        if store.lower() in ("whole_foods", "wf", "wholefoods"):
            p_prime, p_nonprime, wf_reason = classify_wf_prime_fields(raw_text, pct)
            percent_off_prime = p_prime
            percent_off_nonprime = p_nonprime
        else:
            percent_off_nonprime = pct

        reasons = [r for r in [name_reason, wf_reason, price_reason] if r]
        manual_review_reason = ";".join([r for r in reasons if r])

        rec = {
            "item_name": item_name,
            "week_code": week_code,
            "percent_off_prime": percent_off_prime,
            "percent_off_nonprime": percent_off_nonprime,
            "price_text": price_text,
            "unit_price": unit_price,
            "promo_start": promo_start,
            "promo_end": promo_end,
            "manual_review_reason": manual_review_reason,
            "source_file": source_file,
        }

        out.append(rec)
        debug.append({**rec, "raw_text": raw_text})

    out_df = pd.DataFrame(out, columns=STD_HEADERS)
    debug_df = pd.DataFrame(debug, columns=STD_HEADERS + DEBUG_EXTRA)
    return out_df, debug_df


def main():
    if len(sys.argv) < 5:
        print("Usage:")
        print("  python convert_messy_excel_to_supabase_csv.py <xlsx_path> <store> <week_code> <out_csv> [out_debug_csv] [promo_start] [promo_end]")
        sys.exit(2)

    xlsx_path = sys.argv[1]
    store = sys.argv[2]
    week_code = sys.argv[3]
    out_csv = sys.argv[4]

    # Optional args
    out_debug_csv = sys.argv[5] if len(sys.argv) >= 6 and sys.argv[5].lower().endswith(".csv") else ""
    promo_start = sys.argv[6] if len(sys.argv) >= 7 else ""
    promo_end = sys.argv[7] if len(sys.argv) >= 8 else ""

    if not os.path.exists(xlsx_path):
        raise FileNotFoundError(xlsx_path)

    source_file = os.path.basename(xlsx_path)

    df = excel_to_rows(xlsx_path)
    tidy_df, debug_df = build_output(
        df=df,
        week_code=week_code,
        promo_start=promo_start,
        promo_end=promo_end,
        source_file=source_file,
        store=store,
    )

    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    tidy_df.to_csv(out_csv, index=False)

    if out_debug_csv:
        os.makedirs(os.path.dirname(out_debug_csv) or ".", exist_ok=True)
        debug_df.to_csv(out_debug_csv, index=False)

    print(f"[OK] Wrote tidy CSV : {out_csv} ({len(tidy_df)} rows)")
    if out_debug_csv:
        print(f"[OK] Wrote debug CSV: {out_debug_csv} ({len(debug_df)} rows)")


if __name__ == "__main__":
    main()
