#!/usr/bin/env python3
"""PokerBet PLO Bot - Enhanced with Remote Control and Fingerprint Spoofing.

FEATURES:
- Remote control command polling (buy-in, fold, check, call, raise, cashout)
- Auto CHECK/CALL pre-action after seating (ONE automatic action)
- NO idle timeout - bots stay seated and only respond to remote control
- Fingerprint randomization (anti-detection)
- Human-like behavior (typing with typos, random delays)
- n4p.js injection for table state sync

BEHAVIOR:
1. Seat at table with MIN buy-in (default)
2. Immediately set CHECK/CALL pre-action
3. Wait for remote control commands ONLY
4. NO automatic sitting out, NO closing table

CRITICAL: n4p.js MUST be injected inside the poker iframe (skillgames / 18751019/*).
The iframe switch happens at Step 9 (driver.switch_to.frame). All JS after that point
runs inside the iframe context. Do NOT switch back to default_content before injecting.
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import os
import random
import json
import string
import requests

BUILD_SNAPSHOT_JS = """
return (function() {
    var match = location.href.match(/\/tbl\/(\d+)/);
    var tableId = match ? match[1] : null;
    if (!tableId) return null;
    var containers = document.querySelectorAll('.player-mini-container-p');
    if (containers.length === 0) return null;
    var fullTableEl = document.querySelector('.full-table-w-p');
    var tsM = fullTableEl ? fullTableEl.className.match(/player-count-(\d+)/) : null;
    var tableSize = tsM ? parseInt(tsM[1]) : 6;
    var dealerEl = document.querySelector('.dealer-icon-view');
    var dM = dealerEl ? dealerEl.className.match(/position-(\d+)/) : null;
    var dealerSeat = dM ? parseInt(dM[1]) : null;
    var potEl = document.querySelector('.pot-w-view-p');
    var potText = potEl ? potEl.innerText : '';
    var pM = potText.match(/([\d.,]+)/);
    var potZar = pM ? parseFloat(pM[1].replace(',', '')) : null;
    var allCards = document.querySelectorAll('.single-cart-view-p');
    var boardCards = [];
    for (var i = 0; i < allCards.length; i++) {
        var card = allCards[i];
        var isPC = false;
        var par = card.parentElement;
        while (par) { if (par.classList && par.classList.contains('player-mini-container-p')) { isPC = true; break; } par = par.parentElement; }
        if (!isPC) { var cm = card.className.match(/icon-layer2_([shdc])(10|[akqjt2-9])_p-c-d/i); if (cm) boardCards.push(cm[2].toLowerCase() + cm[1].toLowerCase()); }
    }
    var street = 'PREFLOP';
    if (boardCards.length >= 3) street = 'FLOP';
    if (boardCards.length >= 4) street = 'TURN';
    if (boardCards.length >= 5) street = 'RIVER';
    var board = { flop: boardCards.slice(0, 3), turn: boardCards[3] || null, river: boardCards[4] || null };
    var seats = [];
    for (var i = 0; i < containers.length; i++) {
        var c = containers[i];
        var isHero = c.classList.contains('self-player');
        var isSO = c.classList.contains('seat-out-v');
        var posM = c.className.match(/position-(\d+)/);
        var si = posM ? parseInt(posM[1]) : i;
        var nEl = c.querySelector('p.single-win-item-sizes');
        var nm = nEl ? nEl.innerText.trim() : null;
        var sEl = c.querySelector('.player-text-info-p span b');
        var sT = sEl ? sEl.innerText : '';
        var sM = sT.match(/([\d.,]+)/);
        var stk = sM ? parseFloat(sM[1].replace(',', '')) : null;
        var ccC = c.querySelector('.carts-container-p');
        var ccM = ccC ? ccC.className.match(/cards-count-(\d+)/) : null;
        var cc = ccM ? parseInt(ccM[1]) : 0;
        var hc = [];
        if (isHero) { var hcEls = c.querySelectorAll('.single-cart-view-p'); for (var j = 0; j < hcEls.length; j++) { var hcm = hcEls[j].className.match(/icon-layer2_([shdc])(10|[akqjt2-9])_p-c-d/i); if (hcm) hc.push(hcm[2].toLowerCase() + hcm[1].toLowerCase()); } }
        var st = 'playing'; if (isSO) st = 'sitting_out'; else if (cc === 0) st = 'folded';
        seats.push({ seat_index: si, name: nm, stack_zar: stk, hole_cards: hc, cards_count: cc, cards_visible: cc > 0, is_hero: isHero, is_dealer: si === dealerSeat, status: st });
    }
    return { table_id: tableId, variant: 'plo', table_size: tableSize, street: street, pot_zar: potZar, dealer_seat: dealerSeat, board: board, seats: seats, session_id: 'relay_' + Date.now() };
})();
"""

def relay_snapshot(driver, api_base, bot_id):
    api_key = os.getenv("TRACKER_API_KEY", "trk_default")
    try:
        snapshot = driver.execute_script(BUILD_SNAPSHOT_JS)
        if not snapshot:
            try:
                url = driver.execute_script("return window.location.href")
                body_len = driver.execute_script("return document.body ? document.body.innerText.length : -1")
                has_tbl = driver.execute_script("return /\/tbl\//.test(location.href)")
                pmc = driver.execute_script("return document.querySelectorAll('.player-mini-container-p').length")
                print(f"  [RELAY] No snapshot. url_has_tbl={has_tbl} pmc={pmc} body={body_len} url={url[:80]}")
            except Exception as dbg:
                print(f"  [RELAY] No snapshot (debug failed: {dbg})")
            return False
        snapshot["bot_id"] = bot_id
        hero = [s for s in snapshot.get("seats", []) if s.get("is_hero")]
        tbl = snapshot.get("table_id", "?")
        nseats = len(snapshot.get("seats", []))
        st = snapshot.get("street", "?")
        print(f"  [RELAY] table={tbl} seats={nseats} hero={len(hero)} street={st}")
        if not hero:
            try:
                classes = driver.execute_script('return Array.from(document.querySelectorAll(".player-mini-container-p")).map(function(c){return {hasSelf: c.classList.contains("self-player"), childSelf: c.querySelector(".self-player") !== null}})')
                print(f"  [RELAY] HERO DEBUG: {classes}")
            except:
                print("  [RELAY] HERO DEBUG: could not query DOM")
        resp = requests.post(
            api_base + "/snapshot",
            json=snapshot,
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
            timeout=5
        )
        if resp.status_code != 200:
            print(f"  [RELAY] POST {resp.status_code}: " + resp.text[:100])
        else:
            print("  [RELAY] POST 200")
        return resp.status_code == 200
    except Exception as e:
        print(f"  [RELAY] ERROR: {e}")
        return False



# ── Configuration ────────────────────────────────────────────────
USERNAME = os.getenv('POKER_USERNAME', 'Kele1')
PASSWORD = os.getenv('POKER_PASSWORD', 'PokerPass123')
TABLE_NAME = os.getenv('TABLE_NAME', 'Multan')  # City name from lobby
GAME_FILTER = os.getenv('GAME_FILTER', 'omaha_4')  # omaha_4, omaha_6, holdem
BUYIN_AMOUNT = os.getenv('BUYIN_AMOUNT', 'MIN')  # Default: MIN buy-in

# Remote Control API
API_BASE = os.getenv('API_BASE', 'http://172.31.17.239:5000/api')
COMMAND_POLL_INTERVAL = 5  # Poll every 5 seconds

# ── Human-Like Behavior Functions ────────────────────────────────

def human_pause(min_s=0.5, max_s=2.0):
    """Random pause to mimic human thinking."""
    time.sleep(random.uniform(min_s, max_s))

def human_type(element, text, typo_chance=0.15, min_typos=2):
    """Type like a human with occasional typos and corrections.

    typo_chance: probability of making a typo per character (default 8%)
    """
    # Ensure minimum typos by pre-selecting positions
    typo_positions = set()
    alpha_positions = [i for i, c in enumerate(text) if c.isalpha()]
    if alpha_positions and min_typos > 0:
        typo_positions = set(random.sample(alpha_positions, min(min_typos, len(alpha_positions))))

    for i, char in enumerate(text):
        # Random chance to make a typo (or forced for min_typos)
        if (i in typo_positions or random.random() < typo_chance) and char.isalpha():
            # Type a wrong character first
            wrong_char = random.choice(string.ascii_lowercase)
            element.send_keys(wrong_char)
            time.sleep(random.uniform(0.1, 0.3))
            # Pause like noticing the mistake
            time.sleep(random.uniform(0.2, 0.6))
            # Backspace to correct
            element.send_keys(Keys.BACKSPACE)
            time.sleep(random.uniform(0.05, 0.15))

        # Type the correct character
        element.send_keys(char)

        # Variable delay between keystrokes (faster for common sequences)
        if i > 0 and random.random() < 0.15:
            # Occasional longer pause (like thinking or looking at keyboard)
            time.sleep(random.uniform(0.3, 0.8))
        else:
            time.sleep(random.uniform(0.04, 0.22))

    # Pause after finishing typing
    time.sleep(random.uniform(0.3, 1.0))

def human_click(driver, element):
    """Click with slight random delay before and after."""
    human_pause(0.2, 0.7)
    driver.execute_script("arguments[0].click();", element)
    human_pause(0.3, 0.9)

def js_click(driver, selector_or_script):
    """Click via JS with human timing."""
    human_pause(0.2, 0.6)
    driver.execute_script(selector_or_script)
    human_pause(0.3, 0.8)



def is_overlay_present(driver):
    """Check if any overlay/loader is blocking interaction."""
    try:
        overlays = driver.find_elements(By.CSS_SELECTOR,
            ".loader, .overlay, [class*='loading'], [class*='loader'], "
            ".loader-popup-countdown, .modal-overlay, [class*='countdown']")
        return any(o.is_displayed() for o in overlays)
    except:
        return False

def wait_for_overlay_to_clear(driver, timeout=30):
    """Wait for all overlays to disappear with human-like polling."""
    start = time.time()
    while time.time() - start < timeout:
        if not is_overlay_present(driver):
            return True
        time.sleep(random.uniform(0.3, 0.7))
    raise Exception(f"Overlay did not clear within {timeout}s")

def wait_until_interactable(driver, selector, timeout=20):
    """Wait until element is clickable AND no overlay is blocking."""
    wait_for_overlay_to_clear(driver, timeout)
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
    if not element.is_displayed() or not element.is_enabled():
        raise Exception(f"Element {selector} exists but not interactable")
    return element

def safe_type(driver, selector, text, timeout=20):
    """Wait for interactability, then type with human behaviour."""
    element = wait_until_interactable(driver, selector, timeout)
    human_click(driver, element)
    human_pause(0.2, 0.5)
    human_type(element, text)
    return element

def safe_click(driver, selector, timeout=20):
    """Wait for interactability, then click with human behaviour."""
    element = wait_until_interactable(driver, selector, timeout)
    human_click(driver, element)
    return element

def check_session_conflict(driver):
    """Detect and dismiss 'logged out from another device' dialog."""
    try:
        result = driver.execute_script(
            "var dialogs = document.querySelectorAll('.modal, [class*=\"modal\"], [class*=\"popup\"]');"
            "for (var d of dialogs) {"
            "  if (d.textContent.indexOf('logged out') !== -1 || d.textContent.indexOf('another device') !== -1) {"
            "    var btn = d.querySelector('button');"
            "    if (btn) { btn.click(); return 'dismissed'; }"
            "    return 'found';"
            "  }"
            "}"
            "return 'none';"
        )
        if result != 'none':
            print(f"  [SESSION] Conflict dialog: {result}")
            return True
    except:
        pass
    return False


# ── Remote Control Command Functions ─────────────────────────────

def get_hero_seat(driver):
    """Get hero seat index from table."""
    try:
        hero_info = driver.execute_script("""
            var result = {seat_index: null, name: null};
            var players = document.querySelectorAll('.player-mini-container-p');
            for (var i = 0; i < players.length; i++) {
                var p = players[i];
                if (p.classList.contains('self-player') || (p.closest && p.closest('.self-player') !== null)) {
                    var nameEl = p.querySelector('.player-name-p, [class*="player-name"]');
                    result.name = nameEl ? nameEl.textContent.trim() : 'unknown';
                    result.seat_index = i;
                    break;
                }
            }
            return result;
        """)
        return hero_info['seat_index'], hero_info['name']
    except:
        return None, None


def get_table_id(driver):
    """Extract table ID from URL."""
    try:
        url = driver.execute_script("return window.location.href")
        # URL format: https://skillgames.pokerbet.xyz/18751019/<table_id>
        parts = url.split('/')
        if len(parts) >= 5:
            return parts[4]  # table_id
    except:
        pass
    return None


def poll_command(seat_token):
    """Poll for pending command from remote control."""
    try:
        response = requests.get(
            f'{API_BASE}/commands/pending',
            params={'token': seat_token},
            timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('ok') and data.get('command'):
                return data['command']
    except Exception as e:
        print(f"  [CMD] Poll error: {e}")
    return None


def ack_command(table_id, seat_index, command):
    """Acknowledge command completion."""
    try:
        response = requests.post(
            f'{API_BASE}/commands/ack',
            json={
                'table_id': table_id,
                'seat_index': seat_index,
                'command': command
            },
            timeout=3
        )
        return response.status_code == 200
    except:
        return False


def execute_buyin_command(driver, command_type):
    """Execute buy-in commands: buyin_min or buyin_max"""
    try:
        print(f"  [BUYIN] Executing {command_type}...")

        # Wait for buy-in modal
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "sg-buy-in-modal"))
        )

        if command_type == 'buyin_min':
            # Click MIN button
            driver.execute_script("""
                var modal = document.querySelector('sg-buy-in-modal');
                var btns = modal.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    if (btns[i].textContent.trim() === 'Min') { btns[i].click(); break; }
                }
            """)
            print(f"  [BUYIN] Clicked MIN")
            time.sleep(0.5)

        elif command_type == 'buyin_max':
            # Click MAX button
            driver.execute_script("""
                var modal = document.querySelector('sg-buy-in-modal');
                var btns = modal.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    if (btns[i].textContent.trim() === 'Max') { btns[i].click(); break; }
                }
            """)
            print(f"  [BUYIN] Clicked MAX")
            time.sleep(0.5)

        # Click EXECUTE button
        driver.execute_script("""
            var modal = document.querySelector('sg-buy-in-modal');
            var btns = modal.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].textContent.trim() === 'Buy-In') { btns[i].click(); break; }
            }
        """)
        print(f"  [BUYIN] Clicked EXECUTE")

        time.sleep(2)
        return True

    except Exception as e:
        print(f"  [BUYIN] ERROR: {e}")
        return False


def execute_action_command(driver, command):
    """Execute action commands: fold, check, call, raise_max, cashout"""
    try:
        print(f"  [ACTION] Executing {command}...")

        if command == 'fold':
            driver.execute_script("""
                var btns = document.querySelectorAll('button, .action-button, [class*="action"], [class*="btn"]');
                for (var i = 0; i < btns.length; i++) {
                    var txt = btns[i].textContent.trim().toLowerCase();
                    if (txt === 'fold' || txt === 'f') { btns[i].click(); break; }
                }
            """)
            print(f"  [ACTION] Clicked FOLD")

        elif command == 'check':
            driver.execute_script("""
                var btns = document.querySelectorAll('button, .action-button, [class*="action"], [class*="btn"]');
                for (var i = 0; i < btns.length; i++) {
                    var txt = btns[i].textContent.trim().toLowerCase();
                    if (txt === 'check' || txt === 'k') { btns[i].click(); break; }
                }
            """)
            print(f"  [ACTION] Clicked CHECK")

        elif command == 'call':
            driver.execute_script("""
                var btns = document.querySelectorAll('button, .action-button, [class*="action"], [class*="btn"]');
                for (var i = 0; i < btns.length; i++) {
                    var txt = btns[i].textContent.trim().toLowerCase();
                    if (txt.indexOf('call') !== -1 || txt === 'c') { btns[i].click(); break; }
                }
            """)
            print(f"  [ACTION] Clicked CALL")

        elif command == 'raise_max':
            # Click MAX raise button (or slider to max, then raise)
            driver.execute_script("""
                var maxBtn = null;
                var btns = document.querySelectorAll('button, [class*="max"], [class*="btn"]');
                for (var i = 0; i < btns.length; i++) {
                    var txt = btns[i].textContent.trim().toLowerCase();
                    if (txt === 'max' || txt === 'all-in') {
                        btns[i].click();
                        maxBtn = btns[i];
                        break;
                    }
                }

                // Then click Raise/Bet button
                setTimeout(function() {
                    var btns2 = document.querySelectorAll('button, .action-button, [class*="action"]');
                    for (var j = 0; j < btns2.length; j++) {
                        var txt2 = btns2[j].textContent.trim().toLowerCase();
                        if (txt2.indexOf('raise') !== -1 || txt2.indexOf('bet') !== -1) {
                            btns2[j].click();
                            break;
                        }
                    }
                }, 300);
            """)
            print(f"  [ACTION] Clicked RAISE MAX")

        elif command == 'cashout':
            # Click cashout/leave button
            driver.execute_script("""
                var btns = document.querySelectorAll('button, [class*="cashout"], [class*="leave"]');
                for (var i = 0; i < btns.length; i++) {
                    var txt = btns[i].textContent.trim().toLowerCase();
                    if (txt.indexOf('cashout') !== -1 || txt.indexOf('leave') !== -1) {
                        btns[i].click();
                        break;
                    }
                }
            """)
            print(f"  [ACTION] Clicked CASHOUT")

        time.sleep(1)
        return True

    except Exception as e:
        print(f"  [ACTION] ERROR: {e}")
        return False


def execute_preaction_command(driver, command):
    """Execute pre-action commands: check_fold, check_call, clear_preaction"""
    try:
        print(f"  [PREACTION] Executing {command}...")

        if command == 'check_fold':
            driver.execute_script("""
                var checkboxes = document.querySelectorAll('input[type="checkbox"], .checkbox, [class*="preaction"]');
                for (var i = 0; i < checkboxes.length; i++) {
                    var label = checkboxes[i].parentElement;
                    if (label && label.textContent.toLowerCase().indexOf('check/fold') !== -1) {
                        checkboxes[i].checked = true;
                        checkboxes[i].dispatchEvent(new Event('change', {bubbles: true}));
                        break;
                    }
                }
            """)
            print(f"  [PREACTION] Set CHECK/FOLD")

        elif command == 'check_call':
            driver.execute_script("""
                var checkboxes = document.querySelectorAll('input[type="checkbox"], .checkbox, [class*="preaction"]');
                for (var i = 0; i < checkboxes.length; i++) {
                    var label = checkboxes[i].parentElement;
                    if (label && label.textContent.toLowerCase().indexOf('check/call') !== -1) {
                        checkboxes[i].checked = true;
                        checkboxes[i].dispatchEvent(new Event('change', {bubbles: true}));
                        break;
                    }
                }
            """)
            print(f"  [PREACTION] Set CHECK/CALL")

        elif command == 'clear_preaction':
            driver.execute_script("""
                var checkboxes = document.querySelectorAll('input[type="checkbox"], .checkbox, [class*="preaction"]');
                for (var i = 0; i < checkboxes.length; i++) {
                    checkboxes[i].checked = false;
                    checkboxes[i].dispatchEvent(new Event('change', {bubbles: true}));
                }
            """)
            print(f"  [PREACTION] Cleared all")

        time.sleep(0.5)
        return True

    except Exception as e:
        print(f"  [PREACTION] ERROR: {e}")
        return False


def auto_check_call(driver):
    """Set CHECK/CALL pre-action immediately after seating."""
    try:
        print(f"  [AUTO] Setting CHECK/CALL pre-action...")
        time.sleep(2)  # Wait for UI to fully load
        driver.execute_script("""
            var checkboxes = document.querySelectorAll('input[type="checkbox"], .checkbox, [class*="preaction"]');
            for (var i = 0; i < checkboxes.length; i++) {
                var parent = checkboxes[i].parentElement;
                if (parent && parent.textContent.toLowerCase().indexOf('check') !== -1 && parent.textContent.toLowerCase().indexOf('call') !== -1) {
                    checkboxes[i].checked = true;
                    checkboxes[i].dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                }
            }
            return false;
        """)
        print(f"  [AUTO] ✅ CHECK/CALL pre-action set")
        return True
    except Exception as e:
        print(f"  [AUTO] ERROR setting CHECK/CALL: {e}")
        return False


# ── Main Bot Logic ───────────────────────────────────────────────

try:
    # ── STEP 1: Setup Firefox ──────────────────────────────────────
    print("[1] Starting Firefox...")
    opts = Options()
    opts.binary_location = "/usr/bin/firefox"
    opts.accept_insecure_certs = True
    opts.set_preference("browser.cache.disk.enable", False)
    opts.set_preference("browser.cache.memory.enable", False)
    opts.set_preference("browser.cache.offline.enable", False)
    opts.set_preference("network.http.use-cache", False)
    opts.set_preference("security.mixed_content.block_active_content", False)
    opts.set_preference("security.mixed_content.block_display_content", False)
    opts.set_preference("permissions.default.image", 1)
    opts.set_preference("dom.webdriver.enabled", False)
    opts.set_preference('useAutomationExtension', False)
    opts.set_preference("general.useragent.override",
        "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0")

    # Fingerprint randomization
    opts.set_preference("privacy.resistFingerprinting", True)
    opts.set_preference("webgl.disabled", False)
    opts.set_preference("media.peerconnection.enabled", False)

    service = Service(executable_path="/usr/local/bin/geckodriver")
    driver = webdriver.Firefox(service=service, options=opts)
    driver.set_window_size(1280, 800)
    wait = WebDriverWait(driver, 20)

    # Load n4p.js from file if available
    N4P_CODE = None
    if os.path.exists('/app/n4p.js'):
        with open('/app/n4p.js', 'r') as f:
            N4P_CODE = f.read()
        print("  n4p.js loaded from file")

    # ── STEP 2: Navigate to PokerBet ───────────────────────────────
    # Clear all cookies and cache before starting
    driver.delete_all_cookies()
    print("  Cleared cookies and cache")
    print("[2] Loading pokerbet.co.za...")
    driver.get("https://www.pokerbet.co.za/")
    human_pause(2.0, 3.5)

    # Close popup if present
    print("[2] Checking for popup...")
    try:
        popup = driver.find_element(By.CSS_SELECTOR, "div.popup-middleware-bc button")
        human_click(driver, popup)
        print("  Closed popup")
        human_pause(0.8, 1.5)
    except:
        print("  No popup")

    # ── STEP 2b: Log out if already logged in ─────────────────────
    print("[2b] Checking if already logged in...")
    logged_in = driver.execute_script("""
        // Check for logout/user menu elements that indicate logged-in state
        var userMenu = document.querySelector('.user-name-bc, .hdr-user-info-bc, [class*="user-name"], [class*="logout"]');
        var signInBtn = null;
        var btns = document.querySelectorAll('button, a');
        for (var i = 0; i < btns.length; i++) {
            var t = btns[i].textContent.trim().toLowerCase();
            if (t === 'sign in' || t === 'log in') { signInBtn = btns[i]; break; }
        }
        return { loggedIn: !!userMenu || !signInBtn, hasUserMenu: !!userMenu, hasSignIn: !!signInBtn };
    """)
    print(f"  State: {logged_in}")
    if logged_in.get('loggedIn') or logged_in.get('hasUserMenu'):
        print("  Already logged in - logging out first...")
        driver.execute_script("""
            // Try clicking user menu then logout
            var userBtn = document.querySelector('.hdr-user-info-bc, .user-name-bc, [class*="user-menu"], [class*="account"]');
            if (userBtn) userBtn.click();
        """)
        human_pause(1.0, 2.0)
        driver.execute_script("""
            var els = document.querySelectorAll('a, button, span, div');
            for (var i = 0; i < els.length; i++) {
                var t = els[i].textContent.trim().toLowerCase();
                if (t === 'log out' || t === 'logout' || t === 'sign out') {
                    els[i].click();
                    return true;
                }
            }
            return false;
        """)
        human_pause(3.0, 5.0)
        print("  Logged out")
        # Reload page fresh
        driver.get("https://www.pokerbet.co.za/")
        human_pause(3.0, 5.0)

    # ── STEP 3: Sign In ───────────────────────────────────────────
    print("[3] Clicking Sign In...")
    human_pause(1.0, 2.0)
    # Try multiple approaches to click Sign In
    signed_in_clicked = False
    # Approach 1: Original CSS selector
    try:
        sign_in = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR,
            "#root > div.layout-header-holder-bc > header > "
            "div.hdr-main-content-bc > div.hdr-user-bc > "
            "div.hdr-sign-in-wrap-bc > button")))
        human_click(driver, sign_in)
        signed_in_clicked = True
        print("  Clicked Sign In (CSS)")
    except:
        pass
    # Approach 2: Text search
    if not signed_in_clicked:
        signed_in_clicked = driver.execute_script("""
            var els = document.querySelectorAll('button, a, span');
            for (var i = 0; i < els.length; i++) {
                var t = els[i].textContent.trim().toLowerCase();
                if (t === 'sign in' || t === 'log in' || t === 'login') {
                    els[i].click();
                    return true;
                }
            }
            return false;
        """)
        if signed_in_clicked:
            print("  Clicked Sign In (text search)")
    if not signed_in_clicked:
        print("  WARNING: Could not find Sign In button")
    human_pause(2.0, 3.0)

    # ── STEP 4: Enter Username ─────────────────────────────────────
    print(f"[4] Entering username: {USERNAME}...")
    print("  [PRE-LOGIN] Waiting for UI to be ready...")
    for attempt in range(3):
        try:
            wait_for_overlay_to_clear(driver, timeout=30)
            print("  Overlay cleared")
            username_field = wait_until_interactable(driver,
                "input[type='text'], input[name='username'], input[name*='user']", timeout=20)
            human_click(driver, username_field)
            human_pause(0.2, 0.5)
            human_type(username_field, USERNAME)
            print(f"  Username entered")
            break
        except Exception as e:
            print(f"  [RETRY {attempt+1}/3] Username entry failed: {e}")
            human_pause(1.0, 2.0)
    else:
        raise Exception("Could not enter username after 3 attempts")

    # ── STEP 5: Enter Password ─────────────────────────────────────
    print("[5] Entering password...")
    for attempt in range(3):
        try:
            wait_for_overlay_to_clear(driver, timeout=10)
            password_field = wait_until_interactable(driver,
                "input[type='password']", timeout=20)
            human_click(driver, password_field)
            human_pause(0.2, 0.5)
            human_type(password_field, PASSWORD)
            print(f"  Password entered")
            break
        except Exception as e:
            print(f"  [RETRY {attempt+1}/3] Password entry failed: {e}")
            human_pause(1.0, 2.0)
    else:
        raise Exception("Could not enter password after 3 attempts")

    # ── STEP 6: Submit Login ───────────────────────────────────────
    print("[6] Logging in...")
    human_pause(0.8, 1.5)
    # Try clicking the login button
    login_clicked = False
    login_selectors = [
        "#login_form_id button[type='submit']",
        "#login_form_id button",
        "form button[type='submit']",
        "button.btn-login",
    ]
    for sel in login_selectors:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, sel)
            human_click(driver, btn)
            login_clicked = True
            print(f"  Clicked login: {sel}")
            break
        except:
            continue
    if not login_clicked:
        # Fallback: press Enter on password field
        password_field.send_keys(Keys.RETURN)
        print("  Submitted via Enter key")
    human_pause(5.0, 7.0)

    # Verify login succeeded
    human_pause(3.0, 5.0)
    login_check = driver.execute_script("""
        var signInBtn = false;
        var btns = document.querySelectorAll('button, a');
        for (var i = 0; i < btns.length; i++) {
            var t = btns[i].textContent.trim().toLowerCase();
            if (t === 'sign in' || t === 'login' || t === 'log in') {
                signInBtn = true; break;
            }
        }
        var bal = document.querySelector('.balance-amount, [class*="balance"], .hdr-balance-bc');
        var balText = bal ? bal.textContent.trim() : 'not found';
        var username = document.querySelector('.user-name-bc, [class*="username"], [class*="user-name"]');
        return {
            stillShowsLogin: signInBtn,
            balance: balText,
            username: username ? username.textContent.trim() : 'not found',
            url: location.href
        };
    """)
    print(f"  Balance: {login_check.get('balance', 'unknown')}")
    print(f"  Username shown: {login_check.get('username', 'unknown')}")

    if login_check.get('stillShowsLogin'):
        print("  [WARN] Login may have FAILED - Sign In button still visible!")
        print("  Attempting login retry...")
        # Try clicking Sign In again and re-entering credentials
        driver.execute_script("""
            var btns = document.querySelectorAll('button, a');
            for (var i = 0; i < btns.length; i++) {
                var t = btns[i].textContent.trim().toLowerCase();
                if (t === 'sign in' || t === 'log in') { btns[i].click(); break; }
            }
        """)
        human_pause(2.0, 3.0)
        try:
            usr = driver.find_element(By.CSS_SELECTOR, "input[type='text'], input[name*='user'], input[placeholder*='user' i], input[placeholder*='email' i]")
            usr.clear()
            human_type(usr, USERNAME)
            pwd = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            pwd.clear()
            human_type(pwd, PASSWORD)
            # Click login button
            driver.execute_script("""
                var form = document.querySelector('form');
                if (form) {
                    var btn = form.querySelector('button[type="submit"], button');
                    if (btn) btn.click();
                } else {
                    var btns = document.querySelectorAll('button');
                    for (var i = 0; i < btns.length; i++) {
                        var t = btns[i].textContent.trim().toLowerCase();
                        if (t === 'log in' || t === 'login' || t === 'sign in') { btns[i].click(); break; }
                    }
                }
            """)
            print("  Login retry submitted")
            human_pause(4.0, 6.0)
        except Exception as e:
            print(f"  Login retry failed: {e}")

    # ── STEP 7: Navigate to Poker ──────────────────────────────────
    print("[7] Navigating to Poker...")
    human_pause(0.5, 1.5)
    # Try clicking poker tab first
    try:
        poker_tab = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR,
            "#root > div.layout-header-holder-bc > header > "
            "div.nav-content-bc > div > nav > "
            "ul.nav-menu.nav-menu-hide-items > "
            "li:nth-child(1) > a > span:nth-child(2)")))
        human_click(driver, poker_tab)
        print("  Clicked Poker tab")
    except:
        # Fallback: click any link/tab containing "Poker"
        clicked = driver.execute_script("""
            var links = document.querySelectorAll('a, span, li');
            for (var i = 0; i < links.length; i++) {
                var t = links[i].textContent.trim();
                if (t === 'Poker' || t === 'POKER') {
                    links[i].click();
                    return true;
                }
            }
            return false;
        """)
        if clicked:
            print("  Clicked Poker via text search")
        else:
            print("  WARNING: Could not find Poker tab")
    human_pause(1.5, 3.0)

    # ── STEP 8: Launch Poker Client ────────────────────────────────
    print("[8] Launching poker client...")
    human_pause(1.0, 2.0)

    # Check if poker iframe already exists
    poker_iframe_found = driver.execute_script("""
        var iframes = document.querySelectorAll('iframe');
        for (var i = 0; i < iframes.length; i++) {
            var src = iframes[i].src || '';
            if (src.indexOf('poker-web') !== -1 || src.indexOf('skillgames') !== -1 || src.indexOf('18751019') !== -1) {
                return true;
            }
        }
        return false;
    """)

    if not poker_iframe_found:
        print("  [8] No poker iframe yet. Trying to launch...")
        # Try clicking the original PLAY button
        play_selectors = [
            "#root > div.layout-content-holder-bc > div:nth-child(2) > div > div > button",
            "button.play-btn",
            "#root button[class*='play']",
            "div.layout-content-holder-bc button",
        ]
        clicked = False
        for sel in play_selectors:
            try:
                btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                human_click(driver, btn)
                print(f"  Found PLAY via: {sel}")
                clicked = True
                break
            except:
                continue

        if not clicked:
            # Try direct navigation to poker URL
            print("  [8] Trying direct poker URL...")
            driver.get("https://www.pokerbet.co.za/en/poker")
            human_pause(3.0, 5.0)

        human_pause(5.0, 7.0)

        # Check again for poker iframe
        poker_iframe_found = driver.execute_script("""
            var iframes = document.querySelectorAll('iframe');
            for (var i = 0; i < iframes.length; i++) {
                var src = iframes[i].src || '';
                if (src.indexOf('poker-web') !== -1 || src.indexOf('skillgames') !== -1 || src.indexOf('18751019') !== -1) {
                    return true;
                }
            }
            return false;
        """)

        if not poker_iframe_found:
            # Last resort: try /en/skillgames or /en/casino/poker
            for url in ["https://www.pokerbet.co.za/en/skillgames", "https://www.pokerbet.co.za/en/page/casino/poker"]:
                print(f"  [8] Trying: {url}")
                driver.get(url)
                human_pause(5.0, 8.0)
                poker_iframe_found = driver.execute_script("""
                    var iframes = document.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        var src = iframes[i].src || '';
                        if (src.indexOf('poker-web') !== -1 || src.indexOf('skillgames') !== -1 || src.indexOf('18751019') !== -1) {
                            return true;
                        }
                    }
                    return false;
                """)
                if poker_iframe_found:
                    break
    else:
        print("  [8] Poker iframe already present!")

    # Dump page state
    page_debug = driver.execute_script("""
        var iframes = document.querySelectorAll('iframe');
        var srcs = [];
        for (var i = 0; i < iframes.length; i++) srcs.push((iframes[i].src || '').substring(0, 60));
        return { url: location.href, iframes: srcs, iframeCount: iframes.length };
    """)
    print(f"  [8] URL: {page_debug.get('url', '')[:60]}")
    print(f"  [8] Iframes: {page_debug.get('iframes', [])}")

    if not poker_iframe_found:
        raise Exception("Could not find poker iframe after all attempts")

    human_pause(2.0, 3.0)

    # Dump page state for debugging
    page_debug = driver.execute_script("""
        var iframes = document.querySelectorAll('iframe');
        var iframeSrcs = [];
        for (var i = 0; i < iframes.length; i++) {
            iframeSrcs.push(iframes[i].src || iframes[i].getAttribute('src') || 'no-src');
        }
        var buttons = document.querySelectorAll('button');
        var btnTexts = [];
        for (var i = 0; i < Math.min(buttons.length, 10); i++) {
            btnTexts.push(buttons[i].textContent.trim().substring(0, 30));
        }
        return {
            url: location.href,
            title: document.title,
            iframeCount: iframes.length,
            iframeSrcs: iframeSrcs,
            buttonTexts: btnTexts,
            bodyLen: document.body ? document.body.innerHTML.length : 0
        };
    """)
    print(f"  [DEBUG] URL: {page_debug.get('url', '')[:80]}")
    print(f"  [DEBUG] Title: {page_debug.get('title', '')}")
    print(f"  [DEBUG] Iframes ({page_debug.get('iframeCount', 0)}): {page_debug.get('iframeSrcs', [])}")
    print(f"  [DEBUG] Buttons: {page_debug.get('buttonTexts', [])}")
    print(f"  [DEBUG] Body length: {page_debug.get('bodyLen', 0)}")

    # ── STEP 9: Enter Poker Iframe ─────────────────────────────────
    print("[9] Switching to poker iframe...")
    human_pause(2.0, 3.0)

    # Find the correct poker iframe (not the chat widget)
    all_iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"  [9] Found {len(all_iframes)} iframes")
    poker_iframe = None
    for ifr in all_iframes:
        src = ifr.get_attribute("src") or ""
        print(f"  [9] iframe src: {src[:80]}")
        if "poker-web" in src or "skillgames" in src or "18751019" in src:
            poker_iframe = ifr
            break

    if not poker_iframe:
        # Try by size - poker iframe should be the largest
        for ifr in all_iframes:
            src = ifr.get_attribute("src") or ""
            if "ladesk" not in src and "javascript" not in src and src:
                poker_iframe = ifr
                break

    if not poker_iframe and all_iframes:
        # Last resort: skip chat widgets, try remaining
        for ifr in all_iframes:
            src = ifr.get_attribute("src") or ""
            if "ladesk" not in src:
                poker_iframe = ifr
                break

    if poker_iframe:
        driver.switch_to.frame(poker_iframe)
        print(f"  [9] Entered poker iframe")
    else:
        # Fallback to first iframe
        print("  [9] WARNING: No poker iframe found, trying first iframe")
        driver.switch_to.frame(all_iframes[0])

    human_pause(2.0, 3.0)

    # Verify we're in the right place
    current_url = driver.execute_script("return location.href")
    print(f"  [9] iframe URL: {current_url[:80]}")
    if "poker-web" not in current_url and "skillgames" not in current_url:
        print("  [9] WARNING: May not be in poker iframe!")
        # Check for nested iframes
        nested = driver.find_elements(By.TAG_NAME, "iframe")
        for nf in nested:
            src = nf.get_attribute("src") or ""
            if "poker-web" in src or "skillgames" in src:
                driver.switch_to.frame(nf)
                print(f"  [9] Switched to nested poker iframe: {src[:80]}")
                break
    print("  Inside poker iframe")
    human_pause(1.0, 2.0)

    # ── STEP 10: Wait for lobby to load, then Cash Games Tab ──────
    print("[10] Waiting for poker lobby to load...")
    # Wait for sg-app or lobby elements to appear (up to 30s)
    lobby_loaded = False
    for wait_attempt in range(15):
        check = driver.execute_script("""
            var sg = document.querySelector('sg-app, sg-lobby, [class*="lobby"]');
            var mainEl = document.getElementById('mainElement');
            var childCount = mainEl ? mainEl.children.length : 0;
            return {
                sgApp: !!sg,
                mainEl: !!mainEl,
                mainChildren: childCount,
                url: location.href,
                bodyLen: document.body ? document.body.innerHTML.length : 0
            };
        """)
        print(f"  [10] Wait {wait_attempt+1}/15: sg={check.get('sgApp')}, mainChildren={check.get('mainChildren')}, bodyLen={check.get('bodyLen')}, url={str(check.get('url',''))[:60]}")
        if check.get('sgApp') or check.get('mainChildren', 0) > 2:
            lobby_loaded = True
            break
        time.sleep(2)

    if not lobby_loaded:
        print("  [10] WARNING: Lobby may not have loaded fully")

    print("[10] Clicking Cash Games...")
    tabs = driver.find_elements(By.CSS_SELECTOR, "sg-product-categories-nav li a span")
    for tab in tabs:
        if "CASH" in tab.text.upper():
            human_click(driver, tab)
            break
    human_pause(1.5, 2.5)

    # ── STEP 11: Filter by Game Type ───────────────────────────────
    print(f"[11] Selecting {GAME_FILTER} filter...")
    driver.execute_script(f"""
        var f = document.querySelector('li.filter-middle-li[data-game="{GAME_FILTER}"]');
        if (f) f.click();
    """)
    human_pause(4.0, 6.0)  # Longer wait for lobby tables to load

    # ── STEP 12: Table Selection with TABLE_NAME filter ─────────────
    if TABLE_NAME:
        print(f"[12] TABLE_NAME filter active: target='{TABLE_NAME}'")
    else:
        print("[12] No TABLE_NAME set — scanning for best PLO4 9-max table")

    table_selected = False
    max_table_attempts = 5

    for table_attempt in range(1, max_table_attempts + 1):
        print(f"  [12.{table_attempt}] Table selection attempt {table_attempt}/{max_table_attempts}")

        result = driver.execute_script("""
            var targetName = arguments[0];

            var rows = document.querySelectorAll('.lobby-p-list-items-rows > ul');
            if (rows.length === 0) rows = document.querySelectorAll('.lobby-p-list-items-rows ul');
            if (rows.length === 0) rows = document.querySelectorAll('sg-table-list ul, .table-list ul');
            if (rows.length === 0) rows = document.querySelectorAll('ul[class*="lobby"], ul[class*="table"]');

            // Diagnostic: what's in the DOM
            var bodySnippet = document.body ? document.body.innerHTML.substring(0, 500) : 'no body';
            var allUls = document.querySelectorAll('ul');
            var sgElements = document.querySelectorAll('[class*="lobby"]');
            console.log('[BOT] Lobby scan: ' + rows.length + ' tables, ' + allUls.length + ' ULs, ' + sgElements.length + ' lobby elements');

            if (rows.length === 0) {
                return { success: false, error: 'No tables in lobby (ULs=' + allUls.length + ', lobby-els=' + sgElements.length + ')', bodySnippet: bodySnippet.substring(0, 200) };
            }

            // If TABLE_NAME is set, find that specific table only
            if (targetName) {
                var targetLower = targetName.toLowerCase();
                for (var i = 0; i < rows.length; i++) {
                    var text = rows[i].textContent.toLowerCase();
                    if (text.indexOf(targetLower) !== -1) {
                        var seatMatch = rows[i].textContent.match(/(\\d+)\\/(\\d+)/);
                        var seatsUsed = seatMatch ? parseInt(seatMatch[1]) : 0;
                        var maxSeats = seatMatch ? parseInt(seatMatch[2]) : 9;
                        var stakesMatch = rows[i].textContent.match(/R\\s*(\\d+)/);
                        var stakes = stakesMatch ? parseInt(stakesMatch[1]) : 0;

                        rows[i].click();
                        return {
                            success: true,
                            matched: true,
                            targetName: targetName,
                            tableName: rows[i].textContent.substring(0, 60).trim(),
                            seats: maxSeats - seatsUsed,
                            stakes: stakes
                        };
                    }
                }
                return {
                    success: false,
                    matched: false,
                    targetName: targetName,
                    error: 'Target table "' + targetName + '" not found in lobby',
                    tablesScanned: rows.length
                };
            }

            // No TABLE_NAME — best-available PLO4 9-max
            var plo4Tables = [];
            for (var i = 0; i < rows.length; i++) {
                var text = rows[i].textContent;
                var isPLO4 = text.indexOf('PLO4') !== -1 ||
                            text.indexOf('Omaha 4') !== -1 ||
                            text.indexOf('PLO 4') !== -1;
                var is9Max = text.indexOf('9-max') !== -1 ||
                            text.indexOf('9 max') !== -1 ||
                            text.match(/\\d+\\/9/);

                if (isPLO4 && is9Max) {
                    var seatMatch = text.match(/(\\d+)\\/9/);
                    var seatsUsed = seatMatch ? parseInt(seatMatch[1]) : 8;
                    var stakesMatch = text.match(/R\\s*(\\d+)/);
                    var stakes = stakesMatch ? parseInt(stakesMatch[1]) : 99999;
                    plo4Tables.push({
                        row: rows[i], seats: 9 - seatsUsed, stakes: stakes,
                        name: text.substring(0, 50)
                    });
                }
            }

            if (plo4Tables.length > 0) {
                plo4Tables.sort(function(a, b) {
                    if (a.seats !== b.seats) return b.seats - a.seats;
                    return a.stakes - b.stakes;
                });
                var sel = plo4Tables[0];
                sel.row.click();
                return { success: true, matched: false, plo4Count: plo4Tables.length, seats: sel.seats, stakes: sel.stakes };
            }

            return { success: false, error: 'No PLO4 9-max tables found' };
        """, TABLE_NAME or "")

        if result and result.get('success'):
            if result.get('matched'):
                print(f"  [12] TARGET TABLE FOUND: '{result.get('targetName')}'")
                print(f"       Lobby entry: {result.get('tableName', '?')}")
            else:
                print(f"  [12] Best-available table selected (no TABLE_NAME filter)")
            print(f"       Seats available: {result.get('seats', '?')}")
            print(f"       Stakes: R{result.get('stakes', '?')}")
            table_selected = True
            break
        else:
            error_msg = result.get('error', 'unknown') if result else 'no result'
            if TABLE_NAME and result and not result.get('matched', True):
                print(f"  [12] TARGET TABLE NOT FOUND: '{TABLE_NAME}'")
                print(f"       Tables scanned: {result.get('tablesScanned', '?')}")
                print(f"       Join aborted because target table missing")
            else:
                print(f"  [12] Failed: {error_msg}")
                if result and result.get('bodySnippet'):
                    print(f"       DOM: {result['bodySnippet'][:150]}")
            if table_attempt < max_table_attempts:
                print("       Retrying in 5s...")
                time.sleep(5)

    if not table_selected:
        if TABLE_NAME:
            print(f"[12] FATAL: Target table '{TABLE_NAME}' not found after {max_table_attempts} attempts")
            print(f"     Join aborted — will NOT fall back to another table")
        else:
            print("[12] FATAL: Could not select any table after 3 attempts")
        driver.save_screenshot('/app/error_table_selection.png')
        driver.quit()
        sys.exit(1)

    human_pause(1.5, 2.5)

    # Check for STANDBY_MODE
    if os.getenv('STANDBY_MODE') == 'true':
        print("[STANDBY] Bot seated in lobby. Waiting for commands...")
        print("  Set STANDBY_MODE=false to auto-seat at table")
        while True:
            time.sleep(30)
            print("  [STANDBY] Still waiting...")
        sys.exit(0)

    # If STANDBY_MODE=false, proceed with normal seating flow
    # ── STEP 13: Click Join (Lobby) ────────────────────────────────
    print("[13] Clicking Join (lobby)...")
    human_pause(0.5, 1.5)
    driver.execute_script("""
        var btns = document.querySelectorAll('button');
        for (var i = 0; i < btns.length; i++) {
            if (btns[i].textContent.trim() === 'Join') { btns[i].click(); break; }
        }
    """)
    human_pause(2.0, 3.5)

    # ── STEP 14: Click Join in Modal ───────────────────────────────
    print("[14] Clicking Join in modal...")
    human_pause(0.5, 1.5)
    driver.execute_script("""
        // Try specific selector first
        var joinBtn = document.querySelector('sg-join-multiple-tables div.modal-button-container ul li:nth-child(1) button');
        if (joinBtn) { joinBtn.click(); return 'specific'; }
        // Fallback to generic modal search
        var modal = document.querySelector('sg-modal, sg-join-multiple-tables');
        if (modal) {
            var btns = modal.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].textContent.trim() === 'Join') { btns[i].click(); return 'generic'; }
            }
        }
        return 'none';
    """)
    human_pause(2.0, 3.5)

    # -- STEP 14b: If already seated, click table tab
    at_table = driver.execute_script("return document.querySelectorAll('sg-poker-table').length > 0;")
    if not at_table:
        tab_clicked = driver.execute_script('''
            var tab = document.querySelector('sg-poker-table-tab div p span i');
            if (!tab) tab = document.querySelector('sg-lobby-header div.header-container-p div sg-tabs div:nth-child(2) sg-poker-table-tab div p span i');
            if (tab) { tab.click(); return true; }
            return false;
        ''')
        if tab_clicked:
            print("  [14b] Already seated - clicked table tab")
            human_pause(2.0, 3.0)


    # ── STEP 15: Buy-In ────────────────────────────────────────────
    print(f"[15] Waiting for buy-in dialog... (Amount={BUYIN_AMOUNT})")
    seated = False
    for attempt in range(10):
        human_pause(1.5, 2.5)
        state = driver.execute_script("""
            return {
                sgTable: document.querySelectorAll('sg-poker-table').length,
                players: document.querySelectorAll('.player-mini-container-p').length,
                buyinModal: document.querySelectorAll('sg-buy-in-modal').length
            };
        """)

        if state['buyinModal'] > 0:
            print(f"  Buy-in dialog found! Amount={BUYIN_AMOUNT}")
            human_pause(0.5, 1.5)

            if BUYIN_AMOUNT == 'MAX':
                # Click Max button
                driver.execute_script("""
                    var modal = document.querySelector('sg-buy-in-modal');
                    var btns = modal.querySelectorAll('button');
                    for (var i = 0; i < btns.length; i++) {
                        if (btns[i].textContent.trim() === 'Max') { btns[i].click(); break; }
                    }
                """)
                print("  Clicked Max")
            elif BUYIN_AMOUNT == 'MIN':
                # Click Min button
                driver.execute_script("""
                    var modal = document.querySelector('sg-buy-in-modal');
                    var btns = modal.querySelectorAll('button');
                    for (var i = 0; i < btns.length; i++) {
                        if (btns[i].textContent.trim() === 'Min') { btns[i].click(); break; }
                    }
                """)
                print("  Clicked Min")
            else:
                # Click Min first to ensure valid amount, then set desired amount
                driver.execute_script("""
                    var modal = document.querySelector('sg-buy-in-modal');
                    var btns = modal.querySelectorAll('button');
                    for (var i = 0; i < btns.length; i++) {
                        if (btns[i].textContent.trim() === 'Min') { btns[i].click(); break; }
                    }
                """)
                human_pause(0.3, 0.6)
                # Now set desired amount via input using nativeInputValueSetter for Angular
                driver.execute_script(f"""
                    var modal = document.querySelector('sg-buy-in-modal');
                    var input = modal.querySelector('input[type="number"], input[type="range"], input[type="text"], input');
                    if (input) {{
                        var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        nativeSetter.call(input, '{BUYIN_AMOUNT}');
                        input.dispatchEvent(new Event('input', {{bubbles: true}}));
                        input.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }}
                """)
                print(f"  Set buy-in to ZAR {BUYIN_AMOUNT}")

            human_pause(0.8, 2.0)
            # Click Buy-In button
            driver.execute_script("""
                var modal = document.querySelector('sg-buy-in-modal');
                var btns = modal.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    if (btns[i].textContent.trim() === 'Buy-In') { btns[i].click(); break; }
                }
            """)
            print("  Buy-In clicked!")
            human_pause(4.0, 6.0)
            seated = True
            break

        if state['sgTable'] > 0 and state['buyinModal'] == 0:
            print("  Already at table!")
            seated = True
            break

        print(f"  Waiting... (attempt {attempt+1}/10)")

    # ── STEP 16: Verify Seated ─────────────────────────────────────
    human_pause(2.0, 3.0)
    final = driver.execute_script("""
        return {
            sgTable: document.querySelectorAll('sg-poker-table').length,
            players: document.querySelectorAll('.player-mini-container-p').length,
            selfPlayer: document.querySelectorAll('.self-player').length,
            buyinModal: document.querySelectorAll('sg-buy-in-modal').length,
            url: window.location.href
        };
    """)
    print(f"[16] State: {final}")
    driver.save_screenshot('/app/seated.png')

    if final['selfPlayer'] >= 2:
        print("[OK] Seated! (selfPlayer detected)")
    elif final['sgTable'] == 0:
        print("[ERROR] Failed to seat at table!")
        driver.save_screenshot('/app/error_seat.png')
        raise Exception(f"Not seated: sgTable={final['sgTable']} buyinModal={final['buyinModal']}")
    elif final['buyinModal'] > 0:
        print("[WARN] Modal still in DOM but trying to continue...")
        # Try clicking Buy-In one more time
        driver.execute_script("""
            var modal = document.querySelector('sg-buy-in-modal');
            if (modal) {
                var btns = modal.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    var txt = btns[i].textContent.trim();
                    if (txt === 'Buy-In' || txt === 'BUY-IN') { btns[i].click(); break; }
                }
            }
        """)
        human_pause(3.0, 5.0)
        recheck = driver.execute_script("""
            return { selfPlayer: document.querySelectorAll('.self-player').length }
        """)
        if recheck['selfPlayer'] < 2:
            driver.save_screenshot('/app/error_seat.png')
            raise Exception(f"Not seated: sgTable={final['sgTable']} buyinModal={final['buyinModal']}")
        print("[OK] Seated after retry!")

    # ── STEP 17: Get Table Info ────────────────────────────────────
    print("[17] SEATED! Getting table info...")
    table_info = driver.execute_script("""
        var result = {players: []};
        document.querySelectorAll('.player-mini-container-p').forEach(function(p) {
            var name = p.querySelector('.player-name-p, [class*="player-name"]');
            result.players.push({
                name: name ? name.textContent.trim() : 'unknown',
                isSelf: p.classList.contains('self-player') || (p.closest && p.closest('.self-player') !== null)
            });
        });
        result.url = window.location.href;
        return result;
    """)
    print(f"  Table: {json.dumps(table_info)}")

    # ── STEP 17b: Identity Mapping ─────────────────────────────────
    hero_screen_name = None
    for p in table_info.get('players', []):
        if p.get('isSelf'):
            raw_name = p.get('name', '')
            # Strip stack info (e.g., "Minkimas \u202dZAR 8\u202c" -> "Minkimas")
            hero_screen_name = raw_name.split('\u202d')[0].strip() if '\u202d' in raw_name else raw_name.strip()
            break
    if not hero_screen_name:
        hero_screen_name = USERNAME
    IDENTITY_MAP = {"login": USERNAME, "screen_name": hero_screen_name}
    print(f"[IDENTITY] Login '{USERNAME}' -> Screen name '{hero_screen_name}'")

    # ── STEP 18: Inject n4p.js ─────────────────────────────────────
    # CRITICAL: Must be inside poker iframe (skillgames / 18751019/*)
    # Verify we're in the correct iframe before injecting
    current_url = driver.execute_script("return window.location.href")
    if 'skillgames' not in current_url and '18751019' not in current_url:
        print(f"  [WARN] Not in poker iframe! URL: {current_url}")
        print("  Attempting to switch to poker iframe...")
        driver.switch_to.default_content()
        try:
            iframe = driver.find_element(By.TAG_NAME, "iframe")
            driver.switch_to.frame(iframe)
            current_url = driver.execute_script("return window.location.href")
            print(f"  Switched to iframe: {current_url}")
        except Exception as e:
            print(f"  [ERROR] Could not find iframe: {e}")
    print("[18] Injecting n4p.js...")
    if N4P_CODE:  # Use local file
        api_base = os.environ.get('API_BASE', 'https://test.potlimitomaha.xyz:8080/api')
        driver.execute_script(f"window._botId = '{USERNAME}'; window._botLogin = '{USERNAME}'; window._botScreenName = '{hero_screen_name}'; window._n4p_api_base = 'http://172.31.17.239:5000/api';")
        driver.execute_script(N4P_CODE)
        print("  n4p.js injected from local file!")
    else:
        # Set bot identity BEFORE loading n4p.js
        driver.execute_script(f"""
            window._botId = '{USERNAME}';
            window._botLogin = '{USERNAME}';
            window._botScreenName = '{hero_screen_name}';
            fetch('https://test.potlimitomaha.xyz:8080/static/n4p.js')
                .then(r => r.text())
                .then(code => {{ eval(code); window._n4p_injected = true; }})
                .catch(e => console.error('[N4P] fetch failed:', e));
        """)
        print(f"  n4p.js injected with botId='{USERNAME}', screenName='{hero_screen_name}'")

    human_pause(5.0, 8.0)

    # Verify n4p.js injection
    time.sleep(3)
    injection_status = driver.execute_script("""
        return {
            injected: window._n4p_injected || false,
            n4pActive: window._n4p_active || false
        };
    """)
    print(f"  [N4P] Status: {injection_status}")
    

    # ── STEP 19: Auto CHECK/CALL ───────────────────────────────────
    print("[19] Setting auto CHECK/CALL pre-action...")
    auto_check_call(driver)
    human_pause(2.0, 3.0)

    # ── STEP 20: Get Seat Token ────────────────────────────────────
    hero_seat, hero_name = get_hero_seat(driver)
    table_id = get_table_id(driver)

    if hero_seat is None or table_id is None:
        print("[ERROR] Could not determine seat or table ID!")
        raise Exception("Missing seat/table info")

    seat_token = f"seat_{hero_seat}"
    print(f"[20] Bot ready!")
    print(f"  User: {USERNAME} (seat {hero_seat})")
    print(f"  Table ID: {table_id}")
    print(f"  Seat Token: {seat_token}")
    print(f"  Command Polling: Every {COMMAND_POLL_INTERVAL}s")
    print(f"  Auto Action: CHECK/CALL only (no timeout, no sit out)")

    # ── STEP 21: Monitor + Command Polling ─────────────────────────
    print("[21] Monitoring and polling for commands...")

    poll_counter = 0

    while True:
        try:
            # Poll for commands every COMMAND_POLL_INTERVAL seconds
            if poll_counter % COMMAND_POLL_INTERVAL == 0:
                cmd = poll_command(seat_token)

                if cmd:
                    print(f"  [CMD] Received: {cmd}")

                    success = False

                    # Execute buy-in commands
                    if cmd in ['buyin_min', 'buyin_max']:
                        success = execute_buyin_command(driver, cmd)

                    # Execute action commands
                    elif cmd in ['fold', 'check', 'call', 'raise_max', 'cashout']:
                        success = execute_action_command(driver, cmd)

                    # Execute pre-action commands
                    elif cmd in ['check_fold', 'check_call', 'clear_preaction']:
                        success = execute_preaction_command(driver, cmd)

                    else:
                        print(f"  [CMD] Unknown command: {cmd}")

                    # Acknowledge if successful
                    if success:
                        if ack_command(table_id, hero_seat, cmd):
                            print(f"  [CMD] ✅ {cmd} completed and acknowledged")
                        else:
                            print(f"  [CMD] ⚠️ {cmd} completed but ACK failed")
                    else:
                        print(f"  [CMD] ❌ {cmd} failed")

            # Ensure we're in the poker iframe before querying DOM
            try:
                cur_url = driver.execute_script("return window.location.href")
                if "18751019" not in cur_url and "poker-web" not in cur_url:
                    driver.switch_to.default_content()
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for ifr in iframes:
                        src = ifr.get_attribute("src") or ""
                        if "18751019" in src or "skillgames" in src:
                            driver.switch_to.frame(ifr)
                            print("  [IFRAME] Re-entered poker iframe")
                            break
            except Exception as iframe_err:
                print(f"  [IFRAME] Switch error: {iframe_err}")

            # Check if still seated
            snap = driver.execute_script("""
                return {
                    players: document.querySelectorAll('.player-mini-container-p').length,
                    selfPlayer: document.querySelectorAll('.self-player').length,
                    sgTable: document.querySelectorAll('sg-poker-table').length
                };
            """)

            if snap['sgTable'] == 0:
                print("  [WARN] Lost table view! Attempting iframe recovery...")
                try:
                    driver.switch_to.default_content()
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for ifr in iframes:
                        src = ifr.get_attribute("src") or ""
                        if "18751019" in src or "skillgames" in src:
                            driver.switch_to.frame(ifr)
                            print("  [RECOVERY] Switched to poker iframe")
                            break
                except Exception as rec_err:
                    print(f"  [RECOVERY] Failed: {rec_err}")
            else:
                if poll_counter % 30 == 0:  # Print status every 30s
                    print(f"  [OK] players={snap['players']} self={snap['selfPlayer']}")

            # Relay snapshot every 2 seconds
            if poll_counter % 2 == 0:
                relay_snapshot(driver, API_BASE, USERNAME)

            poll_counter += 1
            time.sleep(1)  # Check every second

        except Exception as e:
            print(f"  [ERROR] Monitor: {e}")
            time.sleep(5)

except Exception as e:
    print(f"[FATAL] {e}")
    try:
        driver.save_screenshot('/app/error.png')
    except:
        pass
    raise
finally:
    driver.quit()
