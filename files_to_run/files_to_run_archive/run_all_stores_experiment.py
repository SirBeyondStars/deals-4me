#!/usr/bin/env python3
"""
Deals-4Me Mini Admin — v1.6 (files_to_run edition)

What’s new in 1.6 (per Jesse’s “C” choice):
- Safe promo math (no more float division by zero on bad OCR)
- Robust MULTI_BUY parsing with qty/total guards
- Debug mode that captures bad OCR lines and writes a parse_errors.csv
- Parse-only works even if no new OCR was generated this run
- Progress messages per image during OCR
- Option 6: Preview latest parsed CSV (unchanged)
- Option 7: Preview parsed CSV for ANY week (you pick)
- Cleaner confidence scoring and item name cleanup

Updated for weekNN folders:
- Weeks are now named like "week47" instead of MMDDYY
- Looks for raw_png/raw_pdf/ocr folders (and falls back to old names)
"""

from __future__ import annotations

import os
import re
import csv
import json
import shutil
import subprocess
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

# =========================
# Week + path helpers
# =========================

# weekNN pattern, where NN is 1–53
WEEK_CODE_RE = re.compile(r"^week(\d{1,2})$")


def project_root() -> str:
    """
    Try to resolve the true project root.

    If this file lives in:
      <root>/files_to_run/backend/run_all_stores.py
    then parent is <root>/files_to_run; we go up one more.

    If it lives in:
      <root>/files_to_run/run_all_stores.py
    then parent is already <root>.
    """
    here = os.path.abspath(os.path.dirname(__file__))
    parent = os.path.abspath(os.path.join(here, os.pardir))

    # If parent has 'flyers', assume that is root.
    if os.path.isdir(os.path.join(parent, "flyers")):
        return parent

    # Otherwise, go one more level up.
    grandparent = os.path.abspath(os.path.join(parent, os.pardir))
    return grandparent


