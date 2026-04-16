#!/opt/plo-equity/venv/bin/python3
"""
GoldRush PLO Table Scraper with Login
Logs into GoldRush, navigates to poker lobby, and scrapes PLO tables.
Keeps data separate from PokerBet.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

SCRAPE_LOG = "/tmp/goldrush_scraper.log"
OUTPUT_JSON = "/opt/plo-equity/goldrush_tables.json"

GOLDRUSH_EMAIL = "warrenabrahams@gmail.com"
GOLDRUSH_PASSWORD = "Gemm@12345"

# JavaScript to extract PLO tables
GOLDRUSH_SCRAPER_JS = r"""
(function() {
  const tables = [];

  const selectors = [
    '[class*="table"]',
    '[class*="game"]',
    '[class*="lobby"]',
    '[data-game]',
    '[data-table]',
    '.table-row',
    '.game-row',
    'tr',
    'div[class*="table"]'
  ];

  const allElements = new Set();
  selectors.forEach(selector => {
    try {
      document.querySelectorAll(selector).forEach(el => allElements.add(el));
    } catch(e) {}
  });

  allElements.forEach(el => {
    const text = el.innerText || el.textContent || '';

    // Look for PLO indicators
    const isPLO4 = text.match(/PLO[\s-]*4|Omaha[\s-]*4|4[\s-]*Card[\s-]*Omaha|Pot[\s-]*Limit[\s-]*Omaha(?!.*6)/i);
    const isPLO6 = text.match(/PLO[\s-]*6|Omaha[\s-]*6|6[\s-]*Card[\s-]*Omaha/i);

    if (isPLO4 || isPLO6) {
      // Extract table name
      const nameMatch = text.match(/\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b/);
      
      // Extract stakes (R X/Y or ZAR X/Y format)
      const stakesMatch = text.match(/(?:R|ZAR)\s*(\d+(?:\.\d+)?)\s*[\/\-]\s*(\d+(?:\.\d+)?)/i);
      
      // Extract seats
      const seatsMatch = text.match(/(\d+)[\s-]*max/i) || text.match(/(\d+)\s+seat/i);

      if (stakesMatch) {
        const name = nameMatch ? nameMatch[1].trim() : 'Table ' + Math.random().toString(36).substr(2, 5);
        
        tables.push({
          name: name,
          game_type: isPLO6 ? 'PLO6' : 'PLO4',
          small_blind: parseFloat(stakesMatch[1]),
          big_blind: parseFloat(stakesMatch[2]),
          stakes_display: `R ${stakesMatch[1]}/${stakesMatch[2]}`,
          seats_total: seatsMatch ? parseInt(seatsMatch[1]) : 6,
          platform: 'GoldRush',
          raw_text: text.substring(0, 100)
        });
      }
    }
  });

  // Deduplicate
  const uniqueTables = [];
  const seen = new Set();
  tables.forEach(t => {
    const key = `${t.game_type}_${t.stakes_display}`;
    if (!seen.has(key)) {
      seen.add(key);
      delete t.raw_text;
      uniqueTables.push(t);
    }
  });

  return uniqueTables;
})();
"""


def _log(msg):
    """Write to log file."""
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(SCRAPE_LOG, "a") as f:
            f.write(line)
    except Exception:
        pass
    logger.info(msg)


def login_to_goldrush(driver):
    """Login to GoldRush casino."""
    _log("Navigating to GoldRush homepage")
    driver.get("https://www.goldrush.co.za")
    time.sleep(5)

    # Look for login/sign in button
    _log("Looking for login button")
    login_clicked = False
    
    for btn in driver.find_elements(By.TAG_NAME, "button") + driver.find_elements(By.TAG_NAME, "a"):
        text = btn.text.strip().lower()
        if any(word in text for word in ['login', 'sign in', 'log in']):
            _log(f"Found login button: {btn.text}")
            driver.execute_script("arguments[0].click()", btn)
            login_clicked = True
            time.sleep(3)
            break

    if not login_clicked:
        _log("No login button found, trying direct navigation")
        driver.get("https://www.goldrush.co.za/login")
        time.sleep(3)

    # Fill login form
    _log(f"Filling login form for {GOLDRUSH_EMAIL}")
    try:
        # Try common email field selectors
        email_field = None
        for selector in ['input[type="email"]', 'input[name*="email"]', 'input[name*="username"]', 'input[id*="email"]']:
            try:
                email_field = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except:
                pass
        
        if email_field:
            email_field.clear()
            email_field.send_keys(GOLDRUSH_EMAIL)
            _log("Email entered")
        else:
            raise Exception("Could not find email field")

        # Password field
        password_field = None
        for selector in ['input[type="password"]', 'input[name*="password"]', 'input[id*="password"]']:
            try:
                password_field = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except:
                pass
        
        if password_field:
            password_field.clear()
            password_field.send_keys(GOLDRUSH_PASSWORD)
            password_field.send_keys(Keys.RETURN)
            _log("Password entered and form submitted")
        else:
            raise Exception("Could not find password field")

        time.sleep(8)

        # Verify login
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if "balance" in body_text or "logout" in body_text or "account" in body_text:
            _log("Login successful")
            return True
        else:
            _log("Login verification uncertain, proceeding anyway")
            return True

    except Exception as e:
        _log(f"Login error: {e}")
        return False


def navigate_to_poker_lobby(driver):
    """Navigate to poker lobby."""
    _log("Navigating to live poker lobby")
    driver.get("https://www.goldrush.co.za/live-poker")
    time.sleep(8)

    # Check for iframes
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    _log(f"Found {len(iframes)} iframes")

    for i, iframe in enumerate(iframes):
        src = iframe.get_attribute("src") or ""
        if src and "google" not in src.lower():
            _log(f"Switching to iframe: {src[:100]}")
            driver.switch_to.frame(iframe)
            time.sleep(5)
            break

    # Look for poker/lobby links
    for elem in driver.find_elements(By.XPATH, "//*[contains(text(),'Poker') or contains(text(),'POKER') or contains(text(),'Lobby') or contains(text(),'LOBBY')]"):
        try:
            if elem.is_displayed() and elem.is_enabled():
                _log(f"Clicking: {elem.text[:50]}")
                driver.execute_script("arguments[0].click()", elem)
                time.sleep(3)
                break
        except:
            pass

    # Scroll to load content
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)
    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(1)

    _log("Navigation complete")


def scrape_tables(driver):
    """Execute JavaScript scraper."""
    _log("Executing table scraper JavaScript")
    try:
        tables = driver.execute_script(GOLDRUSH_SCRAPER_JS)
        _log(f"Scraper returned {len(tables)} tables")
        return tables
    except Exception as e:
        _log(f"JavaScript execution failed: {e}")
        return []


def save_to_json(tables):
    """Save scraped tables to JSON."""
    data = {
        "platform": "GoldRush",
        "scraped_at": datetime.now().isoformat(),
        "count": len(tables),
        "tables": tables
    }

    try:
        with open(OUTPUT_JSON, "w") as f:
            json.dump(data, f, indent=2)
        _log(f"Saved {len(tables)} tables to {OUTPUT_JSON}")
        return True
    except Exception as e:
        _log(f"Failed to save JSON: {e}")
        return False


def scrape_goldrush(headless=True):
    """Main scraper entry point."""
    start_time = time.time()
    _log("=== GoldRush Table Scraper Started ===")

    try:
        # Setup Firefox
        os.environ["DISPLAY"] = ":1"
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        _log("Starting Firefox")
        driver = webdriver.Firefox(options=options)

        try:
            # Login
            if not login_to_goldrush(driver):
                _log("Login failed, attempting to continue anyway")

            # Navigate to lobby
            navigate_to_poker_lobby(driver)

            # Scrape
            tables = scrape_tables(driver)

            # Save
            save_to_json(tables)

            duration = time.time() - start_time
            _log(f"=== Scraping Complete ({duration:.1f}s) ===")

            return {
                "ok": True,
                "platform": "GoldRush",
                "tables": tables,
                "count": len(tables),
                "duration": duration,
                "output_file": OUTPUT_JSON
            }

        finally:
            driver.quit()
            _log("Firefox closed")

    except Exception as e:
        import traceback
        error_msg = f"Scraper failed: {e}\n{traceback.format_exc()}"
        _log(error_msg)
        return {
            "ok": False,
            "platform": "GoldRush",
            "error": str(e),
            "tables": [],
            "duration": time.time() - start_time
        }


if __name__ == "__main__":
    headless = "--headless" in sys.argv
    result = scrape_goldrush(headless=headless)

    print(json.dumps(result, indent=2))

    if result["ok"]:
        print(f"\n✓ Found {result['count']} GoldRush PLO tables")
        print(f"✓ Saved to {result['output_file']}")
        sys.exit(0)
    else:
        print(f"\n✗ Scraping failed: {result['error']}")
        sys.exit(1)
