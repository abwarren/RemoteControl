#!/usr/bin/env python3
"""W4P Bot v2 — 2-phase: navigate to table, wait for GO signal, then seat simultaneously.

Phase 1: Login -> Poker -> iframe -> find Belgrade -> READY
Phase 2: Wait for /tmp/GO -> join table -> MAX buy-in -> SEATED
Extension auto-injects w4p.js into the poker iframe for snapshot posting.
"""
import os, sys, time, subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

USERNAME = os.getenv("POKER_USERNAME", "")
PASSWORD = os.getenv("POKER_PASSWORD", "")
TABLE_NAME = os.getenv("TABLE_NAME", "Belgrade")
BUYIN_AMOUNT = os.getenv("BUYIN_AMOUNT", "MAX")
EXTENSION_PATH = os.getenv("EXTENSION_PATH", "/app/FINALEXT")

if not USERNAME or not PASSWORD:
    print("ERROR: POKER_USERNAME and POKER_PASSWORD required")
    sys.exit(1)

print(f"[W4P] Bot v2 starting: {USERNAME} | Table: {TABLE_NAME} | Buy-in: {BUYIN_AMOUNT}")
sys.stdout.flush()

# Kill the custom_startup.sh Chrome loop to avoid conflicts
subprocess.run(["pkill", "-f", "custom_startup.sh"], capture_output=True)
subprocess.run(["pkill", "-9", "-f", "google-chrome"], capture_output=True)
time.sleep(2)
# Clear Chrome locks
for f in os.listdir("/tmp"):
    if f.startswith(".com.google.Chrome"):
        subprocess.run(["rm", "-rf", f"/tmp/{f}"], capture_output=True)
subprocess.run(["rm", "-f", "/home/kasm-user/.config/google-chrome/SingletonLock"], capture_output=True)
subprocess.run(["rm", "-rf", "/tmp/chrome-bot-profile"], capture_output=True)

# Clean up signal files
for f in ["/tmp/READY", "/tmp/GO", "/tmp/SEATED", "/tmp/ERROR"]:
    try:
        os.remove(f)
    except:
        pass

# Chrome with extension (clean profile avoids conflicts)
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-background-timer-throttling")
options.add_argument("--disable-renderer-backgrounding")
options.add_argument(f"--load-extension={EXTENSION_PATH}")
options.add_argument(f"--disable-extensions-except={EXTENSION_PATH}")
options.add_argument("--user-data-dir=/tmp/chrome-bot-profile")

service = Service(executable_path="/usr/local/bin/chromedriver")

try:
    driver = webdriver.Chrome(service=service, options=options)
except Exception as e:
    print(f"[W4P] Chrome start failed: {e}, retrying...")
    sys.stdout.flush()
    time.sleep(3)
    subprocess.run(["pkill", "-9", "-f", "chrome"], capture_output=True)
    time.sleep(2)
    driver = webdriver.Chrome(service=service, options=options)

wait = WebDriverWait(driver, 30)