def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def safe_input(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\nExiting…")
        return "0"


def pause(msg: str = "Press Enter to continue…") -> None:
    try:
        input(msg)
    except (EOFError, KeyboardInterrupt):
        pass


def current_week_code() -> str:
    """
    Return current ISO week code as 'weekNN', Monday-based.
    This matches the idea of your PowerShell Get-WeekFolderName.
    """
    week_num = datetime.now().isocalendar().week  # 1–53
    return f"week{week_num:02d}"


def _store_root(root: str, store: str) -> str:
    return os.path.join(root, "flyers", store)


def weeks_for_store(root: str, store: str) -> List[str]:
    """
    Return sorted list of week codes for a store, e.g. ["week45", "week46", "week47"].
    """
    sroot = _store_root(root, store)
    if not os.path.isdir(sroot):
        return []

    codes: List[Tuple[int, str]] = []
    for w in os.listdir(sroot):
        m = WEEK_CODE_RE.match(w)
        if m and os.path.isdir(os.path.join(sroot, w)):
            num = int(m.group(1))
            codes.append((num, w))

    return [name for _, name in sorted(codes)]


def latest_week_for_store(root: str, store: str) -> Optional[str]:
    wks = weeks_for_store(root, store)
    return wks[-1] if wks else None


def latest_week_any(root: str) -> Optional[str]:
    """
    Find the numerically latest weekNN across all stores.
    """
    flyers_root = os.path.join(root, "flyers")
    if not os.path.isdir(flyers_root):
        return None

    max_num: Optional[int] = None
    for store in os.listdir(flyers_root):
        sp = os.path.join(flyers_root, store)
        if not os.path.isdir(sp):
            continue
        for wk in os.listdir(sp):
            m = WEEK_CODE_RE.match(wk)
            if not m:
                continue
            if not os.path.isdir(os.path.join(sp, wk)):
                continue
            num = int(m.group(1))
            if max_num is None or num > max_num:
                max_num = num

    return f"week{max_num:02d}" if max_num is not None else None


def log_path(root: str, store: str) -> str:
    d = os.path.join(root, "logs", store)
    ensure_dir(d)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(d, f"admin_{stamp}.log")


def write_log(lines: List[str], path: str) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def find_tesseract() -> Optional[str]:
    exe = shutil.which("tesseract")
    if exe:
        return exe
    for c in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if os.path.isfile(c):
            return c
    return None


def to_float(x: Optional[str]) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


# =========================
# Promo math
# =========================
def compute_effective_price(record: Dict[str, Any]) -> Optional[float]:
    """Return per-unit effective price given promo fields, with safety guards."""
    sale_price = to_float(record.get("sale_price"))
    regular = to_float(record.get("regular_price"))
    promo_type = (record.get("promo_type") or "").upper()
    qty = int(record.get("promo_qty") or 0)
    total = to_float(record.get("promo_price_total"))
    bogo_variant = (record.get("bogo_variant") or "").upper()  # "FREE", "50", etc.
    pct = to_float(record.get("percent_off"))

    # Simple price drop or unknown promo
    if promo_type in ("", "PRICE_DROP"):
        return sale_price if sale_price is not None else regular

    # Multi-buy (e.g., 2/$5, 10 for $10)
    if promo_type == "MULTI_BUY":
        if qty and qty > 0 and total:
            return round(total / qty, 4)
        # If OCR dropped the qty or total, fall back to a sane base
        base = sale_price if sale_price is not None else regular
        return base

    # BOGO variants
    if promo_type == "BOGO":
        base = sale_price if sale_price is not None else regular
        if base is None:
            return None
        if bogo_variant == "FREE":
            return round(base / 2.0, 4)  # buy one, get one free → avg 50%
        if bogo_variant in ("50", "50%"):
            return round(base * 0.75, 4)  # one at 100%, one at 50% → avg 75%
        return base

    # Percent off
    if promo_type == "PERCENT_OFF":
        base = sale_price if sale_price is not None else regular
        if base is not None and pct is not None:
            return round(base * (1 - pct / 100.0), 4)
        return base

    # Member price: treat sale_price as effective
    if promo_type == "MEMBER_PRICE":
        return sale_price if sale_price is not None else regular

    # Fallback
    return sale_price if sale_price is not None else regular


# =========================
# OCR parsing helpers
# =========================
_price_re = re.compile(r"\$?\s*(\d{1,3}(?:[.,]\d{2})?)")
_multibuy_re = re.compile(
    r"(?:(\d+)\s*/\s*\$?\s*(\d+(?:\.\d{2})?)|(\d+)\s*(?:for)\s*\$?\s*(\d+(?:\.\d{2})?))",
    re.I,
)
_bogo_free_re = re.compile(r"\b(BOGO|BUY\s*1\s*GET\s*1|BUY ONE GET ONE)\b.*(FREE)", re.I)
_bogo_50_re = re.compile(r"\b(BOGO|BUY\s*1\s*GET\s*1)\b.*(50%|\b50\b)", re.I)
_percent_off_re = re.compile(r"(\d{1,2})\s*%?\s*OFF", re.I)
_unit_markers = [
    ("lb", [" lb", "/lb", "per lb"]),
    ("ea", [" ea", " each"]),
    ("oz", [" oz", "/oz"]),
    ("ct", [" ct"]),
    ("pkg", [" pkg", " package"]),
]


def guess_unit(line: str) -> str:
    low = " " + line.lower() + " "
    for unit, keys in _unit_markers:
        for k in keys:
            if k in low:
                return unit
    return "ea"


def clean_item_name(text: str) -> str:
    t = re.sub(r"\$?\s*\d{1,3}(?:[.,]\d{2})?", "", text)
    t = re.sub(
        r"\b(BOGO|BUY\s*1\s*GET\s*1|FREE|WITH CARD|MEMBER PRICE|EACH|EA|LB|OZ|CT|PKG|PACKAGE|% OFF|FOR)\b",
        "",
        t,
        flags=re.I,
    )
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip(" ,.-")


def parse_line(line: str) -> Dict[str, Any]:
    """Parse one OCR text line into structured fields."""
    rec: Dict[str, Any] = {
        "item_name": None,
        "regular_price": None,
        "sale_price": None,
        "promo_type": None,
        "promo_qty": None,
        "promo_price_total": None,
        "effective_unit_price": None,
        "unit_type": None,
        "min_purchase_qty": None,
        "limit_per_customer": None,
        "member_only": False,
        "percent_off": None,
        "bogo_variant": None,
        "confidence_score": 0.5,
    }

    text = " ".join((line or "").strip().split())
    if not text:
        return rec

    low = text.lower()

    rec["unit_type"] = guess_unit(text)

    # Member-only
    if (
        "with card" in low
        or "digital coupon" in low
        or "members" in low
        or "member price" in low
    ):
        rec["promo_type"] = "MEMBER_PRICE"
        rec["member_only"] = True

    # Multi-buy
    m = _multibuy_re.search(text)
    if m:
        qty = m.group(1) or m.group(3)
        total = m.group(2) or m.group(4)
        if qty and total:
            try:
                rec["promo_type"] = "MULTI_BUY"
                rec["promo_qty"] = int(qty)
                rec["promo_price_total"] = float(total)
                # safe calc in compute_effective_price
                rec["sale_price"] = round(
                    rec["promo_price_total"] / max(rec["promo_qty"], 1), 4
                )
            except Exception:
                # leave fields; compute_effective_price will fall back gracefully
                pass

    # BOGO variants
    if _bogo_free_re.search(text):
        rec["promo_type"] = "BOGO"
        rec["bogo_variant"] = "FREE"
    elif _bogo_50_re.search(text):
        rec["promo_type"] = "BOGO"
        rec["bogo_variant"] = "50"

    # Percent off
    m = _percent_off_re.search(text)
    if m:
        rec["promo_type"] = "PERCENT_OFF"
        try:
            rec["percent_off"] = float(m.group(1))
        except Exception:
            pass

    # Prices present
    dollars = [p for p in _price_re.findall(text)]
    dollars = [d.replace(",", ".") for d in dollars]
    prices: List[float] = []
    for d in dollars:
        try:
            prices.append(round(float(d), 2))
        except Exception:
            pass

    # Heuristics for assigning prices
    if "reg" in low or "regular" in low:
        if prices:
            rec["regular_price"] = prices[-1]
            if len(prices) > 1:
                rec["sale_price"] = prices[0]
    else:
        if prices:
            rec["sale_price"] = prices[0]
            if len(prices) > 1:
                rec["regular_price"] = prices[1]

    if rec["sale_price"] is None and prices:
        rec["sale_price"] = prices[0]

    # Name
    name_guess = clean_item_name(text)
    if name_guess:
        rec["item_name"] = name_guess

    # Effective price with guards
    rec["effective_unit_price"] = compute_effective_price(rec)

    # Confidence heuristic
    score = 0.25
    if prices:
        score += 0.35
    if rec["item_name"]:
        score += 0.30
    if rec.get("regular_price") is not None and rec.get("sale_price") is not None:
        score += 0.10
    rec["confidence_score"] = max(0.05, min(score, 0.99))

    return rec


# =========================
# Parse OCR folder (with DEBUG reporting)
# =========================
def parse_ocr_folder(
    store: str, week: str, ocr_txt_dir: str, out_dir: str, log_lines: List[str], debug: bool
) -> Tuple[int, int, int]:
    """Parse all .txt in ocr_txt_dir -> CSV/JSON in out_dir. Returns (rows, low_conf, errors)."""
    ensure_dir(out_dir)
    rows: List[Dict[str, Any]] = []
    errors = 0
    low_conf = 0
    error_rows: List[Dict[str, str]] = []

    if not os.path.isdir(ocr_txt_dir):
        log_lines.append(f"[PARSE] No ocr dir found at {ocr_txt_dir}.")
        return 0, 0, 0

    txt_files = [f for f in sorted(os.listdir(ocr_txt_dir)) if f.lower().endswith(".txt")]
    for fname in txt_files:
        path = os.path.join(ocr_txt_dir, fname)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [ln.rstrip("\n") for ln in f]
        except Exception as e:
            errors += 1
            log_lines.append(f"[ERR] Unable to read {path}: {e}")
            if debug:
                error_rows.append({"file": fname, "line": "", "error": f"read_error: {e}"})
            continue

        for ln in lines:
            try:
                rec = parse_line(ln)
                if (
                    not rec.get("item_name")
                    and not rec.get("sale_price")
                    and not rec.get("regular_price")
                ):
                    continue  # skip empty/noise lines

                rec["store"] = store
                rec["week_code"] = week
                rec["source_file"] = fname
                rows.append(rec)
                if (rec.get("confidence_score") or 0) < 0.55:
                    low_conf += 1
            except Exception as e:
                errors += 1
                if debug:
                    error_rows.append({"file": fname, "line": ln[:300], "error": repr(e)})

    # Write CSV/JSON
    if rows:
        csv_path = os.path.join(out_dir, "parsed_items.csv")
        json_path = os.path.join(out_dir, "parsed_items.json")
        fieldnames = [
            "store",
            "week_code",
            "item_name",
            "regular_price",
            "sale_price",
            "promo_type",
            "promo_qty",
            "promo_price_total",
            "effective_unit_price",
            "unit_type",
            "min_purchase_qty",
            "limit_per_customer",
            "member_only",
            "percent_off",
            "bogo_variant",
            "confidence_score",
            "source_file",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) for k in fieldnames})

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

        log_lines.append(f"[PARSE] Wrote {len(rows)} items → {csv_path}")
    else:
        log_lines.append("[PARSE] No items parsed from OCR text.")

    # Write error CSV if debug + any errors
    if debug and error_rows:
        err_path = os.path.join(out_dir, "parse_errors.csv")
        with open(err_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["file", "line", "error"])
            w.writeheader()
            for r in error_rows:
                w.writerow(r)
        log_lines.append(f"[DEBUG] Wrote parse_errors.csv with {len(error_rows)} rows.")

    return len(rows), low_conf, errors


