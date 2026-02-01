# files_to_run/backend/test_ocr_one_folder.py
from pathlib import Path
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_ocr_one_folder.py <folder_path_to_pngs>")
        sys.exit(1)

    folder = Path(sys.argv[1]).expanduser()
    if not folder.exists() or not folder.is_dir():
        print(f"Folder not found: {folder}")
        sys.exit(1)

    # Import your OCR function (this is the one you just edited)
    from date_ocr_runner import ocr_image
	
    pngs = sorted(folder.glob("*.png"))
    if not pngs:
        print(f"No PNGs found in: {folder}")
        sys.exit(1)

    first = pngs[0]
    print(f"[test] Using first PNG: {first.name}")
    print(f"[test] Full path: {first}")

    text = ocr_image(first)

    print("\n[test] OCR text preview (first 500 chars):")
    preview = (text or "").replace("\r", "")
    print(preview[:500] if preview else "(no text returned)")

    print("\n[test] If guardrails are wired, this file should now exist:")
    print(r"files_to_run\backend\ocr_attempts.csv")

if __name__ == "__main__":
    main()
