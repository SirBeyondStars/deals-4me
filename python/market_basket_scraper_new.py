# scrapers/market_basket_scraper.py
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))  # add /scripts to path

from base_scraper import ChainConfig, scrape_chain

conf = ChainConfig(
    chain_name="MarketBasket",
    store_num=22865,                       # your store number
    url="https://<weekly-ad-or-site-url>", # the page that triggers the JSON calls
    mode="json",
    json_item_path=["products"],           # adjust to match that chain's JSON
    json_fields={
        "name": "name",
        "desc": "description",
        "sale": "price",
        "deal_text": "deal_text"
    },
    out_csv="out/market_basket.csv"
)

if __name__ == "__main__":
    Path("out").mkdir(exist_ok=True)
    scrape_chain(conf)
