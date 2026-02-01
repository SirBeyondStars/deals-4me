from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
import re

# ---- Tool paths (locked) ----
TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_BIN = r"C:\Users\jwein\Downloads\Release-25.07.0-0 (2)\poppler-25.07.0\Library\bin"

# ---- Pass names (locked) ----
PASS_RAW = "tesseract:raw"
PASS_CLAHE = "tesseract:clahe_contrast"

# ---- Signal regex ----
PRICE_RE = re.compile(r"\b\d+\.\d{2}\b")
DOLLAR_RE = re.compile(r"\$\s*\d")

# ---- Knobs (tune here) ----
RAW_SIGNAL_TRIGGER = 10   # if raw score < this, we try CLAHE
WEAK_SIGNAL_ALWAYS = 6    # if score < this, always weak (forces CLAHE)

# --- OCR tuning (WF tiles benefit from this) ---
TESS_LANG = "eng"
TESS_CONFIG = "--oem 3 --psm 6"  # 6 = assume a block of text; good for “deal tile” crops

# --- WF percent-off repair (OCR sometimes drops % or mangles "off") ---
_WF_OFF_RE = re.compile(r"(?<!\d)([0-9Il|]{1,2})\s*(?:o|O)?\s*off\b", re.IGNORECASE)
_WF_OFF_SPLIT_RE = re.compile(r"\b(o\s*f\s*f)\b", re.IGNORECASE)
_WF_PERCENT_GLYPHS_RE = re.compile(r"[％°º]")


def _repair_wf_percent_off(text: str) -> str:
    if not text:
        return text

    t = text

    # normalize common "percent-looking" glyphs
    t = _WF_PERCENT_GLYPHS_RE.sub("%", t)

    # glue "o f f" -> "off"
    t = _WF_OFF_SPLIT_RE.sub("off", t)

    tl = t.lower()

    # Only do the aggressive "% off" insertion when it's clearly WF tiles
    wf_context = ("prime" in tl) or ("with prime" in tl)

    # If we already have a %, just try to normalize "0ff" -> "off"
    if "%" in t:
        t = re.sub(r"\b0ff\b", "off", t, flags=re.IGNORECASE)
        return t

    if not wf_context:
        return t

    def _norm_pct(s: str) -> str:
        return (
            s.replace("I", "1")
             .replace("l", "1")
             .replace("|", "1")
        )

    # "19 off with Prime" -> "19% off with Prime"
    t = _WF_OFF_RE.sub(lambda m: f"{_norm_pct(m.group(1))}% off", t)
    return t


def prep_for_ocr(img):
    """
    Make small UI tiles readable:
      - grayscale
      - upscale (2x/3x)
      - autocontrast + stronger contrast
      - sharpen
      - light binarize
    """
    from PIL import ImageOps, ImageEnhance  # type: ignore
    from PIL.Image import Resampling  # type: ignore

    g = img.convert("L")

    w, h = g.size
    scale = 3 if min(w, h) < 450 else 2
    g = g.resize((w * scale, h * scale), resample=Resampling.LANCZOS)

    g = ImageOps.autocontrast(g, cutoff=1)
    g = ImageEnhance.Contrast(g).enhance(2.1)
    g = ImageEnhance.Sharpness(g).enhance(1.6)

    # Light threshold (helps thin text)
    g = g.point(lambda p: 0 if p < 165 else 255)

    return g


def ensure_ocr_work_dir(week_path: Path) -> Path:
    d = week_path / "ocr_work"
    d.mkdir(parents=True, exist_ok=True)
    return d


