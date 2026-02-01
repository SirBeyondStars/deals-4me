# site/files_to_run/backend/ingest_shared.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple
import os
import re
import requests

from ocr_passes import PASS_CLAHE, score_deal_signal


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
PDF_EXTS = {".pdf"}


def iso_week_now() -> int:
    return datetime.now().isocalendar().week


def normalize_week_code(raw: str) -> str:
    s = (raw or "").strip().lower().replace(" ", "")
    m = re.fullmatch(r"week(\d{1,2})", s)
    if m:
        return f"week{int(m.group(1))}"
    m2 = re.fullmatch(r"(\d{1,2})", s)
    if m2:
        return f"week{int(m2.group(1))}"
    return s


def resolve_week_path(p: Path) -> Path:
    # Accept ...\week51, ...\week51\raw_png, ...\week51\raw_pdf
    if p.name.lower() in ("raw_png", "raw_pdf"):
        return p.parent
    return p


def list_media_files(week_path: Path) -> List[Path]:
    """
    Collect media from:
      - week root
      - raw_png/
      - raw_pdf/

    Rule: If ANY images exist, ignore PDFs entirely.
    """
    files: List[Path] = []
    if not week_path.exists():
        return files

    search_dirs = [week_path, week_path / "raw_png", week_path / "raw_pdf"]

    for d in search_dirs:
        if not d.exists() or not d.is_dir():
            continue
        for p in d.iterdir():
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            if ext in IMAGE_EXTS or ext in PDF_EXTS:
                name_l = p.name.lower()
                if name_l in ("date.png", "date.jpg", "date.jpeg"):
                    continue
                files.append(p)

    has_images = any(p.suffix.lower() in IMAGE_EXTS for p in files)
    if has_images:
        files = [p for p in files if p.suffix.lower() in IMAGE_EXTS]

    files.sort()
    return files


def supabase_headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def insert_rows_supabase(url: str, key: str, table: str, rows: List[dict]) -> Tuple[bool, str]:
    endpoint = url.rstrip("/") + f"/rest/v1/{table}"
    r = requests.post(endpoint, headers=supabase_headers(key), json=rows, timeout=60)
    if 200 <= r.status_code < 300:
        return True, "ok"
    return False, f"HTTP {r.status_code}: {r.text[:300]}"


def fetch_existing_source_files(url: str, key: str, table: str, *, store_id: int, week_code: str) -> Set[str]:
    endpoint = (
        url.rstrip("/")
        + f"/rest/v1/{table}"
        + "?select=source_file"
        + f"&flyer_store_id=eq.{store_id}"
        + f"&week_code=eq.{week_code}"
    )
    r = requests.get(endpoint, headers=supabase_headers(key), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"duplicate guard HTTP {r.status_code}: {r.text[:200]}")
    return {row["source_file"] for row in r.json() if row.get("source_file")}


def compute_manual_review_reason(
    *,
    ocr_text: Optional[str],
    ocr_name: Optional[str],
    sale_price: Optional[float],
    regular_price: Optional[float],
    too_short_len: int = 80,
    weak_signal_threshold: int = 10,
) -> Optional[str]:
    """
    Single place to decide manual review reason.

    Reasons:
      - clahe_no_price
      - ocr_no_price
      - ocr_too_short
      - weak_price_signal
    """
    if not ocr_text:
        return None

    t = ocr_text.strip()
    if not t:
        return None

    if sale_price is None and regular_price is None:
        if ocr_name == PASS_CLAHE:
            return "clahe_no_price"
        return "ocr_no_price"

    if len(t) < too_short_len:
        return "ocr_too_short"

    if score_deal_signal(t) < weak_signal_threshold:
        return "weak_price_signal"

    return None


def get_supabase_creds() -> Tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_KEY", "").strip())
    if not url or not key:
        raise RuntimeError("Missing Supabase credentials (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY).")
    return url, key