# =========================
# Option 1 — OCR + Parse
# =========================
def process_snips():
    root = project_root()
    default_store = "hannaford"

    store = safe_input(f"Store [default {default_store}]: ").strip().lower() or default_store
    store = store.replace(" ", "")

    wk_default = (
        latest_week_for_store(root, store)
        or latest_week_any(root)
        or current_week_code()
    )
    week = safe_input(f"Week code [default {wk_default}] (e.g. week47): ").strip() or wk_default
    if not WEEK_CODE_RE.match(week):
        print("❌ Week must look like 'weekNN' (for example: week47).")
        return

    debug = safe_input("Enable DEBUG report (parse_errors.csv)? [y/N]: ").strip().lower() in {
        "y",
        "yes",
    }

    week_root = os.path.join(root, "flyers", store, week)

    # New-style names
    raw_images = os.path.join(week_root, "raw_png")
    raw_pdfs = os.path.join(week_root, "raw_pdf")
    ocr_dir = os.path.join(week_root, "ocr")

    # Backwards-compat fallbacks if only old names exist
    if not os.path.isdir(raw_images):
        alt = os.path.join(week_root, "raw_images")
        if os.path.isdir(alt):
            raw_images = alt
    if not os.path.isdir(raw_pdfs):
        alt = os.path.join(week_root, "raw_pdfs")
        if os.path.isdir(alt):
            raw_pdfs = alt
    if not os.path.isdir(ocr_dir):
        alt = os.path.join(week_root, "ocr_txt")
        if os.path.isdir(alt):
            ocr_dir = alt

    out_dir = os.path.join(root, "output", store, week)
    ensure_dir(ocr_dir)
    ensure_dir(out_dir)

    if not os.path.isdir(week_root):
        print(f"❌ Week folder not found: {week_root}")
        return
    if not os.path.isdir(raw_images) and not os.path.isdir(raw_pdfs):
        print(
            f"❌ No inputs found.\nPut images/PDFs under:\n  {raw_images}\n  {raw_pdfs}"
        )
        return

    lines: List[str] = []
    lines.append(f"Process snips start: store={store}, week={week}, debug={debug}")

    # ----- OCR (images only for now)
    tess = find_tesseract()
    if not tess:
        print("❌ Tesseract not found. Install the UB Mannheim build or add to PATH.")
        return

    redo = safe_input("Re-run OCR for files that already have .txt? [y/N]: ").strip().lower() in {
        "y",
        "yes",
    }

    img_exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
    images: List[str] = []
    if os.path.isdir(raw_images):
        for name in sorted(os.listdir(raw_images)):
            if os.path.splitext(name)[1].lower() in img_exts:
                images.append(os.path.join(raw_images, name))

    wrote = skipped = ocr_errs = 0
    total_imgs = len(images)
    for idx, img in enumerate(images, start=1):
        base = os.path.splitext(os.path.basename(img))[0]
        out_txt = os.path.join(ocr_dir, base + ".txt")
        if os.path.exists(out_txt) and not redo:
            skipped += 1
            print(f"[{idx}/{total_imgs}] OCR skip: {base}.txt exists")
            continue
        try:
            out_noext = os.path.join(ocr_dir, base)
            cmd = [tess, img, out_noext, "--oem", "1", "--psm", "3"]
            print(f"[{idx}/{total_imgs}] OCR: {os.path.basename(img)} …")
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            wrote += 1
        except subprocess.CalledProcessError as e:
            ocr_errs += 1
            lines.append(f"[ERR] tesseract failed on {img}: {e}")

    if os.path.isdir(raw_pdfs):
        pdfs = [n for n in os.listdir(raw_pdfs) if n.lower().endswith(".pdf")]
    else:
        pdfs = []
    if pdfs:
        lines.append(
            f"[INFO] PDF OCR not enabled yet. {len(pdfs)} PDF(s) present in {raw_pdfs}."
        )

    lines.append(f"OCR summary: wrote={wrote}, skipped={skipped}, errors={ocr_errs}")

    # ----- Parsing (parse whatever exists in ocr_dir)
    parsed_rows, low_conf, parse_errs = parse_ocr_folder(
        store, week, ocr_dir, out_dir, lines, debug
    )
    lines.append(
        f"Parse summary: rows={parsed_rows}, low_conf={low_conf}, errors={parse_errs}"
    )

    # ----- Manifest + log
    manifest = os.path.join(out_dir, "ocr_manifest.txt")
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(
            f"store={store}\nweek={week}\ndebug={debug}\n"
            f"wrote={wrote}\nskipped={skipped}\nerrors={ocr_errs}\n"
        )

    log_file = log_path(root, store)
    write_log(lines, log_file)

    print("\n✅ OCR + Parse complete.")
    print(f"  OCR wrote:   {wrote}")
    print(f"  OCR skipped: {skipped}")
    print(f"  OCR errors:  {ocr_errs}")
    print(
        f"  Parsed rows: {parsed_rows}  (low_conf: {low_conf}, parse_errs: {parse_errs})"
    )
    print(f"  TXT out:     {ocr_dir}")
    print(f"  Parsed out:  {out_dir}\\parsed_items.csv")
    if debug:
        print(f"  Debug errs:  {out_dir}\\parse_errors.csv  (only if created)")
    print(f"  Log:         {log_file}")
    print("Next: Supabase upload + UI savings totals.")


