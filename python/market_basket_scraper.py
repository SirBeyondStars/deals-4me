# market_basket_scraper.py — Market Basket JSON-focused scraper

from playwright.sync_api import sync_playwright
import pandas as pd
from pathlib import Path
import json, re, time

FLYER_URL = "https://www.shopmarketbasket.com/weekly-flyer"
STORE_NUM = 22865  # Market Basket - West Bridgewater, MA

OUT_CSV   = Path("market_basket_flyer.csv")
DEBUG_JSON = Path("mb_items.json")

money_re  = re.compile(r"(\d+(?:\.\d{1,2})?)")
multi_re  = re.compile(r"(?:(\d+)\s*(?:for|\/)\s*\$?\s*(\d+(?:\.\d{1,2})?))", re.I)

def parse_money(x):
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    s = str(x)
    m = money_re.search(s.replace(",", ""))
    return float(m.group(1)) if m else None

def parse_multi(text):
    if not text: return None, None
    m = multi_re.search(text)
    if m: return int(m.group(1)), float(m.group(2))
    if "bogo" in text.lower() or "buy one get one" in text.lower():
        return 2, None
    return None, None

def mine_products(root):
    """Yield (title, desc, sale_price, multi_buy, multi_price, start, end)."""
    if not isinstance(root, dict): return
    dates = root.get("dates") or {}
    start = dates.get("start_date") or ""
    end   = dates.get("end_date") or ""

    prods = root.get("products") or []
    for p in prods:
        if not isinstance(p, dict): continue
        title = p.get("name") or ""
        desc  = p.get("description") or ""
        deal_pricing = p.get("deal_pricing")  # number or string
        deal_text    = p.get("deal_text")     # e.g., "2 for $5" or extra context
        sale_price   = parse_money(deal_pricing if deal_pricing not in (None, "") else deal_text)
        mb, mp       = parse_multi(deal_text)
        if title and sale_price is not None:
            yield title, desc, sale_price, mb, mp, start, end

def main():
    captured = []

    # 1) Load page and capture JSON
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        def on_response(resp):
            try:
                ctype = (resp.headers.get("content-type") or "").lower()
                if "json" in ctype and any(k in resp.url.lower() for k in ["flyer","weekly","products","circular","ad"]):
                    captured.append({"url": resp.url, "json": resp.json()})
            except: pass

        page.on("response", on_response)
        page.goto(FLYER_URL, wait_until="domcontentloaded")
        # give it time to request JSON
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(2)
        browser.close()

    if captured:
        DEBUG_JSON.write_text(json.dumps(captured, indent=2), encoding="utf-8")

    # 2) Parse the JSON we captured
    rows = []
    for pack in captured:
        root = pack.get("json", pack)
        # either a dict with products/dates, or a list of such dicts
        if isinstance(root, dict):
            for t, d, sp, mb, mp, s, e in mine_products(root):
                rows.append({
                    "store_num": STORE_NUM,
                    "product_id": "",
                    "upc": "",
                    "regular_price": "",
                    "sale_price": sp,
                    "multi_buy": mb or "",
                    "multi_price": mp or "",
                    "promo_text": d,
                    "sale_start": s,
                    "sale_end": e,
                    "unit_price": "",
                    "unit_size": "",
                })
        elif isinstance(root, list):
            for obj in root:
                if isinstance(obj, dict):
                    for t, d, sp, mb, mp, s, e in mine_products(obj):
                        rows.append({
                            "store_num": STORE_NUM,
                            "product_id": "",
                            "upc": "",
                            "regular_price": "",
                            "sale_price": sp,
                            "multi_buy": mb or "",
                            "multi_price": mp or "",
                            "promo_text": d,
                            "sale_start": s,
                            "sale_end": e,
                            "unit_price": "",
                            "unit_size": "",
                        })

    # 3) Save CSV in your staging shape
    out_cols = [
        "store_num","product_id","upc","regular_price","sale_price",
        "multi_buy","multi_price","promo_text","sale_start","sale_end",
        "unit_price","unit_size"
    ]
    pd.DataFrame(rows, columns=out_cols).to_csv(OUT_CSV, index=False)
    print(f"Saved {len(rows)} rows -> {OUT_CSV.resolve()}")
    if rows[:3]:  # show a tiny preview in console
        print("Example:", rows[:3])

if __name__ == "__main__":
    main()
