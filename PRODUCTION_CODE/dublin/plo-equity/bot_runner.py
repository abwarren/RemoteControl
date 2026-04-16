#!/usr/bin/env python3
"""
Bot Runner - Runs INSIDE a player container via docker exec.
Drives Chrome/Selenium to: login → poker → find table → seat → buy-in → verify → remote control.
Writes structured status to /tmp/bot_status.json for host-side monitoring.

Usage:
  python3 /tmp/bot_runner.py --username kele1 --password PokerPass123 \
      --table "PLO 1/2" --buyin MIN --bot-id bot_dep_001_0 \
      [--auto-buyin] [--first-action CHECK_OR_CALL_ONCE]
"""

import argparse
import json
import os
import sys
import time
import random
import traceback

os.environ["DISPLAY"] = ":1"

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

STATUS_FILE = "/tmp/bot_status.json"
LOG_FILE = "/tmp/bot_deploy.log"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def write_status(status, error=None, metadata=None):
    data = {
        "status": status,
        "last_update": time.time(),
    }
    if error:
        data["error"] = error
    if metadata:
        data["metadata"] = metadata
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        log(f"WARNING: could not write status file: {e}")


def human_pause(lo=1.0, hi=3.0):
    time.sleep(random.uniform(lo, hi))


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------

def start_browser():
    opts = Options()
    opts.add_argument("--width=1920")
    opts.add_argument("--height=1080")
    service = FirefoxService(executable_path="/usr/local/bin/geckodriver")
    driver = webdriver.Firefox(options=opts, service=service)
    driver.implicitly_wait(5)
    return driver


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def logout_if_needed(driver):
    """If already logged in, log out first."""
    try:
        # Look for profile/account menu or logout link
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        if "logout" in body or "log out" in body or "sign out" in body:
            log("Detected existing session — logging out first")
            links = driver.find_elements(By.TAG_NAME, "a") + driver.find_elements(By.TAG_NAME, "button")
            for el in links:
                txt = el.text.lower()
                if "logout" in txt or "log out" in txt or "sign out" in txt:
                    el.click()
                    human_pause(2.0, 4.0)
                    return True
    except Exception:
        pass
    return False


def dismiss_popups(driver):
    """Dismiss cookie consent, promo popups, or any overlay blocking the page."""
    try:
        # Nuclear option: remove ALL popup/overlay elements via JS
        removed = driver.execute_script("""
            var removed = 0;
            // PokerBet-specific popup classes
            document.querySelectorAll(
                '.popup-middleware-bc, .popup-holder-bc, ' +
                '[class*="popup-middleware"], [class*="popup-holder"], ' +
                '[class*="overlay-bc"], [class*="modal-bc"]'
            ).forEach(function(el) {
                el.remove();
                removed++;
            });
            // Generic overlay/backdrop with fixed position
            document.querySelectorAll('[class*="overlay"], [class*="backdrop"], [class*="modal-bg"]').forEach(function(el) {
                var pos = el.style.position || getComputedStyle(el).position;
                if (pos === 'fixed' || pos === 'absolute') {
                    var z = parseInt(getComputedStyle(el).zIndex) || 0;
                    if (z > 100) { el.remove(); removed++; }
                }
            });
            return removed;
        """)
        if removed:
            log(f"Removed {removed} popup overlay(s) via JS")
            human_pause(0.5, 1.0)

        # Also try clicking any visible close/dismiss buttons as backup
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            try:
                txt = btn.text.strip().lower()
                if txt in ("ok", "accept", "got it", "i agree", "close", "×", "x"):
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        log(f"Dismissed popup button: '{btn.text.strip()}'")
                        human_pause(0.5, 1.0)
            except Exception:
                continue
    except Exception as e:
        log(f"Popup dismissal error (non-fatal): {e}")


