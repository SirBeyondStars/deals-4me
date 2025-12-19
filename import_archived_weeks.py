"""
import_archived_weeks.py

Historical importer for Deals-4Me.

What it does:
- Scans deals-4me-archived-files/ (your archive)
- For each (week_code, store_slug) with real files:
    - Counts PDFs + images
    - Records the relative path to that week folder
- Upserts rows into the Supabase table `archive_weeks`
  using PostgREST (REST API).

SAFE:
- Read-only on your filesystem.
- Uses upsert with unique (week_code, store_slug) so running
  it multiple times won't create duplicates.

Requires:
- Python 3
- `requests` library  (pip install requests)
- .env file in this directory with:
    SUPABASE_URL=...
    SUPABASE_SERVICE_ROLE_KEY=...

Table schema (already shared):
    archive_weeks(
      id bigint PK,
      week_code text,
      store_slug text,
      pdf_count int,
      image_count int,
      root_path text,
      created_at timestamptz,
      unique (week_code, store_slug)
    )
"""

from pathlib import Path
import os
import json
import requests

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
ARCHIVE_ROOT = PROJECT_ROOT / "deals-4me-archived-files"
ENV_PATH = PROJECT_ROOT / ".env"

PDF_EXTS = {".pdf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}

SUPABASE_TABLE = "archive_weeks"

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def load_env(path: Path):
    """Very small .env loader (doesn't overwrite existing env vars)."""
    if not path.is_file():
        print(f"[env] No .env file found at {path}, relying on OS env vars.")
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def is_week_folder(name: str) -> bool:
    """
    Heuristic for week/date folder names:
    - 'Week46', 'week48', etc.
    - 6-digit date codes like 102925 (MMDDYY)
    """
    lower = name.lower()
    if lower.startswith("week") and lower[4:].isdigit():
        return True
    if len(name) == 6 and name.isdigit():
        return True
    return False


def count_files_in_week(week_path: Path):
    """
    Count PDFs and images in a week folder, checking:
    - directly under the week folder
    - pdf/
    - raw_images/
    - raw_images_hd/
    """
    pdf_count = 0
    img_count = 0

    # Direct files
    for p in week_path.iterdir():
        if p.is_file():
            ext = p.suffix.lower()
            if ext in PDF_EXTS:
                pdf_count += 1
            elif ext in IMAGE_EXTS:
                img_count += 1

    # Common subfolders
    for sub in ["pdf", "raw_images", "raw_images_hd"]:
        sdir = week_path / sub
        if not sdir.is_dir():
            continue
        for p in sdir.rglob("*"):
            if p.is_file():
                ext = p.suffix.lower()
                if ext in PDF_EXTS:
                    pdf_count += 1
                elif ext in IMAGE_EXTS:
                    img_count += 1

    return pdf_count, img_count


def scan_archive(root: Path):
    """
    Scan deals-4me-archived-files and build a list of rows:

    [
      {
        "week_code": "102925",
        "store_slug": "aldi",
        "pdf_count": 1,
        "image_count": 37,
        "root_path": "aldi/102925"
      },
      ...
    ]
    """
    if not root.is_dir():
        raise SystemExit(f"[ERROR] Archive root not found: {root}")

    print(f"[scan] Scanning archive root: {root}")
    rows = []

    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir():
            continue

        name = entry.name

        # Case 1: Week folders directly under archive root (rare in your setup)
        if is_week_folder(name):
            week_code = name
            pdfs, imgs = count_files_in_week(entry)
            if pdfs == 0 and imgs == 0:
                continue
            rel = entry.relative_to(root)
            rows.append(
                {
                    "week_code": week_code,
                    "store_slug": "(mixed-or-unknown)",
                    "pdf_count": pdfs,
                    "image_count": imgs,
                    "root_path": str(rel).replace("\\", "/"),
                }
            )
            continue

        # Case 2: Store folders like 'aldi', 'big_y', etc.
        store_slug = name
        for week_entry in sorted(entry.iterdir(), key=lambda p: p.name.lower()):
            if not week_entry.is_dir():
                continue
            if not is_week_folder(week_entry.name):
                # skip 'logs', etc.
                continue

            week_code = week_entry.name
            pdfs, imgs = count_files_in_week(week_entry)
            if pdfs == 0 and imgs == 0:
                # Completely empty → ignore
                continue

            rel = week_entry.relative_to(root)
            rows.append(
                {
                    "week_code": week_code,
                    "store_slug": store_slug,
                    "pdf_count": pdfs,
                    "image_count": imgs,
                    "root_path": str(rel).replace("\\", "/"),
                }
            )

    print(f"[scan] Found {len(rows)} (week, store) combos with files.")
    return rows


def get_supabase_config():
    load_env(ENV_PATH)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv(
        "SUPABASE_SERVICE_KEY"
    )

    if not url or not key:
        raise SystemExit(
            "[ERROR] Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in env/.env"
        )

    return url.rstrip("/"), key


def upsert_archive_rows(rows):
    if not rows:
        print("[import] Nothing to import.")
        return

    url, key = get_supabase_config()
    endpoint = f"{url}/rest/v1/{SUPABASE_TABLE}"

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # tells PostgREST to upsert based on unique constraint
        "Prefer": "resolution=merge-duplicates",
    }

    total = len(rows)
    batch_size = 50
    sent = 0

    print(f"[import] Upserting {total} rows into '{SUPABASE_TABLE}'...")

    for i in range(0, total, batch_size):
        batch = rows[i : i + batch_size]
        resp = requests.post(endpoint, headers=headers, data=json.dumps(batch))
        if not resp.ok:
            print(
                f"[import] ERROR on batch {i//batch_size + 1}: {resp.status_code} {resp.text}"
            )
            raise SystemExit(1)

        sent += len(batch)
        print(f"[import]  -> batch {i//batch_size + 1} OK ({sent}/{total})")

    print("[import] Done. You can query archive_weeks in Supabase now.")


def main():
    rows = scan_archive(ARCHIVE_ROOT)
    if not rows:
        print("[main] No data found to import.")
        return
    upsert_archive_rows(rows)


if __name__ == "__main__":
    main()
