#!/opt/plo-equity/venv/bin/python3
import os
import time
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

os.environ["DISPLAY"] = ":1"
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")

print("Starting Firefox...")
driver = webdriver.Firefox(options=options)

try:
    print("Navigating to GoldRush...")
    driver.get("https://www.goldrush.co.za/live-poker")
    time.sleep(5)
    
    print(f"Page title: {driver.title}")
    print(f"Current URL: {driver.current_url}")
    
    body_text = driver.find_element(By.TAG_NAME, "body").text
    print(f"\nPage text (first 500 chars):\n{body_text[:500]}")
    
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"\nIframes found: {len(iframes)}")
    for i, iframe in enumerate(iframes[:3]):
        print(f"  {i+1}. {iframe.get_attribute('src')[:100] if iframe.get_attribute('src') else 'no src'}")
    
    # Check for login status
    if "login" in body_text.lower() or "sign in" in body_text.lower():
        print("\n⚠ Page requires login")
    else:
        print("\n✓ May be logged in or no login required")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    driver.quit()
    print("\nDone")