def login(driver, username, password, max_retries=2):
    """Login to PokerBet. If already logged in, logout first then login."""
    for attempt in range(max_retries):
        log(f"Login attempt {attempt + 1}/{max_retries} for {username}")

        # Check if already logged in (look for account indicators, not just "poker")
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        if "balance" in body or "my account" in body or "deposit" in body:
            # Double-check: "sign in" should NOT be visible if truly logged in
            if "sign in" not in body:
                log("Already logged in (balance/account visible, no sign-in button)")
                return True

        # If logged in elsewhere, logout first (user instruction)
        logout_if_needed(driver)
        human_pause(0.5, 1.0)

        # Click SIGN IN using JS click (bypasses any overlay)
        # IMPORTANT: do NOT dismiss popups here — the login form opens AS a popup
        sign_in_clicked = False
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            try:
                if btn.text.strip().upper() == "SIGN IN":
                    driver.execute_script("arguments[0].click();", btn)
                    sign_in_clicked = True
                    log("Clicked SIGN IN (JS)")
                    break
            except StaleElementReferenceException:
                continue

        if not sign_in_clicked:
            log("SIGN IN button not found")

        human_pause(2.0, 3.0)

        # Wait for username field (the login form is a popup/modal)
        try:
            username_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'input[name="username"]')
                )
            )
        except TimeoutException:
            log("Username field not found after clicking SIGN IN")
            if attempt < max_retries - 1:
                driver.get("https://www.pokerbet.co.za")
                human_pause(2.0, 4.0)
                continue
            raise Exception("Username field not found after retries")

        username_input.clear()
        for ch in username:
            username_input.send_keys(ch)
            time.sleep(random.uniform(0.03, 0.08))
        human_pause(0.5, 1.0)

        # Password field
        password_input = driver.find_element(
            By.CSS_SELECTOR, 'input[name="password"], input[type="password"]'
        )
        password_input.clear()
        for ch in password:
            password_input.send_keys(ch)
            time.sleep(random.uniform(0.03, 0.08))
        human_pause(0.5, 1.0)

        # Submit — try multiple approaches, any exception means page may have changed (OK)
        try:
            # First: press Enter on password field (most reliable)
            from selenium.webdriver.common.keys import Keys
            password_input.send_keys(Keys.RETURN)
            log("Submitted via Enter key on password field")
        except Exception:
            # Password field went stale — page may have auto-submitted
            log("Password field stale after typing — form may have auto-submitted")
            try:
                # Fallback: click button[type='submit']
                for btn in driver.find_elements(By.CSS_SELECTOR, "button[type='submit']"):
                    safe_click(driver, btn)
                    log("Clicked submit button")
                    break
            except Exception:
                log("Submit button also stale — page likely already changed")

        human_pause(3.0, 5.0)

        # Verify login success
        human_pause(1.0, 2.0)
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        if "incorrect" in body or "invalid" in body or "wrong" in body:
            log(f"Login rejected for {username} (bad credentials)")
            if attempt < max_retries - 1:
                driver.get("https://www.pokerbet.co.za")
                human_pause(2.0, 4.0)
                continue
            raise Exception(f"Login failed for {username} after {max_retries} attempts")

        # After submit, the login modal should close. Refresh body text.
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        # Positive: balance visible OR sign-in button gone
        if "balance" in body or "deposit" in body or "my account" in body:
            log(f"Login successful for {username} (account indicators visible)")
            return True
        # Sign-in still visible means login didn't work
        if "sign in" in body:
            log(f"Login may have failed for {username} (sign-in still visible)")
            if attempt < max_retries - 1:
                driver.get("https://www.pokerbet.co.za")
                human_pause(2.0, 4.0)
                continue
        else:
            log(f"Login appears successful for {username}")
            return True

    raise Exception(f"Login failed for {username} after {max_retries} attempts")


# ---------------------------------------------------------------------------
# Poker client navigation
# ---------------------------------------------------------------------------

def safe_click(driver, element):
    """Click an element, falling back to JS click if intercepted."""
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)


