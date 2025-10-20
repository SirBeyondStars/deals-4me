# OCR all Hannaford images for week 100925
from pathlib import Path
from PIL import Image
import pytesseract

# paths for THIS run
BASE = Path(r"C:\Users\jwein\OneDrive\Desktop\deals-4me\flyers\hannaford\100925")
RAW  = BASE / "raw_images"
OUT  = BASE / "ocr_text"
OUT.mkdir(parents=True, exist_ok=True)

# tell pytesseract where the exe is
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

exts = {".jpg", ".jpeg", ".png"}
images = [p for p in RAW.iterdir() if p.suffix.lower() in exts]
print(f"Found {len(images)} image(s) in {RAW}")

for img_path in images:
    out_txt = OUT / (img_path.stem + ".txt")
    print(f"[OCR] {img_path.name} -> {out_txt.name}")
    img = Image.open(img_path).convert("RGB")
    text = pytesseract.image_to_string(img, config="--psm 6")
    out_txt.write_text(text, encoding="utf-8")

print("✅ OCR complete. Check the ocr_text folder.")
