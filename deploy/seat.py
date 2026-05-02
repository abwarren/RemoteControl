#!/usr/bin/env python3
"""Seat a player at PokerBet PLO table - v2 (chromedriver launches Chrome)"""
import time, sys, os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

USERNAME = os.getenv("POKER_USERNAME", "")
PASSWORD = os.getenv("POKER_PASSWORD", "")
TABLE_XPATH = "/html/body/sg-app/div/sg-lobby/div/div/sg-poker-app/sg-table-category/div[1]/div[1]/sg-tables-list/div/div[2]/div/div/div[12]/div[2]/div/p"

print(f"Seating {USERNAME}...")

# Let chromedriver launch Chrome with proper options
opts = Options()
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
opts.add_argument("--start-maximized")
opts.add_argument("--no-first-run")
opts.add_argument("--disable-extensions-except=/opt/plo-equity/FINALEXT")
opts.add_argument("--load-extension=/opt/plo-equity/FINALEXT")

svc = Service("/usr/local/bin/chromedriver")
d = webdriver.Chrome(service=svc, options=opts)
print(f"Chrome started: {d.title}")

# Step 1: Direct nav to poker page
d.get("https://www.pokerbet.co.za/en/page/casino/poker/28")
time.sleep(8)
print("Page loaded")

# Step 2: Login
try:
    btn = d.find_elements(By.CSS_SELECTOR, "button.btn.s-small.sign-in")
    if btn and USERNAME:
        btn[0].click()
        time.sleep(3)
        un = d.find_elements(By.CSS_SELECTOR, "#login_form_id input[type=text]")
        if un:
            un[0].send_keys(USERNAME)
            pw = d.find_elements(By.CSS_SELECTOR, "#login_form_id input[type=password]")
            if pw:
                pw[0].send_keys(PASSWORD)
            sub = d.find_elements(By.CSS_SELECTOR, "#login_form_id button[type=submit]")
            if sub:
                d.execute_script("arguments[0].click()", sub[0])
            time.sleep(5)
            print(f"Logged in as {USERNAME}")
    else:
        print("Already logged in or no credentials")
except Exception as e:
    print(f"Login: {e}")

# Step 3: Click "Play" button
time.sleep(3)
d.execute_script("""
var buttons = document.querySelectorAll('button');
for (var i = 0; i < buttons.length; i++) {
    if (buttons[i].textContent.trim() === 'Play' && buttons[i].offsetParent) {
        buttons[i].click();
        break;
    }
}
""")
print("Clicked Play")
time.sleep(15)

# Step 4: Switch to game iframe
switched = False
for attempt in range(5):
    frames = d.find_elements(By.TAG_NAME, "iframe")
    for f in frames:
        src = f.get_attribute("src") or ""
        if "LaunchGame" in src or "skillgames" in src.lower():
            d.switch_to.frame(f)
            switched = True
            print(f"Switched to iframe: {src[:80]}")
            break
    if switched:
        break
    time.sleep(5)

if not switched:
    print("ERROR: No game iframe found")
    sys.exit(1)

time.sleep(5)

# Step 5: Click "Cash Games" tab
d.execute_script("""
var els = document.querySelectorAll('*');
for (var i = 0; i < els.length; i++) {
    if (els[i].textContent.trim() === 'Cash Games' && els[i].childNodes.length <= 3 && els[i].offsetParent) {
        els[i].click();
        break;
    }
}
""")
print("Clicked Cash Games")
time.sleep(5)

# Step 6: Click table by XPath
els = d.find_elements(By.XPATH, TABLE_XPATH)
if els:
    els[0].click()
    print(f"Clicked table: {els[0].text}")
else:
    print("ERROR: Table XPath not found")
    sys.exit(1)
time.sleep(3)

# Step 7: Click Join
d.execute_script("""
var buttons = document.querySelectorAll('button');
for (var i = 0; i < buttons.length; i++) {
    if (buttons[i].textContent.trim() === 'Join' && buttons[i].offsetParent) {
        buttons[i].click();
        break;
    }
}
""")
print("Clicked Join")
time.sleep(5)

# Step 8: MAX buy-in
d.execute_script("""
var els = document.querySelectorAll('button,span,div,li');
for (var i = 0; i < els.length; i++) {
    var t = els[i].textContent.trim();
    if ((t === 'Max' || t === 'MAX') && els[i].offsetParent && els[i].offsetWidth < 100) {
        els[i].click();
        break;
    }
}
""")
print("Clicked MAX")
time.sleep(2)

# Step 9: Confirm
d.execute_script("""
var buttons = document.querySelectorAll('button');
for (var i = 0; i < buttons.length; i++) {
    var t = buttons[i].textContent.trim().toUpperCase();
    if ((t.indexOf('CONFIRM') >= 0 || t.indexOf('BUY') >= 0 || t === 'OK') && buttons[i].offsetParent) {
        buttons[i].click();
        break;
    }
}
""")
print("SEATED - Confirm clicked")
time.sleep(3)

# Keep alive
print("Session active. Keeping alive...")
while True:
    time.sleep(60)
    try:
        d.title
    except:
        print("Session lost")
        break