def open_poker_client(driver):
    """
    Full PokerBet navigation:
      1. Click POKER link
      2. Click PLAY button
      3. Switch into the poker iframe (18751019/skillgames)
      4. Click CASH GAMES
    """
    dismiss_popups(driver)
    human_pause(0.5, 1.0)

    # Step 1: Click POKER link
    log("Nav: clicking POKER link")
    clicked = False
    for xpath in [
        "//a[contains(text(),'Poker')]",
        "//a[contains(text(),'POKER')]",
        "//span[contains(text(),'Poker')]",
        "//*[contains(@href,'poker')]",
    ]:
        try:
            el = driver.find_element(By.XPATH, xpath)
            safe_click(driver, el)
            log(f"Nav: clicked POKER -> {el.text[:30]}")
            clicked = True
            break
        except Exception:
            continue
    if not clicked:
        # Fallback: search all elements
        for elem in driver.find_elements(By.TAG_NAME, "a") + driver.find_elements(By.TAG_NAME, "button"):
            try:
                if "poker" in elem.text.lower():
                    safe_click(driver, elem)
                    log(f"Nav: clicked poker fallback -> {elem.text[:30]}")
                    clicked = True
                    break
            except Exception:
                continue
    if not clicked:
        raise Exception("POKER link not found")
    human_pause(3.0, 5.0)
    dismiss_popups(driver)

    # Step 2: Click PLAY button (exact match — avoid "PLAYER EXCLUSION POLICY" etc.)
    log("Nav: clicking PLAY button")
    play_clicked = False
    for elem in driver.find_elements(By.TAG_NAME, "a") + driver.find_elements(By.TAG_NAME, "button"):
        try:
            txt = elem.text.strip()
            # Exact match for short PLAY-like text only
            if txt.upper() in ("PLAY", "PLAY NOW", "PLAY POKER"):
                safe_click(driver, elem)
                log(f"Nav: clicked PLAY -> '{txt}'")
                play_clicked = True
                break
        except Exception:
            continue
    if not play_clicked:
        log("Nav: PLAY button not found, trying direct URL")
    human_pause(4.0, 6.0)
    dismiss_popups(driver)

    # Step 3: Switch to poker iframe (must be 18751019 or skillgames — NOT ladesk/recaptcha)
    # Retry loop: the iframe may take time to load after PLAY
    log("Nav: waiting for poker iframe to load...")
    switched = False
    for attempt in range(10):  # Up to 30 seconds
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            try:
                src = iframe.get_attribute("src") or ""
                fid = iframe.get_attribute("id") or ""
                if "18751019" in src or "skillgames" in src:
                    driver.switch_to.frame(iframe)
                    log(f"Nav: switched to poker iframe (attempt {attempt+1}, id={fid})")
                    switched = True
                    break
            except StaleElementReferenceException:
                continue
        if switched:
            break
        if attempt == 0:
            log(f"Nav: {len(iframes)} iframes found, none match yet. Waiting...")
            for iframe in iframes:
                try:
                    src = iframe.get_attribute("src") or ""
                    fid = iframe.get_attribute("id") or ""
                    log(f"Nav:   iframe id={fid} src={src[:100]}")
                except Exception:
                    pass
        time.sleep(3)
    if not switched:
        log("Nav: WARNING — no poker iframe found after 30s, continuing in main frame")
    human_pause(2.0, 3.0)

    # Step 4: Click CASH GAMES tab
    # NOTE: DOM text is "Cash Games" but CSS text-transform shows "CASH GAMES".
    # XPath text() is case-sensitive so it fails. Use Selenium .text which reflects CSS.
    log("Nav: clicking CASH GAMES")
    cash_clicked = False
    for el in driver.find_elements(By.TAG_NAME, "a"):
        try:
            if el.text.strip().upper() == "CASH GAMES":
                safe_click(driver, el)
                log(f"Nav: clicked CASH GAMES tab (a element)")
                cash_clicked = True
                break
        except StaleElementReferenceException:
            continue
    if not cash_clicked:
        # Fallback: try all clickable elements
        for el in driver.find_elements(By.TAG_NAME, "li") + driver.find_elements(By.TAG_NAME, "span"):
            try:
                if "CASH" in el.text.strip().upper():
                    safe_click(driver, el)
                    log(f"Nav: clicked CASH GAMES fallback -> {el.text[:30]}")
                    cash_clicked = True
                    break
            except StaleElementReferenceException:
                continue
    if not cash_clicked:
        log("Nav: WARNING — CASH GAMES tab not found")
    human_pause(2.0, 3.0)
    dismiss_popups(driver)
    log("Nav: poker lobby ready")