try:
    # === PHASE 1: Navigate to table ===
    print("[W4P] Phase 1: Login and navigate...")
    sys.stdout.flush()

    driver.get("https://www.pokerbet.co.za/en/")
    time.sleep(4)

    # Dismiss popups
    try:
        popup = driver.find_element(By.CSS_SELECTOR, "div.popup-middleware-bc button")
        popup.click()
        time.sleep(1)
    except:
        pass

    # Sign In
    print("[W4P]   Sign In...")
    sys.stdout.flush()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.s-small.sign-in"))).click()
    time.sleep(2)

    # Credentials
    print(f"[W4P]   Credentials for {USERNAME}...")
    sys.stdout.flush()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,
        "#login_form_id input[type=text], #login_form_id div:nth-child(3) label input"))).send_keys(USERNAME)
    driver.find_element(By.CSS_SELECTOR,
        "#login_form_id input[type=password], #login_form_id div:nth-child(4) label input").send_keys(PASSWORD)
    login_btn = driver.find_element(By.CSS_SELECTOR,
        "#login_form_id button[type=submit], #login_form_id .entrance-form-actions-holder-bc button")
    driver.execute_script("arguments[0].click();", login_btn)
    time.sleep(5)
    print("[W4P]   Logged in")
    sys.stdout.flush()

    # Navigate to Poker
    poker_link = wait.until(EC.element_to_be_clickable((By.XPATH,
        "//nav//a[contains(@href, 'poker') or .//span[contains(text(),'Poker')]]")))
    driver.execute_script("arguments[0].click();", poker_link)
    time.sleep(3)

    # Click PLAY
    print("[W4P]   PLAY...")
    sys.stdout.flush()
    play_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.a-color")))
    driver.execute_script("arguments[0].click();", play_btn)
    time.sleep(8)

    # Switch to poker iframe
    print("[W4P]   Poker iframe...")
    sys.stdout.flush()
    iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,
        'iframe[src*="LaunchGame"], iframe[src*="18751019"]')))
    driver.switch_to.frame(iframe)
    time.sleep(5)

    # Handle poker client login if needed
    try:
        login_modal = driver.find_elements(By.CSS_SELECTOR, "sg-login-modal")
        if login_modal:
            print("[W4P]   Poker client login...")
            sys.stdout.flush()
            un = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "sg-login-modal input[type=text]")))
            un.send_keys(USERNAME)
            pw = driver.find_element(By.CSS_SELECTOR, "sg-login-modal input[type=password]")
            pw.send_keys(PASSWORD)
            btn = driver.find_element(By.CSS_SELECTOR, "sg-login-modal button[type=submit], sg-login-modal button")
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(5)
    except:
        pass

    # Cash Games tab
    print("[W4P]   Cash Games...")
    sys.stdout.flush()
    time.sleep(2)
    try:
        tabs = driver.find_elements(By.CSS_SELECTOR,
            "sg-product-categories-nav a, sg-product-categories-nav button, [class*='category'] a")
        for tab in tabs:
            if "CASH" in tab.text.upper():
                driver.execute_script("arguments[0].click();", tab)
                break
    except:
        pass
    # Click Omaha 4 / PLO 4 sub-category
    print("[W4P]   Omaha 4...")
    sys.stdout.flush()
    time.sleep(2)
    try:
        subs = driver.find_elements(By.CSS_SELECTOR,
            "sg-sub-categories a, sg-sub-categories button, [class*=sub-cat] a, [class*=category] a, a, button")
        for s in subs:
            txt = s.text.upper().strip()
            if "OMAHA 4" in txt or "PLO 4" in txt or "PLO4" in txt or txt == "OMAHA":
                driver.execute_script("arguments[0].click();", s)
                print(f"[W4P]   Clicked: {s.text.strip()}")
                break
    except:
        pass
    time.sleep(3)
    time.sleep(3)

    # Click PLO/Omaha 4 filter
    print('[W4P]   Selecting PLO Omaha 4...')
    sys.stdout.flush()
    # Click PLO Omaha 4 via exact XPath
    plo_xpath = '/html/body/sg-app/div/sg-lobby/div/div/sg-poker-app/sg-table-category/div[1]/div[1]/div/div[1]/sg-category-filters-new/div[1]/div/ul[2]/li[2]/a'
    try:
        plo_btn = driver.find_element(By.XPATH, plo_xpath)
        driver.execute_script('arguments[0].click();', plo_btn)
        print('[W4P]   Clicked PLO Omaha 4 filter')
    except:
        print('[W4P]   PLO filter xpath not found, trying JS fallback')
        driver.execute_script("""
            var els = document.querySelectorAll('a, button, span, li');
            for (var i = 0; i < els.length; i++) {
                var t = els[i].textContent.trim().toUpperCase();
                if (t.indexOf('OMAHA') !== -1 || t.indexOf('PLO') !== -1) { els[i].click(); break; }
            }
        """)
    time.sleep(5)

    # Find Belgrade table (retry up to 3x)
    print(f"[W4P]   Finding {TABLE_NAME}...")
    sys.stdout.flush()
    table_rows = []
    for _attempt in range(3):
        time.sleep(5)
        table_rows = driver.find_elements(By.CSS_SELECTOR,
            "sg-tables-list ul li, .table-list li, [class*='tables-list'] li, sg-lobby-table-list li, .table-item")
        if len(table_rows) > 0:
            break
        driver.execute_script('window.scrollTo(0, document.body.scrollHeight)')
    found_row = None
    for row in table_rows:
        if TABLE_NAME.lower() in row.text.lower():
            found_row = row
            print(f"[W4P]   Found: {row.text.split(chr(10))[0]}")
            sys.stdout.flush()
            break

    if not found_row:
        driver.save_screenshot("/app/lobby_debug.png")
        raise Exception(f"Table '{TABLE_NAME}' not found in {len(table_rows)} rows")

    # === SIGNAL READY ===
    with open("/tmp/READY", "w") as f:
        f.write(f"{USERNAME}\n")
    print(f"[W4P] READY - waiting for GO signal...")
    sys.stdout.flush()

    # === PHASE 2: Wait for GO then join ===
    timeout = 180
    start = time.time()
    while not os.path.exists("/tmp/GO"):
        time.sleep(0.5)
        if time.time() - start > timeout:
            print("[W4P] TIMEOUT waiting for GO, joining anyway")
            sys.stdout.flush()
            break

    print("[W4P] GO! Joining table...")
    sys.stdout.flush()

    # Click table row
    driver.execute_script("arguments[0].click();", found_row)
    time.sleep(2)

    # Join table
    join_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,
        "sg-join-multiple-tables button, [class*='join'] button, .modal-button-container button")))
    driver.execute_script("arguments[0].click();", join_btn)
    time.sleep(2)

    # MAX buy-in
    if BUYIN_AMOUNT == "MAX":
        try:
            max_btn = wait.until(EC.element_to_be_clickable((By.XPATH,
                "//button[contains(text(),'Max') or contains(text(),'MAX')]")))
            driver.execute_script("arguments[0].click();", max_btn)
        except:
            print("[W4P]   No MAX button, using default")
            sys.stdout.flush()

    # Confirm buy-in
    confirm_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,
        "sg-buy-in-modal .modal-button-container button, sg-buy-in-modal button[type=submit]")))
    driver.execute_script("arguments[0].click();", confirm_btn)
    time.sleep(3)

    # === SEATED ===
    with open("/tmp/SEATED", "w") as f:
        f.write(f"{USERNAME} seated at {TABLE_NAME} MAX\n")
    print("")
    print("=" * 50)
    print(f"[W4P] SEATED: {USERNAME} at {TABLE_NAME} (MAX)")
    print(f"[W4P] Extension w4p.js active - snapshots flowing")
    print("=" * 50)
    sys.stdout.flush()

    # Keep alive - extension handles snapshots to Flask
    while True:
        time.sleep(60)
        try:
            driver.title
        except:
            print("[W4P] Session lost")
            sys.stdout.flush()
            break

except Exception as e:
    print(f"[W4P] ERROR: {e}")
    sys.stdout.flush()
    with open("/tmp/ERROR", "w") as f:
        f.write(str(e))
    try:
        driver.save_screenshot("/app/error.png")
    except:
        pass
    sys.exit(1)
finally:
    driver.quit()
