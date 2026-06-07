#!/usr/bin/env python3
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
except ImportError:
    print("ERROR: Selenium not installed. Installing...")
    os.system("pip install selenium -q")
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

# Configuration
URL = "https://www.amazon.co.jp/baby-reg/welcomebox?_encoding=UTF8&ref_=cct_cg_PXbenefit_2b1&pf_rd_p=9cc85c64-a328-41c8-b7be-e1dcaa476709&pf_rd_r=VHCS878C8VFC2T3FVY43"
STATE_FILE = "amazon_stock_state.txt"
LOG_FILE = "amazon_stock_check.log"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_msg(message):
    print(f"{timestamp} - {message}")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} - {message}\n")

def get_previous_state():
    if Path(STATE_FILE).exists():
        return Path(STATE_FILE).read_text().strip()
    return "out_of_stock"

def save_state(state):
    Path(STATE_FILE).write_text(state)

def check_stock():
    log_msg("Check started")

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        log_msg(f"Opening URL: {URL}")
        driver.get(URL)

        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "body"))
        )

        # Get page source
        page_source = driver.page_source
        log_msg(f"Page loaded, source length: {len(page_source)}")

        # Check for stock indicators
        is_in_stock = False

        # Japanese indicators
        if "カートに入れる" in page_source and "在庫なし" not in page_source and "品切れ" not in page_source:
            is_in_stock = True
            log_msg("Stock indicator found: カートに入れる (Add to Cart button)")

        # English indicators
        if "buy now" in page_source.lower() and "out of stock" not in page_source.lower():
            is_in_stock = True
            log_msg("Stock indicator found: buy now button")

        # Out of stock indicators
        if "在庫なし" in page_source or "品切れ" in page_source or "out of stock" in page_source.lower():
            is_in_stock = False
            log_msg("Out of stock indicator found")

        log_msg(f"Stock status determined: {'in_stock' if is_in_stock else 'out_of_stock'}")
        log_msg(f"Page preview (first 500 chars): {page_source[:500]}")

        return is_in_stock

    except Exception as e:
        log_msg(f"Error during stock check: {str(e)}")
        return False
    finally:
        if driver:
            driver.quit()

def send_discord_notification():
    if not DISCORD_WEBHOOK:
        log_msg("Discord webhook not configured, skipping notification")
        return

    try:
        import requests
        payload = {
            "content": "🎉 **Amazon Baby Welcome Box is IN STOCK!**\n" + URL
        }
        response = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        if response.status_code in [200, 204]:
            log_msg("Discord notification sent successfully")
        else:
            log_msg(f"Discord notification failed: {response.status_code}")
    except Exception as e:
        log_msg(f"Discord error: {str(e)}")

# Main logic
try:
    is_in_stock = check_stock()
    current_state = "in_stock" if is_in_stock else "out_of_stock"
    previous_state = get_previous_state()

    log_msg(f"Previous state: {previous_state}, Current state: {current_state}")

    # Send notification if stock status changed from out to in
    if current_state == "in_stock" and previous_state == "out_of_stock":
        log_msg("Stock detected! Sending notification...")
        send_discord_notification()

    save_state(current_state)
    log_msg("Check completed successfully")

except Exception as e:
    log_msg(f"Fatal error: {str(e)}")
    sys.exit(1)