# =========================
# Option 2 — Create week folder
# =========================
def create_new_week_folder():
    root = project_root()
    store = safe_input("Store name (e.g., wegmans, hannaford): ").strip().lower()
    if not store:
        print("No store provided. Aborting.")
        return
    store = store.replace(" ", "")

    wk_default = latest_week_for_store(root, store) or current_week_code()
    week = (
        safe_input(f"Week code [e.g., week47] (default {wk_default}): ").strip()
        or wk_default
    )
    if not WEEK_CODE_RE.match(week):
        print("Week must look like 'weekNN'. Aborting.")
        return

    week_root = os.path.join(root, "flyers", store, week)

    # New-style folders
    raw_png = os.path.join(week_root, "raw_png")
    raw_pdf = os.path.join(week_root, "raw_pdf")
    ocr_dir = os.path.join(week_root, "ocr")
    output_dir = os.path.join(root, "output", store, week)
    logs_dir = os.path.join(root, "logs", store)

    for d in (raw_png, raw_pdf, ocr_dir, output_dir, logs_dir):
        ensure_dir(d)

    # Optional: create legacy names too so old scripts don't explode
    for legacy in ("raw_images", "raw_pdfs", "ocr_txt"):
        ensure_dir(os.path.join(week_root, legacy))

    readme = os.path.join(week_root, "README.txt")
    if not os.path.exists(readme):
        with open(readme, "w", encoding="utf-8") as f:
            f.write(
                "Deals-4Me week folder\n"
                f"Store: {store}\nWeek:  {week}\n\n"
                "Put inputs in:\n"
                "- raw_png:  PNG/JPG\n"
                "- raw_pdf:  PDFs\n\n"
                "Outputs:\n- ocr: OCR results\n"
                f"- output/{store}/{week}: parsed/exported data\n"
            )

    print("\n✅ Created/verified folders:")
    for p in (raw_png, raw_pdf, ocr_dir, output_dir, logs_dir):
        print(f"  {p}")
    print("")