def find_and_open_table(driver, target_name, max_wait=45):
    """Find table by name in the poker lobby, double-click it, and click JOIN.

    Flow: Omaha 4 filter → find table name → double-click → JOIN modal → click JOIN.
    NOTE: DOM uses CSS text-transform, so use Selenium .text (not XPath text()).
    """
    from selenium.webdriver.common.action_chains import ActionChains
    log(f"Scanning for table: '{target_name}'")

    # Omaha 4 filter — use Selenium .text (CSS text-transform safe)
    for tag in ["a", "span", "div"]:
        for el in driver.find_elements(By.TAG_NAME, tag):
            try:
                txt = el.text.strip()
                if txt.upper() == "OMAHA 4" or txt == "Omaha 4":
                    safe_click(driver, el)
                    log(f"Clicked filter: '{txt}'")
                    human_pause(2.0, 3.0)
                    break
            except StaleElementReferenceException:
                continue
        else:
            continue
        break

    # Log lobby state
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        log(f"Lobby text (500 chars): {body_text[:500]}")
    except Exception:
        pass

    deadline = time.time() + max_wait
    while time.time() < deadline:
        # Find the table name element using Selenium .text (handles CSS text-transform)
        table_el = None
        for tag in ["p", "span", "div", "td", "a"]:
            for el in driver.find_elements(By.TAG_NAME, tag):
                try:
                    txt = el.text.strip()
                    if txt.upper() == target_name.upper():
                        table_el = el
                        log(f"Found table: <{tag}> text='{txt}'")
                        break
                except StaleElementReferenceException:
                    continue
            if table_el:
                break

        if table_el:
            # Double-click the table name to open the Join modal
            try:
                ActionChains(driver).double_click(table_el).perform()
                log("Double-clicked table element")
            except Exception as e:
                log(f"Double-click failed ({e}), trying JS click")
                safe_click(driver, table_el)

            human_pause(3.0, 5.0)

            # Look for JOIN button in the modal (NOT the detail panel JOIN)
            # The modal JOIN has class 'button-view-m-p', the panel one is 'button-p-view'
            join_clicked = False

            # First try: find JOIN inside the SG-MODAL element
            modals = driver.find_elements(By.TAG_NAME, "sg-modal")
            for modal in modals:
                for btn in modal.find_elements(By.TAG_NAME, "button"):
                    try:
                        if btn.text.strip().upper() == "JOIN" and btn.is_displayed():
                            safe_click(driver, btn)
                            log("Clicked JOIN inside sg-modal")
                            join_clicked = True
                            break
                    except StaleElementReferenceException:
                        continue
                if join_clicked:
                    break

            if not join_clicked:
                # Fallback: find button with modal-specific class
                for btn in driver.find_elements(By.TAG_NAME, "button"):
                    try:
                        cls = btn.get_attribute("class") or ""
                        if btn.text.strip().upper() == "JOIN" and "button-view-m-p" in cls:
                            safe_click(driver, btn)
                            log("Clicked JOIN (button-view-m-p class)")
                            join_clicked = True
                            break
                    except StaleElementReferenceException:
                        continue

            if not join_clicked:
                # Last resort: click any displayed JOIN button
                for btn in driver.find_elements(By.TAG_NAME, "button"):
                    try:
                        if btn.text.strip().upper() == "JOIN" and btn.is_displayed():
                            safe_click(driver, btn)
                            log("Clicked JOIN (any visible)")
                            join_clicked = True
                            break
                    except StaleElementReferenceException:
                        continue

            if join_clicked:
                human_pause(5.0, 8.0)  # Wait for table + Buy-In modal to load
                log("JOIN clicked — waiting for table/buy-in")
                return True
            else:
                # No JOIN modal — check if Buy-In modal appeared directly
                body = driver.find_element(By.TAG_NAME, "body").text.upper()
                if "BUY-IN" in body or "BUY IN" in body:
                    log("Buy-In modal appeared directly (no JOIN modal)")
                    return True
                if "FOLD" in body or "CHECK" in body:
                    log("Table opened directly (no modals)")
                    return True
                log("No JOIN or Buy-In modal found after double-click")

        time.sleep(3)
    return False


