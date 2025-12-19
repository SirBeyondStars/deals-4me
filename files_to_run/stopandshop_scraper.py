# stopandshop_scraper.py
from pathlib import Path as _P
import sys
sys.path.append(str(_P(__file__).resolve().parent))  # import local engine

from base_scraper import ChainConfig, scrape_chain

conf = ChainConfig(
    chain_name="StopAndShop",
    store_num=475,  # label; optional
    url="https://stopandshop.com/savings/weekly-ad/grid-view",
    mode="html",
    # We'll confirm these after the first debug file:
    json_item_path=["products"],          # adjust after inspecting debug/StopAndShop_raw.json
    json_fields={
        "name": "name",
        "desc": "description",
        "sale": "price",                  # try "salePrice" or similar if needed
        "deal_text": "deal_text"          # try "promoText"/"offer" if needed
    },
    out_csv="out/stopandshop_flyer.csv"
)

if __name__ == "__main__":
    here = _P(__file__).resolve().parent
    (here / "out").mkdir(exist_ok=True)
    (here / "debug").mkdir(exist_ok=True)
    scrape_chain(conf)