# =========================
# Option 3 / 4 / 5 / 6 / 7
# =========================
def rerun_ocr_for_store_week():
    print("[Stub] Re-run OCR for a store/week. Replace with your real implementation.")


def view_recent_logs():
    root = project_root()
    logs_root = os.path.join(root, "logs")
    if not os.path.isdir(logs_root):
        print("No logs yet.")
        return
    print("Recent logs (latest 10):")
    entries: List[Tuple[float, str]] = []
    for store in os.listdir(logs_root):
        sp = os.path.join(logs_root, store)
        if not os.path.isdir(sp):
            continue
        for name in os.listdir(sp):
            if name.lower().endswith(".log"):
                fp = os.path.join(sp, name)
                try:
                    entries.append((os.path.getmtime(fp), fp))
                except FileNotFoundError:
                    pass
    if not entries:
        print("  (none)")
        return
    for _, path in sorted(entries, reverse=True)[:10]:
        print("  " + path)


def rerun_ocr_all_stores():
    print("[Stub] Re-run OCR for ALL stores (this week). Replace with your real implementation.")


def preview_latest_parsed():
    """Option 6 — show the first ~20 rows of the latest parsed CSV across stores."""
    root = project_root()
    wk = latest_week_any(root)
    if not wk:
        print("No parsed weeks found yet.")
        return
    preview_for_week(wk)