# ---------------------------------------------------------------------------
# Seating & buy-in
# ---------------------------------------------------------------------------

def handle_buy_in(driver, mode, auto_buyin):
    """Handle the PokerBet Buy-In dialog.

    The Buy-In modal has:
    - REAL MONEY / CASH MONEY tabs
    - Available Balance display
    - Buy-In Amount field
    - MIN / MAX buttons (set buy-in amount)
    - Auto Buy-In checkbox
    - BUY-IN / CANCEL buttons

    Uses Selenium .text for element detection (CSS text-transform safe).
    """
    # Wait for Buy-In modal to appear
    log("Waiting for Buy-In modal...")
    deadline = time.time() + 15
    modal_found = False
    while time.time() < deadline:
        body = driver.find_element(By.TAG_NAME, "body").text.upper()
        if "BUY-IN" in body or "BUY IN" in body:
            modal_found = True
            log("Buy-In modal detected")
            break
        time.sleep(1)

    if not modal_found:
        return {"ok": False, "error": "Buy-in modal not found within 15s"}

    human_pause(1.0, 2.0)

    # Click MIN or MAX button
    min_max_clicked = False
    target = mode.upper()  # "MIN" or "MAX"
    for btn in driver.find_elements(By.TAG_NAME, "button"):
        try:
            txt = btn.text.strip().upper()
            if txt == target and btn.is_displayed():
                safe_click(driver, btn)
                log(f"Clicked {target} buy-in button")
                min_max_clicked = True
                break
        except StaleElementReferenceException:
            continue

    if not min_max_clicked:
        log(f"WARNING: {target} button not found, proceeding with default amount")

    human_pause(0.5, 1.0)

    # Auto buy-in checkbox
    if auto_buyin:
        for el in driver.find_elements(By.TAG_NAME, "label") + driver.find_elements(By.TAG_NAME, "span"):
            try:
                txt = el.text.strip().lower()
                if "auto" in txt and "buy" in txt:
                    safe_click(driver, el)
                    log("Clicked Auto Buy-In checkbox")
                    break
            except StaleElementReferenceException:
                continue

    human_pause(0.5, 1.0)

    # Click BUY-IN button (green confirm button)
    buyin_clicked = False

    # Try inside sg-modal first
    for modal in driver.find_elements(By.TAG_NAME, "sg-modal"):
        for btn in modal.find_elements(By.TAG_NAME, "button"):
            try:
                txt = btn.text.strip().upper()
                if ("BUY" in txt and "IN" in txt) or txt == "BUY-IN":
                    if btn.is_displayed():
                        safe_click(driver, btn)
                        log("Clicked BUY-IN button (in sg-modal)")
                        buyin_clicked = True
                        break
            except StaleElementReferenceException:
                continue
        if buyin_clicked:
            break

    if not buyin_clicked:
        # Fallback: any visible button with BUY-IN text
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            try:
                txt = btn.text.strip().upper()
                if ("BUY" in txt and "IN" in txt) or txt == "BUY-IN":
                    if btn.is_displayed():
                        safe_click(driver, btn)
                        log("Clicked BUY-IN button (fallback)")
                        buyin_clicked = True
                        break
            except StaleElementReferenceException:
                continue

    if not buyin_clicked:
        return {"ok": False, "error": "BUY-IN button not found"}

    human_pause(3.0, 5.0)
    return {"ok": True}


