# parse_flyer_text.py — turns one OCR .txt into a .csv (generic; week/store passed in)
import re, csv, sys, argparse
from pathlib import Path

PRICE_RE = re.compile(r'(?<!\d)(\d+)\s*for\s*\$?(\d+(?:\.\d{2})?)', re.I)  # 2 for 5
EACH_RE  = re.compile(r'\$?(\d+(?:\.\d{2}))\s*(?:ea|each)?', re.I)          # 3.99 ea
SAVE_RE  = re.compile(r'Save\s*\$?(\d+(?:\.\d{2}))', re.I)
REG_RE   = re.compile(r'Reg(?:ular)?\s*\$?(\d+(?:\.\d{2}))', re.I)
BOGO_RE  = re.compile(r'\bBOGO\b|\bBuy\s*1\s*Get\s*1\b', re.I)
SIZE_RE  = re.compile(r'\b(oz|lb|ct|pk|pack|gal|fl\s?oz)\b', re.I)

def guess_line_items(text: str):
    chunks = re.split(r'\n{2,}|•|-{3,}', text)
    return [c.strip() for c in chunks if c.strip()]

def normalize(block: str):
    deal_raw = None; qty = None; sale = None; unit = None; reg = None; save_raw = None

    m = PRICE_RE.search(block)
    if m:
        qty = int(m.group(1)); sale = float(m.group(2)); unit = round(sale/qty, 2); deal_raw = m.group(0)
    else:
        m2 = EACH_RE.search(block)
        if m2:
            qty = 1; sale = float(m2.group(1)); unit = sale; deal_raw = m2.group(0)

    if BOGO_RE.search(block): deal_raw = (deal_raw + " + BOGO") if deal_raw else "BOGO"

    m3 = SAVE_RE.search(block)
    if m3: save_raw = f"Save ${m3.group(1)}"
    m4 = REG_RE.search(block)
    if m4:
        reg = float(m4.group(1))
        if sale is None and m3:
            try:
                save_amt = float(m3.group(1))
                sale = round(reg - save_amt, 2); unit = sale
                deal_raw = (deal_raw + f" | {save_raw}") if deal_raw else save_raw
            except: pass

    first = block.splitlines()[0] if '\n' in block else block[:120]
    name = PRICE_RE.sub('', first)
    name = EACH_RE.sub('', name)
    name = BOGO_RE.sub('', name)
    name = re.sub(r'\s{2,}', ' ', name).strip(' -•:|')

    size=''; variant=''
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    if len(lines)>=2:
        if SIZE_RE.search(lines[1]): size = lines[1]
        else: variant = lines[1][:80]

    return dict(
        product_name=name or "Unknown",
        variant=variant, size=size, deal_raw=deal_raw or "",
        qty=qty or "", sale_price=f"{sale:.2f}" if sale is not None else "",
        unit_price=f"{unit:.2f}" if unit is not None else "",
        reg_price=f"{reg:.2f}" if reg is not None else "",
        savings_raw=save_raw or ""
    )

def main(in_txt: Path, week_start: str, week_end: str, store_name: str, store_id: str):
    text = in_txt.read_text(encoding="utf-8", errors="ignore")
    rows = [normalize(b) for b in guess_line_items(text)]

    # derive the current week's /parsed/ folder from the input path:
    # ...\<store>\<week>\(ocr_text|manual_text)\file.txt  ->  ...\<store>\<week>\parsed\file.csv
    week_dir = in_txt.parent.parent
    out_csv = week_dir / "parsed" / (in_txt.stem + ".csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["chain_name","store_id","store_city","store_state","flyer_week_start","flyer_week_end",
                    "product_name","variant","size","deal_raw","qty","sale_price","unit_price","reg_price",
                    "savings_raw","category","source_type","source_url","notes"])
        for r in rows:
            w.writerow([
                store_name, store_id, "", "", week_start, week_end,
                r["product_name"], r["variant"], r["size"], r["deal_raw"], r["qty"],
                r["sale_price"], r["unit_price"], r["reg_price"], r["savings_raw"],
                "", "manual-ocr", "", ""
            ])
    print(f"Wrote {out_csv}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("in_txt")
    ap.add_argument("--week-start", default="")
    ap.add_argument("--week-end", default="")
    ap.add_argument("--store", default="Hannaford")
    ap.add_argument("--store-id", default="1005")
    args = ap.parse_args()
    main(Path(args.in_txt), args.week_start, args.week_end, args.store, args.store_id)
