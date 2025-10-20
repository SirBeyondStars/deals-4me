# base_scraper.py
# Reusable engine that supports multiple modes (json/html/pdf).
# Start with JSON (works today). We'll plug in HTML/PDF extractors next.

from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Dict, Any, List
import csv
import time
import re
import json

from playwright.sync_api import sync_playwright

money_re  = re.compile(r"(\d+(?:\.\d{1,2})?)")
multi_re  = re.compile(r"(?:(\d+)\s*(?:for|\/)\s*\$?\s*(\d+(?:\.\d{1,2})?))", re.I)

@dataclass
class ChainConfig:
    chain_name: str
    store_num: int
    url: str
    mode: str                          # "json" | "html" | "pdf"
    json_item_path: List[str] = None   # e.g. ["products"]
    json_fields: Dict[str, str] = None # map logical fields -> json keys, e.g. {"name":"name","desc":"description","sale":"deal_pricing","deal_text":"deal_text"}
    out_csv: str = "flyer.csv"

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

def _walk_to_path(root, path_parts: List[str]):
    """Walk a nested dict/list using simple key steps (no wildcards)."""
    node = root
    for part in path_parts or []:
        if isinstance(node, dict):
            node = node.get(part, [])
        else:
            return []
    return node if isinstance(node, list) else []

def _scrape_json(conf: ChainConfig) -> List[Dict[str, Any]]:
    """Capture JSON network responses at conf.url and extract items."""
    captured: List[dict] = []
    rows: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        def on_response(resp):
            try:
                ctype = (resp.headers.get("content-type") or "").lower()
                if "json" in ctype and any(k in resp.url.lower() for k in ["flyer","weekly","circular","ad","products","special"]):
                    captured.append(resp.json())
            except:
                pass

        page.on("response", on_response)
        page.goto(conf.url, wait_until="domcontentloaded")
        # let JS kick in & requests fire
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(1.5)
        browser.close()

    # save debug
    Path("debug").mkdir(exist_ok=True)
    Path(f"debug/{conf.chain_name}_raw.json").write_text(json.dumps(captured, indent=2), encoding="utf-8")

    # mine data
    for pack in captured:
        # dates (optional, if present)
        start = ""
        end   = ""
        if isinstance(pack, dict) and isinstance(pack.get("dates"), dict):
            start = pack["dates"].get("start_date", "") or start
            end   = pack["dates"].get("end_date", "") or end

        items = []
        if conf.json_item_path:
            items = _walk_to_path(pack, conf.json_item_path)
        # also support array of packs
        if not items and isinstance(pack, list):
            for obj in pack:
                if isinstance(obj, dict):
                    items += _walk_to_path(obj, conf.json_item_path or [])

        for it in items:
            if not isinstance(it, dict): 
                continue
            name = it.get(conf.json_fields.get("name","name"), "")
            desc = it.get(conf.json_fields.get("desc","description"), "")
            sale_raw = it.get(conf.json_fields.get("sale","price"))
            deal_text = it.get(conf.json_fields.get("deal_text","deal_text"), "")

            sale_price = parse_money(sale_raw if sale_raw not in (None, "") else deal_text)
            mb, mp = parse_multi(deal_text)
            if name and sale_price is not None:
                rows.append({
                    "store_num": conf.store_num,
                    "product_id": "",
                    "upc": it.get("upc") or it.get("UPC") or "",
                    "regular_price": "",
                    "sale_price": sale_price,
                    "multi_buy": mb or "",
                    "multi_price": mp or "",
                    "promo_text": desc or deal_text or "",
                    "sale_start": start,
                    "sale_end": end,
                    "unit_price": "",
                    "unit_size": it.get("size") or it.get("packageSize") or "",
                })
    return rows

def _scrape_html(conf: ChainConfig) -> List[Dict[str, Any]]:
    """
    Placeholder for HTML-mode chains.
    Strategy: load page, wait, query selectors, parse name/price/promo.
    We'll implement this when we add your first HTML chain.
    """
    # TODO: implement when we add an HTML-first chain (e.g., Roche Bros static page).
    return []

def _scrape_pdf(conf: ChainConfig) -> List[Dict[str, Any]]:
    """
    Placeholder for PDF-mode chains.
    Strategy: download PDF -> extract text w/ pdfplumber -> regex prices.
    """
    # TODO: implement when we add your first PDF chain.
    return []

def scrape_chain(conf: ChainConfig) -> Path:
    if conf.mode == "json":
        rows = _scrape_json(conf)
    elif conf.mode == "html":
        rows = _scrape_html(conf)
    elif conf.mode == "pdf":
        rows = _scrape_pdf(conf)
    else:
        raise ValueError(f"Unknown mode: {conf.mode}")

    out_cols = [
        "store_num","product_id","upc","regular_price","sale_price",
        "multi_buy","multi_price","promo_text","sale_start","sale_end",
        "unit_price","unit_size"
    ]
    out = Path(conf.out_csv)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in out_cols})

    print(f"Saved {len(rows)} rows -> {out.resolve()}")
    return out
