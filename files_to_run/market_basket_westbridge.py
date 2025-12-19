import json
import csv
from playwright.sync_api import sync_playwright

def scrape_market_basket():
    output_file = "market_basket_westbridge.csv"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🛒 Loading Market Basket flyer for West Bridgewater...")
        page.goto("https://shop.mywebgrocer.com/market-basket-ma/flyer", timeout=60000)

        # Wait for page to load
        page.wait_for_timeout(8000)

        # Capture all network requests that contain "flyer" JSON
        responses = []
        def handle_response(response):
            if "flyer" in response.url and "json" in response.url:
                responses.append(response)
        page.on("response", handle_response)

        # Scroll to trigger network activity
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(6000)

        # Try to extract items
        found_items = []
        for response in responses:
            try:
                data = response.json()
                if "products" in data.get("json", {}):
                    found_items.extend(data["json"]["products"])
            except Exception:
                pass

        print(f"Found {len(found_items)} items")

        # Save data
        if found_items:
            with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["name", "description", "deal_text", "sale_start", "sale_end"])
                writer.writeheader()
                for item in found_items:
                    writer.writerow({
                        "name": item.get("name", ""),
                        "description": item.get("description", ""),
                        "deal_text": item.get("deal_text", ""),
                        "sale_start": data.get("json", {}).get("dates", {}).get("start_date", ""),
                        "sale_end": data.get("json", {}).get("dates", {}).get("end_date", "")
                    })
            print(f"✅ Saved flyer data to {output_file}")
        else:
            print("⚠️ No items found — the site may have changed or needs a different link.")

        browser.close()

if __name__ == "__main__":
    scrape_market_basket()