def verify_seated(driver, table_name, max_wait=30):
    """Verify the player is actually seated at the table.

    After buy-in, the table view should show the player's seat.
    Look for table-specific indicators: action buttons, hand info,
    lobby button, chat/emojis, or "wait for big blind".
    """
    deadline = time.time() + max_wait
    while time.time() < deadline:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        # Action buttons (visible when it's player's turn)
        if "fold" in body or "check" in body or "call" in body:
            log("Verified seated: action buttons visible")
            return {"ok": True}
        # Table view indicators (visible even when not player's turn)
        if "wait for big blind" in body or "emojis" in body or "hand id" in body:
            log("Verified seated: table UI elements visible")
            return {"ok": True}
        # The tab at top shows the table name
        if table_name.lower() in body or "lobby" in body:
            # Check there's no Buy-In modal still showing
            if "buy-in" not in body and "buy in" not in body:
                log("Verified seated: table tab visible, no buy-in modal")
                return {"ok": True}
        time.sleep(2)
    return {"ok": False}


# ---------------------------------------------------------------------------
# First action
# ---------------------------------------------------------------------------

def first_action_assist(driver, policy):
    """Execute one CHECK or CALL then hand over to remote control."""
    if policy != "CHECK_OR_CALL_ONCE":
        return "skipped"

    deadline = time.time() + 60
    while time.time() < deadline:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            try:
                txt = btn.text.lower()
                if "check" in txt:
                    btn.click()
                    log("First action: CHECK")
                    return "check"
                if "call" in txt:
                    btn.click()
                    log("First action: CALL")
                    return "call"
            except StaleElementReferenceException:
                continue
        time.sleep(1)

    log("First action: timed out (no check/call available within 60s)")
    return "timeout"


# ---------------------------------------------------------------------------
# N4P.js injection
# ---------------------------------------------------------------------------

N4P_JS_PATH = "/tmp/n4p.js"
N4P_API_BASE = "http://172.31.17.239:5000/api"


def inject_n4p(driver, username, bot_id):
    """Inject n4p.js into the poker iframe for remote control scraping."""
    log(f"Injecting n4p.js for {username} (bot_id={bot_id})")

    # 1. Read n4p.js from the container filesystem (docker-cp'd by host)
    if not os.path.exists(N4P_JS_PATH):
        log(f"WARNING: {N4P_JS_PATH} not found — skipping n4p injection")
        return False

    with open(N4P_JS_PATH, "r") as f:
        n4p_code = f.read()

    if not n4p_code.strip():
        log("WARNING: n4p.js is empty — skipping injection")
        return False

    log(f"Read n4p.js: {len(n4p_code)} bytes")

    # 2. Ensure we're inside the poker iframe
    current_url = driver.execute_script("return window.location.href")
    if "18751019" not in current_url and "skillgames" not in current_url:
        log("Not inside poker iframe — switching to it")
        driver.switch_to.default_content()
        found_iframe = False
        for frame in driver.find_elements(By.TAG_NAME, "iframe"):
            src = frame.get_attribute("src") or ""
            if "18751019" in src or "skillgames" in src:
                driver.switch_to.frame(frame)
                found_iframe = True
                log("Switched to poker iframe for injection")
                break
        if not found_iframe:
            log("ERROR: Could not find poker iframe for n4p injection")
            return False

    # 3. Set window variables
    driver.execute_script(f"""
        window._botId = '{bot_id}';
        window._botLogin = '{username}';
        window._botScreenName = '{username}';
        window._n4p_api_base = '{N4P_API_BASE}';
    """)
    log("Set window._botId, _botLogin, _botScreenName, _n4p_api_base")

    # 4. Execute n4p.js code
    try:
        driver.execute_script(n4p_code)
        log("Executed n4p.js code")
    except Exception as e:
        log(f"ERROR executing n4p.js: {e}")
        return False

    # 5. Verify injection
    time.sleep(2)
    injected = driver.execute_script("return window._n4p_injected === true")
    has_build = driver.execute_script("return typeof window._n4p_buildSnapshot === 'function'")
    log(f"n4p injection check: injected={injected}, buildSnapshot={has_build}")

    if not injected and not has_build:
        log("WARNING: n4p.js not detected — retrying once")
        time.sleep(3)
        driver.execute_script(n4p_code)
        time.sleep(2)
        injected = driver.execute_script("return window._n4p_injected === true")
        has_build = driver.execute_script("return typeof window._n4p_buildSnapshot === 'function'")
        log(f"n4p retry check: injected={injected}, buildSnapshot={has_build}")

    return injected or has_build


