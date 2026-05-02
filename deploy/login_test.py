#!/usr/bin/env python3
"""Login to PokerBet once, report success/fail, then exit."""
import time, sys, os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

USERNAME = os.getenv("POKER_USERNAME", "")
PASSWORD = os.getenv("POKER_PASSWORD", "")

opts = Options()
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
opts.add_argument("--window-size=1920,1080")

svc = Service()
d = webdriver.Chrome(options=opts, service=svc)

try:
    # Navigate to poker page
    d.get("https://www.pokerbet.co.za/en/page/casino/poker/28")
    time.sleep(8)

    # Check if already logged in
    bal = d.find_elements(By.CSS_SELECTOR, "[class*=balance]")
    if bal:
        print(f"ALREADY_LOGGED_IN: {USERNAME}")
        d.quit()
        sys.exit(0)

    # Click Sign In
    btn = d.find_elements(By.CSS_SELECTOR, "button.btn.s-small.sign-in")
    if not btn:
        btn = d.find_elements(By.XPATH, "//button[contains(text(),'Sign In') or contains(text(),'SIGN IN') or contains(text(),'Log In')]")
    if btn:
        btn[0].click()
        time.sleep(3)
    else:
        print(f"NO_SIGNIN_BUTTON: {USERNAME}")
        d.quit()
        sys.exit(1)

    # Enter credentials
    un = d.find_elements(By.CSS_SELECTOR, "#login_form_id input[type=text]")
    if not un:
        un = d.find_elements(By.CSS_SELECTOR, "input[name=username], input[placeholder*=user]")
    if un:
        un[0].clear()
        un[0].send_keys(USERNAME)
        pw = d.find_elements(By.CSS_SELECTOR, "#login_form_id input[type=password]")
        if not pw:
            pw = d.find_elements(By.CSS_SELECTOR, "input[type=password]")
        if pw:
            pw[0].clear()
            pw[0].send_keys(PASSWORD)
        sub = d.find_elements(By.CSS_SELECTOR, "#login_form_id button[type=submit]")
        if not sub:
            sub = d.find_elements(By.CSS_SELECTOR, "button[type=submit]")
        if sub:
            d.execute_script("arguments[0].click()", sub[0])
            time.sleep(6)
    else:
        print(f"NO_INPUT_FIELDS: {USERNAME}")
        d.quit()
        sys.exit(1)

    # Verify login
    bal = d.find_elements(By.CSS_SELECTOR, "[class*=balance]")
    if bal:
        print(f"LOGIN_SUCCESS: {USERNAME} balance={bal[0].text}")
    else:
        # Check for error message
        err = d.find_elements(By.CSS_SELECTOR, ".error-message, .alert-danger, [class*=error]")
        if err:
            print(f"LOGIN_FAILED: {USERNAME} error={err[0].text}")
        else:
            print(f"LOGIN_UNKNOWN: {USERNAME} (no balance, no error)")
finally:
    d.quit()
