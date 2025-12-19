from playwright.sync_api import sync_playwright
from pathlib import Path

STATE = Path("stopandshop_state.json")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # opens a visible browser
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto("https://stopandshop.com/savings/weekly-ad/grid-view", wait_until="domcontentloaded")

    print("\n>>> Select your store in the opened browser if it's not already set.")
    print("Once you see your flyer grid (with items), return here and press ENTER.\n")
    input("Press ENTER when your store is showing...")

    ctx.storage_state(path=str(STATE))
    print(f"✅ Saved store/session to: {STATE.resolve()}")
    browser.close()