# ---------------------------------------------------------------------------
# Remote control relay loop
# ---------------------------------------------------------------------------

RELAY_INTERVAL = 2  # seconds between snapshot relays
COMMAND_POLL_INTERVAL = 1  # seconds between command polls


def relay_snapshot(driver, api_base, bot_id):
    """Read DOM snapshot via n4p.js and POST it to Flask (Python-side relay).

    This bypasses browser mixed-content and CORS restrictions by using
    Python urllib instead of browser fetch().
    """
    import urllib.request
    import urllib.error

    log("Starting relay loop (Python-side snapshot relay)")
    snapshot_count = 0
    error_count = 0

    while True:
        try:
            # 1. Read snapshot from browser DOM
            snap = driver.execute_script("return typeof window._n4p_buildSnapshot === 'function' ? window._n4p_buildSnapshot() : null")
            if snap is None:
                if error_count % 30 == 0:  # Log every ~60s
                    log("Relay: _n4p_buildSnapshot not available")
                error_count += 1
                time.sleep(RELAY_INTERVAL)
                continue

            # Add bot identity
            snap["bot_id"] = bot_id

            # 2. POST snapshot to Flask API
            data = json.dumps(snap).encode("utf-8")
            req = urllib.request.Request(
                f"{api_base}/snapshot",
                data=data,
                headers={"Content-Type": "application/json", "X-API-Key": "trk_default"},
                method="POST",
            )
            try:
                resp = urllib.request.urlopen(req, timeout=5)
                resp.read()
                snapshot_count += 1
                if snapshot_count % 30 == 0:  # Log every ~60s
                    log(f"Relay: {snapshot_count} snapshots sent")
            except urllib.error.URLError as e:
                if error_count % 30 == 0:
                    log(f"Relay: POST failed: {e}")
                error_count += 1

            # 3. Poll for commands
            try:
                cmd_req = urllib.request.Request(
                    f"{api_base}/commands/pending?bot_id={bot_id}",
                    headers={"X-API-Key": "trk_default"},
                )
                cmd_resp = urllib.request.urlopen(cmd_req, timeout=5)
                cmd_data = json.loads(cmd_resp.read().decode("utf-8"))
                commands = cmd_data.get("commands", [])
                for cmd in commands:
                    execute_command(driver, cmd, api_base)
            except Exception:
                pass  # Command polling is best-effort

            time.sleep(RELAY_INTERVAL)

        except Exception as e:
            if "disconnected" in str(e).lower() or "session" in str(e).lower():
                log(f"Relay: Browser disconnected: {e}")
                break
            error_count += 1
            if error_count % 30 == 0:
                log(f"Relay: error #{error_count}: {e}")
            time.sleep(RELAY_INTERVAL)