def score_deal_signal(text: Optional[str]) -> int:
    """
    Higher = better chance OCR captured deal-like content.
    """
    if not text:
        return 0
    t = text.strip()
    if not t:
        return 0

    score = 0
    if DOLLAR_RE.search(t):
        score += 8
    score += 4 * len(PRICE_RE.findall(t))  # each X.XX is valuable

    digits = sum(ch.isdigit() for ch in t)
    score += min(6, digits // 20)

    score += min(6, len(t) // 200)
    return score


def make_clahe_enhanced(img):
    """
    True CLAHE if opencv is available; otherwise safe PIL contrast fallback.
    Returns (enhanced_image_for_tesseract, mode_name)
    """
    try:
        import numpy as np  # type: ignore
        import cv2  # type: ignore
        from PIL import Image  # type: ignore

        arr = np.array(img.convert("L"))
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        out = clahe.apply(arr)
        enhanced = Image.fromarray(out)
        return enhanced, "clahe_contrast"

    except Exception:
        from PIL import ImageOps, ImageEnhance  # type: ignore
        g = img.convert("L")
        g = ImageOps.autocontrast(g, cutoff=2)
        g = ImageEnhance.Contrast(g).enhance(1.7)
        g = ImageEnhance.Sharpness(g).enhance(1.3)
        return g, "autocontrast_fallback"


def is_weak_ocr(text: Optional[str], *, raw_signal_trigger: int = RAW_SIGNAL_TRIGGER) -> bool:
    """
    Weak OCR decision is based on text content only.
    (Price-based decisions happen in ingest_shared when we have price_rules.)
    """
    if not text or len(text.strip()) < 40:
        return True

    signal = score_deal_signal(text)

    if signal < WEAK_SIGNAL_ALWAYS:
        return True

    if signal < raw_signal_trigger:
        return True

    return False


def try_ocr_image(
    path: Path,
    week_path: Path,
    *,
    raw_signal_trigger: int = RAW_SIGNAL_TRIGGER,
) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Returns ALWAYS 3 values:
      (ocr_text, ocr_name, clahe_file_written_or_none)

    Steps:
      1) raw OCR
      2) if weak -> CLAHE fallback
      3) keep whichever has higher deal signal (tie: keep raw)
    """
    raw_name = PASS_RAW
    clahe_name = PASS_CLAHE
    clahe_written: Optional[str] = None

    try:
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore

        pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

        img = Image.open(path)

        # ✅ ACTUALLY OCR THE PREPPED IMAGE + PASS CONFIG
        raw_img = prep_for_ocr(img)
        raw_text = _repair_wf_percent_off(
            (pytesseract.image_to_string(raw_img, lang=TESS_LANG, config=TESS_CONFIG) or "").strip()
        )

        # WF/tile safeguard: skip image-only / junk tiles early
        def looks_like_real_text(t: str) -> bool:
            if not t:
                return False
            t = t.strip()
            if len(t) < 25:
                return False
            if not any(ch.isalnum() for ch in t):
                return False
            return True

        if not looks_like_real_text(raw_text):
            return None, "img_only_tile", None

        if is_weak_ocr(raw_text, raw_signal_trigger=raw_signal_trigger):
            enhanced, _mode = make_clahe_enhanced(img)

            ocr_work = ensure_ocr_work_dir(week_path)
            clahe_path = ocr_work / f"{path.stem}__clahe_contrast.png"
            enhanced.save(clahe_path)
            clahe_written = str(clahe_path).replace("\\", "/")

            # ✅ OCR PREPPED ENHANCED IMAGE + PASS CONFIG
            clahe_img = prep_for_ocr(enhanced)
            clahe_text = _repair_wf_percent_off(
                (pytesseract.image_to_string(clahe_img, lang=TESS_LANG, config=TESS_CONFIG) or "").strip()
            )

            raw_score = score_deal_signal(raw_text)
            clahe_score = score_deal_signal(clahe_text)

            if clahe_score > raw_score:
                return (clahe_text if clahe_text else None), clahe_name, clahe_written

            return (raw_text if raw_text else None), raw_name, clahe_written

        return (raw_text if raw_text else None), raw_name, None

    except Exception as e:
        msg = str(e).replace("\n", " ").strip()[:180]
        return None, f"img_ocr_error:{msg}", None


def try_ocr_pdf(path: Path) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Returns ALWAYS 3 values (3rd is always None).
    """
    try:
        from pdf2image import convert_from_path  # type: ignore
        import pytesseract  # type: ignore

        pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

        pages = convert_from_path(str(path), dpi=300, poppler_path=POPPLER_BIN)
        texts: List[str] = []
        for img in pages:
            # ✅ optional: also prep pages (can help small text)
            prepped = prep_for_ocr(img)
            t = _repair_wf_percent_off(
                (pytesseract.image_to_string(prepped, lang=TESS_LANG, config=TESS_CONFIG) or "").strip()
            )
            if t:
                texts.append(t)

        full_text = "\n\n".join(texts).strip()
        return (full_text if full_text else None), "pdf2image+tesseract", None

    except Exception as e:
        msg = str(e).replace("\n", " ").strip()[:180]
        return None, f"pdf_ocr_error:{msg}", None
