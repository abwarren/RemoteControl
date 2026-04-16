#!/usr/bin/env python3
"""Dump the full CASH GAMES lobby list."""
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

# Login
for b in d.find_elements(By.TAG_NAME, "button"):
    if b.text.strip() == "SIGN IN":
        d.execute_script("arguments[0].click()", b)
        break
time.sleep(3)
for inp in d.find_elements(By.CSS_SELECTOR, "input[name=username]"):
    inp.send_keys("kele1")
for inp in d.find_elements(By.CSS_SELECTOR, "input[name=password]"):
    inp.send_keys("PokerPass123")
    inp.send_keys(Keys.RETURN)
time.sleep(5)

JS_REMOVE = 'document.querySelectorAll(".popup-middleware-bc,.popup-holder-bc").forEach(function(e){e.remove()})'
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
time.sleep(8)

# Switch iframe
for f in d.find_elements(By.TAG_NAME, "iframe"):
    src = f.get_attribute("src") or ""
    if "18751019" in src or "skillgames" in src:
        d.switch_to.frame(f)
        print("In poker iframe")
        break
time.sleep(3)

# Click CASH GAMES tab
for e in d.find_elements(By.XPATH, "//*[contains(text(),'CASH')]"):
    txt = e.text.strip()
    if "CASH" in txt.upper() and len(txt) < 20:
        d.execute_script("arguments[0].click()", e)
        print(f"Clicked: {txt}")
        break
time.sleep(3)

# Now click LOBBY if visible
for e in d.find_elements(By.XPATH, "//*[text()='LOBBY']"):
    d.execute_script("arguments[0].click()", e)
    print("Clicked LOBBY")
    break
time.sleep(3)

# Scroll down to load all tables
d.execute_script("window.scrollTo(0, document.body.scrollHeight)")
time.sleep(2)

body = d.find_element(By.TAG_NAME, "body").text
print("=== LOBBY TEXT (8000 chars) ===")
print(body[:8000])
print()

# Search for all table-like names
lines = body.split("\n")
table_names = []
for i, line in enumerate(lines):
    line = line.strip()
    if line and not line.startswith("ZAR") and not line.isdigit():
        if any(x in lines[min(i+1, len(lines)-1)] for x in ["Omaha", "Hold"]) or \
           any(x in line for x in ["Omaha", "Hold"]):
            continue
        if len(line) > 2 and len(line) < 30 and line[0].isupper():
            table_names.append(line)

print("=== POSSIBLE TABLE NAMES ===")
for name in table_names[:50]:
    print(f"  {name}")

if "algiers" in body.lower():
    print("\n>>> ALGIERS FOUND <<<")
else:
    print("\n>>> ALGIERS NOT IN LOBBY <<<")

d.quit()