def execute_command(driver, cmd, api_base):
    """Execute a remote control command (fold, check, call, raise)."""
    import urllib.request
    import urllib.error

    action = cmd.get("action", "").lower()
    cmd_id = cmd.get("id", "?")
    log(f"Relay: executing command {cmd_id}: {action}")

    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            try:
                txt = btn.text.strip().lower()
                if action in txt and btn.is_displayed():
                    btn.click()
                    log(f"Relay: clicked '{btn.text.strip()}' for command {cmd_id}")
                    break
            except StaleElementReferenceException:
                continue

        # ACK the command
        ack_data = json.dumps({"id": cmd_id, "status": "executed"}).encode("utf-8")
        ack_req = urllib.request.Request(
            f"{api_base}/commands/ack",
            data=ack_data,
            headers={"Content-Type": "application/json", "X-API-Key": "trk_default"},
            method="POST",
        )
        urllib.request.urlopen(ack_req, timeout=5)
    except Exception as e:
        log(f"Relay: command execution error: {e}")


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run(args):
    driver = None
    try:
        # --- STARTING ---
        write_status("STARTING")
        log(f"Starting bot for {args.username} → table '{args.table}' buyin={args.buyin}")
        driver = start_browser()

        # --- OPENING SITE ---
        write_status("OPENING_SITE")
        driver.get("https://www.pokerbet.co.za")
        human_pause(2.0, 3.0)

        # --- LOGGING IN ---
        write_status("LOGGING_IN")
        login(driver, args.username, args.password)

        # --- OPENING POKER ---
        write_status("OPENING_POKER")
        open_poker_client(driver)

        # --- SCANNING TABLES ---
        write_status("SCANNING_TABLES")
        found = find_and_open_table(driver, args.table)
        if not found:
            write_status("TABLE_NOT_FOUND", error=f"Table '{args.table}' not found")
            log(f"Table '{args.table}' not found")
            driver.quit()
            return

        # --- BUY IN ---
        # PokerBet auto-assigns a seat — the Buy-In modal appears after
        # double-clicking the table and clicking JOIN (or directly).
        write_status("SETTING_BUY_IN")
        buyin = handle_buy_in(driver, args.buyin, args.auto_buyin)
        if not buyin["ok"]:
            write_status("BUY_IN_FAILED", error=buyin.get("error"))
            log(f"Buy-in failed: {buyin.get('error')}")
            driver.quit()
            return

        # --- VERIFY ---
        write_status("VERIFYING_SEATED")
        seated = verify_seated(driver, args.table)
        if not seated["ok"]:
            write_status("SEATING_FAILED", error="Not seated after buy-in")
            log("Seating verification failed")
            driver.quit()
            return

        metadata = {
            "mode": "REMOTE_CONTROL",
            "buy_in_mode": args.buyin,
            "auto_buyin": args.auto_buyin,
        }
        write_status("SEATED_READY", metadata=metadata)
        log(f"{args.username} seated successfully")

        # --- N4P.JS INJECTION ---
        write_status("INJECTING_N4P")
        n4p_ok = inject_n4p(driver, args.username, args.bot_id)
        if n4p_ok:
            log("n4p.js injection successful")
            write_status("N4P_INJECTED", metadata={"n4p": True})
        else:
            log("WARNING: n4p.js injection failed — continuing without it")
            write_status("N4P_INJECTION_FAILED", metadata={"n4p": False})

        # --- FIRST ACTION ---
        if args.first_action:
            write_status("WAITING_FOR_FIRST_TURN")
            result = first_action_assist(driver, args.first_action)
            write_status("FIRST_ACTION_COMPLETED", metadata={"action": result})

        # --- REMOTE CONTROL ---
        write_status("REMOTE_CONTROL_ACTIVE")
        relay_snapshot(driver, N4P_API_BASE, args.bot_id)

        write_status("DISCONNECTED")

    except Exception as e:
        tb = traceback.format_exc()
        log(f"ERROR: {e}\n{tb}")
        write_status("ERROR", error=str(e))
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Bot Runner (in-container)")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--buyin", required=True, choices=["MIN", "MAX"])
    parser.add_argument("--bot-id", required=True)
    parser.add_argument("--auto-buyin", action="store_true", default=False)
    parser.add_argument("--first-action", default=None)
    args = parser.parse_args()

    # Clear previous status
    write_status("QUEUED")
    log(f"=== Bot Runner started: {args.username} / {args.bot_id} ===")

    run(args)


if __name__ == "__main__":
    main()
