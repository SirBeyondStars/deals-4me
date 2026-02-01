from __future__ import annotations
import subprocess
import sys
from pathlib import Path

def project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("usage: ocr_week_full.py <store> --week <wk_YYYYMMDD> --region <REGION>")
        return 2

    backend = project_root() / "files_to_run" / "backend"

    # ✅ FULL should call your multi-pass script (usually ocr_passes.py)
    target = backend / "ocr_passes.py"  # <-- change if your real file is different

    if not target.exists():
        print(f"[FATAL] Missing OCR target script: {target}")
        return 2

    cmd = [sys.executable, str(target), *args]
    print("[FULL] Delegating to:", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(project_root()))

if __name__ == "__main__":
    raise SystemExit(main())
