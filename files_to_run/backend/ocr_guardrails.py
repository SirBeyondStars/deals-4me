# site/scripts/ocr_guardrails.py
import csv
import os
from datetime import datetime, timezone

LOG_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "ocr_attempts.csv")


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

def log_ocr_attempt(
    store_id: str,
    week_code: str,
    source_file: str,
    attempt: int,
    status: str,              # "OK" or "FAIL"
    reason: str = "",
    details: str = "",
    log_path: str = LOG_PATH_DEFAULT,
) -> None:
    _ensure_dir(log_path)
    new_file = not os.path.exists(log_path)

    ts = datetime.now(timezone.utc).isoformat()
    row = {
        "timestamp_utc": ts,
        "store_id": store_id,
        "week_code": week_code,
        "source_file": source_file,
        "attempt": attempt,
        "status": status,
        "reason": reason,
        "details": details,
    }

    with open(log_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp_utc",
                "store_id",
                "week_code",
                "source_file",
                "attempt",
                "status",
                "reason",
                "details",
            ],
        )
        if new_file:
            w.writeheader()
        w.writerow(row)

def get_fail_count(
    store_id: str,
    week_code: str,
    source_file: str,
    log_path: str = LOG_PATH_DEFAULT,
) -> int:
    if not os.path.exists(log_path):
        return 0

    fails = 0
    with open(log_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if (
                row.get("store_id") == store_id
                and row.get("week_code") == week_code
                and row.get("source_file") == source_file
                and row.get("status") == "FAIL"
            ):
                fails += 1
    return fails
MANUAL_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "manual_ocr_needed.csv")


def mark_manual_needed(
    store_id: str,
    week_code: str,
    source_file: str,
    reason: str = "MAX_FAILS_REACHED",
    manual_path: str = MANUAL_PATH_DEFAULT,
) -> None:
    """Append a row once to manual_ocr_needed.csv so you know what needs manual entry."""
    # Avoid duplicates
    if os.path.exists(manual_path):
        with open(manual_path, "r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                if (
                    row.get("store_id") == store_id
                    and row.get("week_code") == week_code
                    and row.get("source_file") == source_file
                ):
                    return

    new_file = not os.path.exists(manual_path)
    ts = datetime.now(timezone.utc).isoformat()

    row = {
        "timestamp_utc": ts,
        "store_id": store_id,
        "week_code": week_code,
        "source_file": source_file,
        "reason": reason,
    }

    with open(manual_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if new_file:
            w.writeheader()
        w.writerow(row)
