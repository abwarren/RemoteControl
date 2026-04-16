#!/usr/bin/env python3
"""Quick script to dump the poker lobby text."""
import os, time
os.environ["DISPLAY"] = ":1"
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

opts = Options()
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
opts.add_argument("--window-size=1920,1080")
d = webdriver.Chrome(options=opts)
d.get("https://www.pokerbet.co.za")
time.sleep(5)

JS_REMOVE = 'document.querySelectorAll(".popup-middleware-bc,.popup-holder-bc").forEach(function(e){e.remove()})'

# SIGN IN — do NOT remove popups before this (login form IS a popup)
for b in d.find_elements(By.TAG_NAME, "button"):
    if b.text.strip() == "SIGN IN":
        d.execute_script("arguments[0].click()", b)
        print("Clicked SIGN IN")
        break
time.sleep(3)

for inp in d.find_elements(By.CSS_SELECTOR, "input[name=username]"):
    inp.send_keys("kele1")
    print("Filled username")
for inp in d.find_elements(By.CSS_SELECTOR, "input[name=password]"):
    inp.send_keys("PokerPass123")
    inp.send_keys(Keys.RETURN)
    print("Filled password + Enter")
time.sleep(5)

body = d.find_element(By.TAG_NAME, "body").text.lower()
if "balance" in body or "deposit" in body:
    print("LOGIN OK")
else:
    print("LOGIN FAILED? body starts with:", d.find_element(By.TAG_NAME, "body").text[:100])

d.execute_script(JS_REMOVE)

# POKER
for e in d.find_elements(By.TAG_NAME, "a"):
    if e.text.strip() == "POKER":
        d.execute_script("arguments[0].click()", e)
        break
time.sleep(5)

# PLAY
for e in d.find_elements(By.TAG_NAME, "a") + d.find_elements(By.TAG_NAME, "button"):
    if e.text.strip() == "PLAY":
        d.execute_script("arguments[0].click()", e)
        break
time.sleep(6)

# Switch iframe
for f in d.find_elements(By.TAG_NAME, "iframe"):
    src = f.get_attribute("src") or ""
    if "18751019" in src or "skillgames" in src:
        d.switch_to.frame(f)
        print("In poker iframe")
        break
time.sleep(2)

# CASH GAMES
for e in d.find_elements(By.XPATH, "//*[contains(text(),'CASH')]"):
    d.execute_script("arguments[0].click()", e)
    break
time.sleep(3)

body = d.find_element(By.TAG_NAME, "body").text
print("=== FULL LOBBY ===")
print(body[:5000])
print()
if "algiers" in body.lower():
    print(">>> ALGIERS FOUND <<<")
else:
    print(">>> ALGIERS NOT IN LOBBY <<<")

d.quit()
