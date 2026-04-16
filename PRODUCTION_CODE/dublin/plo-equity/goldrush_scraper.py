#!/usr/bin/env python3
"""
GoldRush PLO Table Scraper
Scrapes available PLO4 and PLO6 tables from GoldRush lobby.
Stores results separately from PokerBet data.
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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

SCRAPE_LOG = "/tmp/goldrush_scraper.log"
OUTPUT_JSON = "/opt/plo-equity/goldrush_tables.json"

# JavaScript to extract PLO tables from GoldRush lobby - using raw string to avoid escape warnings
GOLDRUSH_SCRAPER_JS = r"""
(function() {
  const tables = [];

  // Target all table/game entries
  const selectors = [
    '[class*="table"]',
    '[class*="game"]',
    '[class*="lobby"]',
    '[data-game]',
    '[data-table]',
    '.lobby-item',
    '.game-item',
    '.table-item',
    'tr[class*="table"]',
    'div[class*="game"]',
    'li[class*="item"]'
  ];

  const allElements = new Set();
  selectors.forEach(selector => {
    try {
      document.querySelectorAll(selector).forEach(el => allElements.add(el));
    } catch(e) {}
  });

  allElements.forEach(el => {
    const text = el.innerText || el.textContent || '';

    // Look for PLO4 or PLO6 indicators
    const isPLO4 = text.match(/PLO4|Omaha.*4|4.*Card.*Omaha|Pot Limit Omaha(?!.*6)/i);
    const isPLO6 = text.match(/PLO6|Omaha.*6|6.*Card.*Omaha/i);

    if (isPLO4 || isPLO6) {
      // Extract table name
      const nameMatch = text.match(/\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b/);
      const name = nameMatch ? nameMatch[1] : null;

      // Extract stakes (R X/Y or ZAR X/Y format)
      const stakesMatch = text.match(/(?:R|ZAR)\s*(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)/i);

      // Extract seats
      const seatsMatch = text.match(/(\d+)-max/i) || text.match(/(\d+)\s+seat/i);

      if (name && stakesMatch) {
        tables.push({
          name: name.trim(),
          game_type: isPLO6 ? 'PLO6' : 'PLO4',
          small_blind: parseFloat(stakesMatch[1]),
          big_blind: parseFloat(stakesMatch[2]),
          stakes_display: `R ${stakesMatch[1]}/${stakesMatch[2]}`,
          seats_total: seatsMatch ? parseInt(seatsMatch[1]) : 6,
          platform: 'GoldRush'
        });
      } else if (isPLO4 || isPLO6) {
        // If we found PLO but couldn't parse details, log the element
        console.log('Found PLO table but could not parse:', text.substring(0, 200));
      }
    }
  });

  // Deduplicate by table name
  const uniqueTables = [];
  const seen = new Set();
  tables.forEach(t => {
    if (!seen.has(t.name)) {
      seen.add(t.name);
      uniqueTables.push(t);
    }
  });

  return uniqueTables;
})();
"""


def _log(msg):
    """Write to scraper log file."""
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(SCRAPE_LOG, "a") as f:
            f.write(line)
    except Exception:
        pass
    logger.info(msg)


def navigate_to_goldrush_lobby(driver):
    """Navigate to GoldRush poker lobby."""
    _log("Navigating to goldrush.co.za/live-poker")
    driver.get("https://www.goldrush.co.za/live-poker")
    time.sleep(8)

    # Check for iframes
    _log("Looking for poker game iframes")
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    _log(f"Found {len(iframes)} iframes")

    if iframes:
        # Try to switch to the first relevant iframe
        for i, iframe in enumerate(iframes):
            src = iframe.get_attribute("src") or ""
            _log(f"Iframe {i}: {src[:100]}")
            if "poker" in src.lower() or "game" in src.lower() or "lobby" in src.lower():
                driver.switch_to.frame(iframe)
                _log(f"Switched to poker iframe: {src[:100]}")
                time.sleep(3)
                break

    # Scroll to load all tables
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)
    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(1)

    _log("Navigation complete")


def scrape_goldrush_tables(driver):
    """Execute JavaScript scraper and return table data."""
    _log("Executing GoldRush table scraper JavaScript")
    try:
        tables = driver.execute_script(GOLDRUSH_SCRAPER_JS)
        _log(f"Scraper returned {len(tables)} tables")
        return tables
    except Exception as e:
        _log(f"JavaScript execution failed: {e}")
        return []


def save_tables_to_json(tables):
    """Save scraped tables to JSON file."""
    data = {
        "platform": "GoldRush",
        "scraped_at": datetime.utcnow().isoformat(),
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
    """
    Main entry point for GoldRush table scraping.
    Returns: dict with status, tables list, and metadata.
    """
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
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        _log("Starting Firefox")
        driver = webdriver.Firefox(options=options)

        try:
            # Navigate to GoldRush lobby
            navigate_to_goldrush_lobby(driver)

            # Scrape tables
            tables = scrape_goldrush_tables(driver)

            # Save to JSON
            save_tables_to_json(tables)

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
    # Command-line usage
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
