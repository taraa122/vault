import json
import re
import sys
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

TARGET_URL = "https://us-east-1.quicksight.aws.amazon.com/sn/account/vault-network-inteview/dashboards/3b1cdcb4-3d00-4612-9ff3-4940982b2e99"
EMAIL = "candidate@vaultsportshq.com"
PASS = "Vault!nterview1"

def fix_date(date_str):
    date_str = date_str.strip().replace(".", ",")
    formats = ["%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%m/%d/%Y", "%Y-%m-%d"]
    for f in formats:
        try:
            return datetime.strptime(date_str, f).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str

def kill_annoying_popups(page):
    page.wait_for_timeout(2000)
    targets = [
        'button:has-text("×")', 'button:has-text("Done")',
        'button:has-text("Close")', 'button:has-text("Got it")',
        'button:has-text("Dismiss")', 'button:has-text("Skip")',
        'button[aria-label="Close"]', 'button[aria-label="close"]'
    ]
    for _ in range(3):
        hit_something = False
        for selector in targets:
            try:
                elements = page.locator(selector)
                for i in range(elements.count()):
                    if elements.nth(i).is_visible():
                        print(f"Smashing popup: {selector}")
                        elements.nth(i).evaluate("node => node.click()")
                        page.wait_for_timeout(1000)
                        hit_something = True
                        break
            except Exception:
                pass
            if hit_something:
                break
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        page.keyboard.press("Escape")
    except Exception:
        pass

def login_to_quicksight(page):
    print("Navigating to dashboard URL ...")
    page.goto(TARGET_URL, timeout=90000, wait_until="networkidle")
    
    print("Entering username ...")
    page.locator('input:visible').first.wait_for(state="visible", timeout=60000)
    page.locator('input:visible').first.fill(EMAIL)
    
    print("Clicking Next ...")
    page.locator('button:has-text("Next")').first.click()
    page.wait_for_load_state("networkidle", timeout=90000)
    
    print("Entering password ...")
    page.locator('input[type="password"]').first.wait_for(state="visible", timeout=60000)
    page.locator('input[type="password"]').first.fill(PASS)
    
    print("Clicking Sign in ...")
    page.locator('button:has-text("Sign in"), button:has-text("Submit"), button[type="submit"]').first.click()
    
    print("Credentials submitted -- waiting for dashboard to load ...")
    page.wait_for_load_state("networkidle", timeout=90000)
    kill_annoying_popups(page)

def scrape_the_dom(page):
    print("Extracting from DOM text via JS injection scrolling...")
    print("Running secondary popup check before scrolling...")
    kill_annoying_popups(page)
    
    seen_rows = set()
    scraped_data = []
    page.wait_for_timeout(2000)
    retries_left = 8

    for scroll_attempt in range(100):
        raw_text = page.locator("body").inner_text()
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        start_idx = -1
        for idx, val in enumerate(lines):
            if re.match(r'^AFF\d+$', val):
                start_idx = idx
                break

        new_finds = 0
        if start_idx != -1:
            table_chunks = lines[start_idx:]
            for i in range(0, len(table_chunks) - 4, 5):
                chunk = table_chunks[i:i+5]
                if not re.match(r'^AFF\d+$', chunk[0]):
                    break 
                code, raw_date, state, ftds, regs = chunk
                try:
                    clean_ftds = int(ftds.replace(",", ""))
                    clean_regs = int(regs.replace(",", ""))
                    clean_date = fix_date(raw_date)
                    row_key = f"{clean_date}_{code}_{state}_{clean_ftds}_{clean_regs}"
                    if row_key not in seen_rows:
                        seen_rows.add(row_key)
                        scraped_data.append({
                            "date": clean_date,
                            "code": code,
                            "registrations": clean_regs,
                            "ftds": clean_ftds,
                            "state": state
                        })
                        new_finds += 1
                except Exception:
                    pass 

        if new_finds == 0:
            retries_left -= 1
            print(f"No new rows found. Scroll attempt {scroll_attempt} (Retries left: {retries_left})")
        else:
            retries_left = 8
            if scroll_attempt % 2 == 0:
                print(f"Scroll {scroll_attempt}: extracted {len(scraped_data)} unique rows so far...")

        if retries_left <= 0:
            print("Reached the end of the data.")
            break

        page.evaluate("""
            () => {
                document.querySelectorAll('*').forEach(el => {
                    if (el.scrollHeight > el.clientHeight) {
                        el.scrollTop += 800;
                    }
                });
            }
        """)
        page.wait_for_timeout(2500)
    return scraped_data

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--no-sandbox", "--disable-gpu"])
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            login_to_quicksight(page)
            page.wait_for_timeout(8000) 
            
            final_data = scrape_the_dom(page)
            
            if not final_data:
                print("Extraction failed. Saving debug screenshot.")
                page.screenshot(path="failed_extraction.png", full_page=True)
                sys.exit(1)
            
            final_data.sort(key=lambda x: (x["date"], x["code"], x["state"]))
            out_path = Path(__file__).parent / "output.json"
            with open(out_path, "w") as f:
                json.dump(final_data, f, indent=2)
            print(f"Success! Wrote {len(final_data)} records to output.json")
            
        except PWTimeout:
            print("The script timed out.")
            page.screenshot(path="timeout_error.png", full_page=True)
        except Exception as e:
            print(f"Error occurred: {e}")
            page.screenshot(path="crash_error.png", full_page=True)
        finally:
            browser.close()

if __name__ == "__main__":
    main()
