#!/usr/bin/env python3
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Installing Playwright...")
    os.system("pip install playwright -q && playwright install chromium -q")
    from playwright.sync_api import sync_playwright

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
    """Get previous state and timestamp"""
    if Path(STATE_FILE).exists():
        content = Path(STATE_FILE).read_text().strip()
        # Format: "state|timestamp" or just "state" for backward compatibility
        if "|" in content:
            state, prev_timestamp = content.split("|", 1)
            return state.strip(), prev_timestamp.strip()
        else:
            return content, None
    return "out_of_stock", None

def save_state(state):
    """Save state with current timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    Path(STATE_FILE).write_text(f"{state}|{timestamp}")

def check_stock():
    log_msg("Check started")
    log_msg(f"Opening URL: {URL}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            try:
                page.goto(URL, wait_until="networkidle", timeout=30000)
                log_msg("Page loaded successfully")

                # Get page content
                content = page.content()
                log_msg(f"Page content length: {len(content)}")

                # Check for stock indicators
                is_in_stock = False
                stock_details = []

                # Japanese indicators for in-stock
                if "カートに入れる" in content:
                    is_in_stock = True
                    stock_details.append("カートに入れるボタンが表示")
                    log_msg("Found: カートに入れる (Add to Cart button)")

                # English indicators for in-stock
                if "buy now" in content.lower():
                    is_in_stock = True
                    stock_details.append("'Buy Now'ボタンが表示")
                    log_msg("Found: buy now button")

                if "add to cart" in content.lower():
                    is_in_stock = True
                    if "Add to Cart" not in stock_details:
                        stock_details.append("'Add to Cart'ボタンが表示")
                    log_msg("Found: add to cart button")

                # Out of stock indicators
                if "在庫なし" in content or "品切れ" in content:
                    is_in_stock = False
                    stock_details.append("在庫なし/品切れ表記あり")
                    log_msg("Found: 在庫なし or 品切れ (out of stock)")

                if "out of stock" in content.lower() or "sold out" in content.lower():
                    is_in_stock = False
                    stock_details.append("Out of Stock/Sold Out表記あり")
                    log_msg("Found: out of stock or sold out")

                log_msg(f"Stock status: {'in_stock' if is_in_stock else 'out_of_stock'}")

                # Show page preview
                preview = content[:500].replace("\n", " ")
                log_msg(f"Page preview: {preview}")

                return is_in_stock, stock_details

            finally:
                browser.close()

    except Exception as e:
        log_msg(f"Error during stock check: {str(e)}")
        import traceback
        log_msg(traceback.format_exc())
        return False, []

def send_discord_notification(stock_details, previous_timestamp, current_timestamp):
    if not DISCORD_WEBHOOK:
        log_msg("Discord webhook not configured, skipping notification")
        return

    try:
        import requests

        # Build message with stock details and timeline
        message = "🎉 **Amazon Baby Welcome Box が在庫復活しました！**\n\n"

        # Previous check status
        message += "**前回のチェック:**\n"
        if previous_timestamp:
            message += f"• 時刻: {previous_timestamp}\n"
            message += "• 状態: 売切れ\n"
        else:
            message += "• 初回チェック\n"
        message += "\n"

        # Current check status
        message += "**今回のチェック:**\n"
        message += f"• 時刻: {current_timestamp}\n"
        message += "• 状態: 在庫あり\n"
        message += "\n"

        # Stock details
        if stock_details:
            message += "**在庫詳細:**\n"
            for detail in stock_details:
                message += f"• {detail}\n"
            message += "\n"

        message += f"**購入ページ:** {URL}"

        payload = {
            "content": message
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
    is_in_stock, stock_details = check_stock()
    current_state = "in_stock" if is_in_stock else "out_of_stock"
    previous_state, previous_timestamp = get_previous_state()
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_msg(f"Previous state: {previous_state} (at {previous_timestamp}), Current state: {current_state}")

    # Send notification if stock status changed from out to in
    if current_state == "in_stock" and previous_state == "out_of_stock":
        log_msg("Stock detected! Sending notification...")
        send_discord_notification(stock_details, previous_timestamp, current_timestamp)

    save_state(current_state)
    log_msg("Check completed successfully")

except Exception as e:
    log_msg(f"Fatal error: {str(e)}")
    import traceback
    log_msg(traceback.format_exc())
    sys.exit(1)