def preview_for_week(week: str):
    root = project_root()
    out_root = os.path.join(root, "output")
    if not os.path.isdir(out_root):
        print("No output folder yet.")
        return

    found_path = None
    found_store = None
    for store in sorted(os.listdir(out_root)):
        sp = os.path.join(out_root, store, week)
        candidate = os.path.join(sp, "parsed_items.csv")
        if os.path.isfile(candidate):
            found_path = candidate
            found_store = store
            break

    if not found_path:
        print(f"No parsed_items.csv found for week {week}.")
        return

    print(f"\n📄 Previewing parsed_items.csv for store '{found_store}' week {week}:")
    print(f"File: {found_path}\n")
    try:
        with open(found_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i == 0:
                    print("HEADER →", line.strip(), "\n")
                else:
                    print(line.strip())
                if i >= 20:
                    print("\n(Showing first 20 rows…)")
                    break
    except Exception as e:
        print(f"Error reading preview: {e}")


def preview_pick_week():
    """Option 7 — choose a week to preview across stores."""
    root = project_root()
    flyers_root = os.path.join(root, "flyers")
    all_weeks = set()
    if os.path.isdir(flyers_root):
        for store in os.listdir(flyers_root):
            sp = os.path.join(flyers_root, store)
            if not os.path.isdir(sp):
                continue
            for wk in os.listdir(sp):
                if WEEK_CODE_RE.match(wk) and os.path.isdir(os.path.join(sp, wk)):
                    all_weeks.add(wk)
    weeks_sorted = sorted(all_weeks, key=lambda s: int(WEEK_CODE_RE.match(s).group(1)))
    if not weeks_sorted:
        print("No weeks found in flyers/.")
        return

    print("\nAvailable weeks:")
    print(" ".join(weeks_sorted[-20:]))
    week = safe_input("\nEnter week code (e.g. week47): ").strip()
    if not WEEK_CODE_RE.match(week):
        print("Invalid week.")
        return
    preview_for_week(week)


# =========================
# Menu
# =========================
def banner(current_week: Optional[str]) -> str:
    line = f"Current Week (latest): {current_week}" if current_week else "Current Week (latest): [none]"
    return f"""
=== Deals-4Me Mini Admin ===
{line}

1) Process snips (OCR + upload) for a store/week
2) Create new week folder for a store
3) Re-run OCR for a store/week
4) View recent logs
5) Re-run OCR for ALL stores (this week)
6) Preview parsed items (latest)
7) Preview parsed items (pick week)
0) Exit
"""


def run_menu():
    root = project_root()
    while True:
        wk = latest_week_any(root)
        print(banner(wk))
        choice = safe_input("Choose an option: ").strip().lower()
        if choice in {"0", "q", "quit", "exit"}:
            print("Bye! 👋")
            return
        try:
            if choice == "1":
                process_snips()
            elif choice == "2":
                create_new_week_folder()
            elif choice == "3":
                rerun_ocr_for_store_week()
            elif choice == "4":
                view_recent_logs()
            elif choice == "5":
                rerun_ocr_all_stores()
            elif choice == "6":
                preview_latest_parsed()
            elif choice == "7":
                preview_pick_week()
            else:
                print("Invalid choice. Try again.")
        except Exception as e:
            print(f"❌ Task error: {e}")
        print("")
        pause()


# =========================
# Entry
# =========================
if __name__ == "__main__":
    run_menu()
