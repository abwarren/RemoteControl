# Bot Seating & Synchronization - Complete Master Document
**Full Navigation Path + Synchronization Mode of Operation**

**Date:** 2026-04-06  
**Status:** Production-Tested Architecture  
**Purpose:** Complete end-to-end flow from bot startup → seated → synced with remote control

---

## TABLE OF CONTENTS

1. [Overview](#1-overview)
2. [Full Navigation Path (19 Steps)](#2-full-navigation-path-19-steps)
3. [Synchronization Mode of Operation](#3-synchronization-mode-of-operation)
4. [Multi-Bot Coordination](#4-multi-bot-coordination)
5. [Failure Points & Recovery](#5-failure-points--recovery)
6. [Deployment Commands](#6-deployment-commands)
7. [Verification & Testing](#7-verification--testing)

---

## 1. OVERVIEW

### 1.1 The Problem

**You have 9 bots that need to:**
1. Navigate to PokerBet site
2. Login with unique credentials
3. Find a specific table (e.g., "Belgrade")
4. Join and get seated
5. Inject data collector (n4p.js)
6. Send snapshots to remote control
7. Stay synchronized with remote control UI

### 1.2 The Solution Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT STAGE                             │
└─────────────────────────────────────────────────────────────────┘
                          ↓
        ┌─────────────────────────────────┐
        │  Docker Container per Bot       │
        │  - Chrome + Selenium            │
        │  - poker_bot_production.py      │
        │  - Environment variables        │
        └─────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                    NAVIGATION STAGE (19 Steps)                  │
│  Force Logout → Login → Poker Lobby → Table Search             │
│  → Join (Step 1) → Join (Step 2) → Buy-in → Seated             │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                    SYNCHRONIZATION STAGE                        │
│  Inject n4p.js → Start Polling → Send Snapshots                │
│  → Remote Control Receives → UI Updates                        │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                    OPERATIONAL STAGE                            │
│  Bot: Passive mode + 1 emergency action                        │
│  n4p.js: Snapshot every 2s, poll commands every 1s             │
│  Remote Control: Send commands, receive snapshots              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Key URLs

| Component | URL | Purpose |
|-----------|-----|---------|
| **Poker Site** | https://www.pokerbet.co.za | Login and game lobby |
| **Logout** | /en/page/auth/logout | Force clean session |
| **Poker Lobby** | /en/page/casino/poker/28?openGames=28-real&gameNames=Poker | Direct entry to poker |
| **Game Iframe** | Contains `18751019` in src | Actual poker client |
| **Remote Control** | https://test.nuts4poker.com:8080 | Control dashboard |
| **n4p.js Script** | https://test.nuts4poker.com:8080/n4p.js | Data collector |
| **API Endpoint** | https://test.nuts4poker.com:8080/api/ | Backend API |

---

## 2. FULL NAVIGATION PATH (19 Steps)

### PHASE 1: PRE-AUTHENTICATION (Steps 1-4)

#### Step 1: Force Logout
**Purpose:** Clear any existing session, start fresh  
**Method:** Direct URL navigation  
**URL:** `https://www.pokerbet.co.za/en/page/auth/logout`  
**Duration:** 2-3 seconds  

**Why Critical:**
- Prevents "already logged in" conflicts
- Clears cached session state
- Ensures bot knows exact starting state

```python
driver.get("https://www.pokerbet.co.za/en/page/auth/logout")
time.sleep(3)
```

---

#### Step 2: Load Poker Lobby
**Purpose:** Navigate directly to poker section  
**Method:** Direct URL with query params  
**URL:** `/en/page/casino/poker/28?openGames=28-real&gameNames=Poker`  
**Duration:** 3-5 seconds  

**Selectors:**
- Wait for page load: `body` element visible
- Look for login button: text contains "Sign In"

```python
lobby_url = "https://www.pokerbet.co.za/en/page/casino/poker/28?openGames=28-real&gameNames=Poker"
driver.get(lobby_url)
time.sleep(5)
```

---

#### Step 3: Dismiss Popups/Overlays
**Purpose:** Close any promotional overlays  
**Method:** Click close buttons, try multiple selectors  
**Retries:** 2 attempts  

**Common Popup Selectors:**
- `.close-button`
- `button[aria-label="Close"]`
- `.modal-close`
- `//button[contains(text(), "Close")]`

```python
def dismiss_popups():
    selectors = [
        "button.close",
        "button[aria-label='Close']",
        "//button[contains(text(), 'Close')]"
    ]
    for selector in selectors:
        try:
            elem = driver.find_element(By.CSS_SELECTOR, selector)
            elem.click()
            time.sleep(1)
        except:
            pass
```

---

#### Step 4: Click Sign In Button
**Purpose:** Open login modal  
**Method:** Text-based search (NOT CSS selector)  
**Retries:** 3 attempts with 2s delay  

**Selector:** `//button[contains(text(), 'Sign In')]`  
**Success Indicator:** Login form visible (username + password fields)

```python
for attempt in range(3):
    try:
        sign_in = driver.find_element(By.XPATH, "//button[contains(text(), 'Sign In')]")
        sign_in.click()
        time.sleep(2)
        # Verify login form appeared
        driver.find_element(By.NAME, "username")  # Verify
        break
    except:
        time.sleep(2)
```

---

### PHASE 2: AUTHENTICATION (Steps 5-7)

#### Step 5: Enter Username
**Purpose:** Input login username  
**Method:** Find by name attribute, clear + send_keys  
**Field:** `input[name="username"]`  
**Value:** From `POKER_USERNAME` environment variable  

```python
username_field = driver.find_element(By.NAME, "username")
username_field.clear()
username_field.send_keys(os.environ["POKER_USERNAME"])
time.sleep(1)
```

---

#### Step 6: Enter Password
**Purpose:** Input login password  
**Method:** Find by name attribute, clear + send_keys  
**Field:** `input[name="password"]` or `input[type="password"]`  
**Value:** From `POKER_PASSWORD` environment variable  

```python
password_field = driver.find_element(By.NAME, "password")
password_field.clear()
password_field.send_keys(os.environ["POKER_PASSWORD"])
time.sleep(1)
```

---

#### Step 7: Submit Login
**Purpose:** Submit credentials and authenticate  
**Method:** Click submit button OR press Enter  
**Retries:** 2 attempts  

**Selectors:**
- `button[type="submit"]`
- `//button[contains(text(), 'Log In')]`
- Fallback: Press Enter on password field

**Success Indicator:**
- Login modal closes
- User menu appears (profile icon or username display)
- URL changes or page reloads

```python
try:
    submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Log In')]")
    submit_btn.click()
except:
    # Fallback: press Enter
    password_field.send_keys(Keys.RETURN)

time.sleep(5)  # Wait for login to complete
```

---

### PHASE 3: NAVIGATION TO POKER CLIENT (Steps 8-10)

#### Step 8: Dismiss "Mission Leader" Popup (Optional)
**Purpose:** Close promotional daily mission popup  
**Method:** Uncheck "Don't show again" + close  
**Frequency:** Only appears once per day per account  

**Selectors:**
- Checkbox: `input[type="checkbox"]` near text "Don't show"
- Close button: `.close-button` or `//button[contains(text(), 'Close')]`

```python
try:
    # Uncheck "don't show again"
    checkbox = driver.find_element(By.XPATH, "//input[@type='checkbox']")
    if checkbox.is_selected():
        checkbox.click()
    
    # Close popup
    close_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Close')]")
    close_btn.click()
    time.sleep(2)
except:
    pass  # Popup may not appear
```

---

#### Step 9: Navigate to Poker Section
**Purpose:** Click "Poker" tab if not already there  
**Method:** Text-based search  
**May Skip:** If already in poker lobby from direct URL  

**Selector:** `//div[contains(text(), 'Poker')]`  
**Success Indicator:** Poker lobby visible with game tiles

```python
try:
    poker_tab = driver.find_element(By.XPATH, "//div[contains(text(), 'Poker')]")
    poker_tab.click()
    time.sleep(3)
except:
    pass  # Already in poker section
```

---

#### Step 10: Enter Poker Client Iframe
**Purpose:** Switch Selenium context to poker game iframe  
**Method:** Search for iframe containing `18751019` in src  
**Critical:** All subsequent actions happen inside this iframe  

**Iframe Identifier:** URL contains `18751019`  
**Full Pattern:** `https://poker-web.pokerbet.co.za/18751019/#/...`

```python
iframes = driver.find_elements(By.TAG_NAME, "iframe")
for iframe in iframes:
    src = iframe.get_attribute("src") or ""
    if "18751019" in src:
        driver.switch_to.frame(iframe)
        print("[OK] Switched to poker client iframe")
        break
else:
    raise Exception("Poker iframe not found")

time.sleep(3)
```

---

### PHASE 4: TABLE SELECTION (Steps 11-12)

#### Step 11: Click "Cash Games" Tab
**Purpose:** Navigate to cash game lobby (vs tournaments)  
**Method:** Text-based button search  
**Context:** Inside poker client iframe  

**Selector:** `//button[contains(text(), 'Cash Games')]`  
**Success Indicator:** Cash game table list visible

```python
cash_games_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Cash Games')]")
cash_games_btn.click()
time.sleep(3)
```

---

#### Step 12: Select Game Filter (Omaha 4-card)
**Purpose:** Filter to show only PLO 4-card tables  
**Method:** Text-based filter button  
**Options:** "Omaha 4", "Omaha 6", "Hold'em", "All"  

**Selector:** `//button[contains(text(), 'Omaha 4')]`  
**From Environment:** `GAME_FILTER` env var (default: "omaha_4")

```python
game_filter = os.environ.get("GAME_FILTER", "omaha_4")
filter_text = "Omaha 4" if game_filter == "omaha_4" else "Omaha 6"

filter_btn = driver.find_element(By.XPATH, f"//button[contains(text(), '{filter_text}')]")
filter_btn.click()
time.sleep(2)
```

---

### PHASE 5: TABLE JOIN (Steps 13-16)

#### Step 13: Find Target Table by Name
**Purpose:** Locate specific table in lobby  
**Method:** Search DOM for table name text  
**Name Source:** `TABLE_NAME` environment variable (e.g., "Belgrade")  

**Search Strategy:**
1. Get all table elements (usually in a list or grid)
2. Iterate through each table card
3. Look for text matching `TABLE_NAME`
4. Store reference to JOIN button

```python
table_name = os.environ["TABLE_NAME"]  # e.g., "Belgrade"

# Search all table cards
table_cards = driver.find_elements(By.XPATH, "//div[contains(@class, 'table-card')]")

for card in table_cards:
    text = card.text
    if table_name.lower() in text.lower():
        # Found target table
        join_btn = card.find_element(By.XPATH, ".//button[contains(text(), 'Join')]")
        print(f"[OK] Found table: {table_name}")
        break
else:
    raise Exception(f"Table '{table_name}' not found")
```

---

#### Step 14: JOIN Step 1 (Lobby Join)
**Purpose:** First click on "Join" button in lobby  
**Method:** Click JOIN button found in Step 13  
**Result:** Opens `sg-modal` dialog (NOT buy-in modal yet)  

**Critical:** This is step 1 of 3-step join process  
**Success Indicator:** Modal appears with another "Join" button inside

```python
join_btn.click()
time.sleep(2)

# Verify modal opened
modal = driver.find_element(By.CLASS_NAME, "sg-modal")
print("[OK] JOIN Step 1: Modal opened")
```

---

#### Step 15: JOIN Step 2 (Modal Join)
**Purpose:** Second click on "Join" inside modal dialog  
**Method:** Find and click "Join" button inside `sg-modal`  
**Result:** Opens table view + `sg-buy-in-modal`  

**Critical:** This is step 2 of 3-step join process  
**Success Indicator:** Buy-in modal appears with amount input

**Selector:** `//div[@class='sg-modal']//button[contains(text(), 'Join')]`

```python
modal_join_btn = driver.find_element(
    By.XPATH, 
    "//div[@class='sg-modal']//button[contains(text(), 'Join')]"
)
modal_join_btn.click()
time.sleep(3)

# Verify buy-in modal appeared
buyin_modal = driver.find_element(By.CLASS_NAME, "sg-buy-in-modal")
print("[OK] JOIN Step 2: Buy-in modal opened")
```

---

#### Step 16: Set Buy-in and Confirm (JOIN Step 3)
**Purpose:** Set buy-in amount and complete seating  
**Method:** Select MIN/MAX or enter custom amount  
**Result:** Bot is seated at table  

**Buy-in Options:**
- MIN: Click "Min" button
- MAX: Click "Max" button
- Custom: Enter amount in input field

**Steps:**
1. Select buy-in amount
2. Enable "Auto Buy-in" checkbox (optional)
3. Click "Buy-In" confirm button
4. Wait for seating confirmation

```python
buyin_amount = os.environ.get("BUYIN_AMOUNT", "MIN")

if buyin_amount == "MIN":
    min_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Min')]")
    min_btn.click()
elif buyin_amount == "MAX":
    max_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Max')]")
    max_btn.click()
else:
    # Custom amount
    amount_input = driver.find_element(By.CSS_SELECTOR, "input[type='number']")
    amount_input.clear()
    amount_input.send_keys(buyin_amount)

time.sleep(1)

# Enable auto buy-in
try:
    auto_checkbox = driver.find_element(By.XPATH, "//input[@type='checkbox']")
    if not auto_checkbox.is_selected():
        auto_checkbox.click()
except:
    pass

# Confirm buy-in
confirm_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Buy-In')]")
confirm_btn.click()
time.sleep(5)

print("[OK] JOIN Step 3: Buy-in confirmed, seating...")
```

---

### PHASE 6: VERIFICATION (Step 17)

#### Step 17: Verify Seated
**Purpose:** Confirm bot is successfully seated at table  
**Method:** Check for "selfPlayer" indicator in DOM  
**Retries:** 5 attempts with 3s delay  

**Success Indicators:**
- Element with class `selfPlayer` or `self-player` exists
- Player name matches `POKER_USERNAME`
- Stack amount visible
- Hole cards placeholder visible (when hand starts)

**Failure Scenarios:**
- Seating timeout (waiting list)
- Insufficient balance
- Table full

```python
def verify_seated():
    for attempt in range(5):
        try:
            # Check for selfPlayer indicator
            self_player = driver.find_element(By.CSS_SELECTOR, "[class*='selfPlayer']")
            
            # Get table state
            state = driver.execute_script("""
                return {
                    selfPlayer: document.querySelectorAll("[class*='selfPlayer']").length,
                    players: document.querySelectorAll("[class*='player']").length,
                    sgTable: document.querySelectorAll("[class*='sg-table']").length
                };
            """)
            
            if state["selfPlayer"] > 0:
                print(f"[OK] Seated! (selfPlayer detected)")
                print(f"[State] {state}")
                return True
        except:
            pass
        
        time.sleep(3)
    
    raise Exception("Seating verification failed")

verify_seated()
```

---

### PHASE 7: SYNCHRONIZATION SETUP (Steps 18-19)

#### Step 18: Inject n4p.js Data Collector
**Purpose:** Load data collection script into poker client  
**Method:** Fetch from HTTPS server + eval  
**Critical:** Must use server URL, NOT local file  

**Why Server Fetch:**
- Poker site is HTTPS → n4p.js must be HTTPS
- Same-origin fetch avoids CORS
- Dynamic updates without bot restart

**Injection Command:**
```javascript
fetch('https://test.nuts4poker.com:8080/n4p.js')
  .then(r => r.text())
  .then(eval)
  .catch(e => console.error('[N4P] Failed:', e));
```

**Verification:**
```javascript
window._n4p_injected  // Should be true
window.N4P            // Should be object with sendSnapshot()
```

**Full Python Implementation:**
```python
def inject_n4p():
    injection_script = """
    (function() {
        if (window._n4p_injected) {
            console.log('[N4P] Already injected');
            return;
        }
        
        fetch('https://test.nuts4poker.com:8080/n4p.js')
            .then(r => {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.text();
            })
            .then(code => {
                eval(code);
                console.log('[N4P] Injection successful');
            })
            .catch(e => {
                console.error('[N4P] Injection failed:', e);
            });
    })();
    """
    
    driver.execute_script(injection_script)
    time.sleep(3)
    
    # Verify injection
    injected = driver.execute_script("return window._n4p_injected === true")
    if injected:
        print("[OK] n4p.js injected successfully")
        return True
    else:
        print("[WARN] n4p.js injection status unclear")
        return False

inject_n4p()
```

**Alternative Method (CDP Pre-injection):**
```python
# If using Chrome DevTools Protocol
driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
    'source': open('/app/n4p.js', 'r').read()
})
```

---

#### Step 19: Enter Monitoring Loop
**Purpose:** Keep bot alive and monitor state  
**Method:** Infinite loop with status checks  
**Frequency:** Every 15-60 seconds  

**Monitoring Tasks:**
1. Check if still seated (selfPlayer exists)
2. Check if n4p.js still loaded
3. Re-inject n4p.js if lost
4. Handle ONE emergency action (CHECK/CALL)
5. Log status

**Bot Policy:**
- **Passive Mode:** Wait for remote control commands
- **Emergency Action:** ONE CHECK or CALL allowed (prevents timeout)
- **After First Action:** Fully passive
- **Re-injection:** If `window._n4p_injected` becomes false

```python
def monitoring_loop():
    action_taken = False
    seated_time = time.time()
    
    while True:
        try:
            # Check n4p.js status
            n4p_status = driver.execute_script("return window._n4p_injected === true")
            
            if not n4p_status:
                print("[WARN] n4p.js lost, re-injecting...")
                inject_n4p()
            
            # Check seated status
            state = driver.execute_script("""
                return {
                    selfPlayer: document.querySelectorAll("[class*='selfPlayer']").length,
                    players: document.querySelectorAll("[class*='player']").length,
                    actionButtons: document.querySelectorAll("button[class*='action']").length
                };
            """)
            
            # Emergency action (only once)
            if not action_taken and state["actionButtons"] > 0:
                try:
                    # Look for CHECK button first, fallback to CALL
                    check_btn = driver.find_element(
                        By.XPATH, 
                        "//button[contains(@class, 'action') and contains(text(), 'Check')]"
                    )
                    check_btn.click()
                    print("[ACTION] Emergency CHECK taken")
                    action_taken = True
                except:
                    try:
                        call_btn = driver.find_element(
                            By.XPATH, 
                            "//button[contains(@class, 'action') and contains(text(), 'Call')]"
                        )
                        call_btn.click()
                        print("[ACTION] Emergency CALL taken")
                        action_taken = True
                    except:
                        pass
            
            # Log status
            elapsed = int(time.time() - seated_time)
            print(f"[💓 {elapsed}s] players={state['players']} "
                  f"n4p={n4p_status} actions={state['actionButtons']} "
                  f"emergency_used={action_taken}")
            
            time.sleep(60)  # Check every 60 seconds
            
        except Exception as e:
            print(f"[ERROR] Monitoring loop: {e}")
            time.sleep(30)

monitoring_loop()
```

---

## 3. SYNCHRONIZATION MODE OF OPERATION

### 3.1 Data Flow Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   BOT (CHROME + SELENIUM)                    │
│  poker_bot_production.py running in Docker container        │
└──────────────────────────────────────────────────────────────┘
                          ↓
                  Injects n4p.js (Step 18)
                          ↓
┌──────────────────────────────────────────────────────────────┐
│            N4P.JS (INJECTED IN POKER CLIENT)                 │
│  Runs inside iframe, extracts card data from DOM             │
└──────────────────────────────────────────────────────────────┘
          ↓ Every 2s                        ↑ Every 1s
   POST /api/snapshot                GET /api/commands/pending
          ↓                                  ↑
┌──────────────────────────────────────────────────────────────┐
│              FLASK BACKEND (app.py)                          │
│  - Stores snapshots in _snapshot_store                      │
│  - Queues commands in _command_queue                        │
│  - Merges data for /api/table/latest                        │
└──────────────────────────────────────────────────────────────┘
          ↓ Every 1s
   GET /api/table/latest
          ↓
┌──────────────────────────────────────────────────────────────┐
│           REMOTE CONTROL UI (Browser)                        │
│  Displays all 9 seats, sends commands via buttons           │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Polling Intervals

| Component | Action | Frequency | Endpoint |
|-----------|--------|-----------|----------|
| **n4p.js → Backend** | Send snapshot | Every 2 seconds | POST /api/snapshot |
| **n4p.js → Backend** | Poll for commands | Every 1 second | GET /api/commands/pending |
| **UI → Backend** | Get table state | Every 1 second | GET /api/table/latest |
| **UI → Backend** | Get hand history | Every 2 seconds | GET /api/hands/recent |
| **Bot → n4p.js** | Check injection status | Every 60 seconds | window._n4p_injected |

### 3.3 Snapshot Payload

**Sent by n4p.js every 2 seconds:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 3,
  "name": "Player1",
  "stack_zar": 200.50,
  "hole_cards": ["Ah", "Kh", "Qd", "Jc"],
  "board_cards": ["As", "Ks", "Qh"],
  "pot_zar": 150.00,
  "status": "playing",
  "is_hero": true,
  "timestamp": 1775432100
}
```

**Backend Storage:**
```python
_snapshot_store = {
  "tbl_2143037:3": {
    "seat_index": 3,
    "name": "Player1",
    "stack_zar": 200.50,
    "hole_cards": ["Ah", "Kh", "Qd", "Jc"],
    "last_seen": 1775432100
  }
}
```

### 3.4 Command Queue

**User clicks CALL button on Seat 3:**
```
1. UI sends: POST /api/commands/queue
   {
     "table_id": "tbl_2143037",
     "seat_index": 3,
     "command_type": "call"
   }

2. Backend stores:
   _command_queue["<seat_token>"] = {
     "id": "abc123",
     "type": "call",
     "status": "pending"
   }

3. n4p.js polls: GET /api/commands/pending?token=<seat_token>
   Response: {"ok": true, "command": {"id": "abc123", "type": "call"}}

4. n4p.js executes: document.querySelector(".action-call").click()

5. n4p.js sends: POST /api/commands/ack
   {
     "token": "<seat_token>",
     "command_id": "abc123"
   }

6. Backend removes command from queue
```

### 3.5 Seat Token Generation

**Backend generates unique token per seat:**
```python
def generate_seat_token(table_id, seat_index):
    import hmac
    import hashlib
    
    message = f"{table_id}:{seat_index}"
    secret = "your-secret-key"
    
    token = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    
    return token
```

**Token Example:**
- Table: `tbl_2143037`, Seat: `3`
- Token: `a7f8e4c2b9d1e6f3`
- Used for: Command queue key, auth for polling

---

## 4. MULTI-BOT COORDINATION

### 4.1 The 9-Bot Setup

**Container Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│  HOST SERVER (EC2 or Production Server)                     │
│                                                              │
│  Docker Containers:                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ chrome1      │  │ chrome2      │  │ chrome3      │      │
│  │ User: Kele1  │  │ User: pile   │  │ User: lont   │      │
│  │ Table: -     │  │ Table: -     │  │ Table: -     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ chrome4      │  │ chrome5      │  │ chrome6      │      │
│  │ User: Kana   │  │ User: hele   │  │ User: player6│      │
│  │ Table: -     │  │ Table: -     │  │ Table: -     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ chrome7      │  │ chrome8      │  │ chrome9      │      │
│  │ User: player7│  │ User: player8│  │ User: player9│      │
│  │ Table: -     │  │ Table: -     │  │ Table: -     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Synchronized Seating

**Objective:** All 9 bots join the SAME table (e.g., "Belgrade")

**Method:**
1. Set `TABLE_NAME=Belgrade` for all 9 bots
2. Launch bots with 5-second stagger (prevent simultaneous join)
3. Each bot completes 19-step navigation independently
4. Backend merges all 9 snapshots into single table view

**Stagger Script:**
```bash
#!/bin/bash
# Launch all 9 bots with 5s delay between each

CONTAINERS=(chrome1 chrome2 chrome3 chrome4 chrome5 chrome6 chrome7 chrome8 chrome9)
USERS=(Kele1 pile lont Kana hele player6 player7 player8 player9)

for i in "${!CONTAINERS[@]}"; do
    container="${CONTAINERS[$i]}"
    username="${USERS[$i]}"
    
    echo "[$(date)] Launching $username in $container..."
    
    docker exec -d "$container" bash -c "
        export POKER_USERNAME=$username
        export POKER_PASSWORD=PokerPass123
        export TABLE_NAME=Belgrade
        export BUYIN_AMOUNT=MIN
        nohup python3 /app/poker_bot_production.py > /tmp/bot.log 2>&1 &
    "
    
    # Wait 5 seconds before next bot
    sleep 5
done

echo "[$(date)] All 9 bots launched"
```

### 4.3 Table Merging

**Backend Merge Logic:**
```python
def _merge_table(table_id):
    """
    Merge all seat snapshots for a given table_id
    Returns single table object with 9 seats
    """
    seats = []
    
    for seat_index in range(9):
        key = f"{table_id}:{seat_index}"
        snapshot = _snapshot_store.get(key)
        
        if snapshot:
            # Seat occupied
            seats.append({
                "seat_index": seat_index,
                "name": snapshot.get("name"),
                "stack_zar": snapshot.get("stack_zar", 0),
                "hole_cards": snapshot.get("hole_cards", []),
                "board_cards": snapshot.get("board_cards", []),
                "status": snapshot.get("status", "idle"),
                "is_hero": True,  # All bots are self-player
                "is_dealer": snapshot.get("is_dealer", False),
                "last_seen_ago": time.time() - snapshot.get("timestamp", 0)
            })
        else:
            # Seat empty
            seats.append({
                "seat_index": seat_index,
                "name": None,
                "stack_zar": 0,
                "hole_cards": [],
                "status": "empty",
                "is_hero": False,
                "last_seen_ago": None
            })
    
    # Get board from any seat (all should have same board)
    board_cards = []
    pot_zar = 0
    for seat in seats:
        if seat["board_cards"]:
            board_cards = seat["board_cards"]
            pot_zar = _snapshot_store.get(f"{table_id}:{seat['seat_index']}", {}).get("pot_zar", 0)
            break
    
    return {
        "table_id": table_id,
        "seats": seats,
        "board": board_cards,
        "pot_zar": pot_zar,
        "street": get_street(board_cards),
        "last_updated": int(time.time())
    }
```

### 4.4 Hero-Only Architecture

**Critical Concept: ALL players are "self-player"**

**Traditional Poker Bot:**
- 1 hero (you)
- 8 villains (opponents with face-down cards)

**This System:**
- 9 heroes (all bots controlled by you)
- 0 villains
- ALL cards visible
- ALL stacks known
- Perfect information

**Benefits:**
- No card inference needed
- No villain modeling
- Simple data aggregation
- Direct control of entire table

**Data Structure:**
```json
{
  "table_id": "tbl_2143037",
  "seats": [
    {
      "seat_index": 0,
      "name": "Kele1",
      "is_hero": true,
      "hole_cards": ["Ah", "Kh", "Qd", "Jc"]
    },
    {
      "seat_index": 1,
      "name": "pile",
      "is_hero": true,
      "hole_cards": ["6c", "Kh", "9d", "Th"]
    },
    {
      "seat_index": 2,
      "name": "lont",
      "is_hero": true,
      "hole_cards": ["Qh", "Jc", "Ts", "8c"]
    }
  ]
}
```

---

## 5. FAILURE POINTS & RECOVERY

### 5.1 Common Failure Scenarios

| Step | Failure | Symptom | Recovery |
|------|---------|---------|----------|
| **2** | Lobby not loading | Timeout waiting for page | Retry with longer wait, check network |
| **7** | Login fails | "Invalid credentials" | Verify env vars, check account status |
| **10** | Iframe not found | "18751019" not in any iframe | Wait longer, refresh page |
| **12** | Table not found | "Belgrade" not in lobby | Check table name spelling, verify table exists |
| **14-16** | Join fails | Stuck in modal or buy-in fails | Check balance, table may be full, retry |
| **17** | Seating timeout | selfPlayer not detected | May be on waiting list, check table occupancy |
| **18** | n4p.js injection fails | Fetch error or eval exception | Check n4p.js URL accessibility, CORS issues |
| **19** | Snapshots not reaching backend | UI shows empty seats | Check API endpoint, verify n4p.js executing |

### 5.2 Diagnostic Commands

**Check bot logs:**
```bash
docker exec <container> tail -f /tmp/bot.log
```

**Check if bot process running:**
```bash
docker exec <container> ps aux | grep bot.py
```

**Check n4p.js injection status:**
```bash
docker exec <container> python3 -c "
from selenium import webdriver
driver = webdriver.Chrome()
# ... navigate to table ...
status = driver.execute_script('return window._n4p_injected')
print(f'n4p.js injected: {status}')
"
```

**Test snapshot API:**
```bash
curl -X POST https://test.nuts4poker.com:8080/api/snapshot \
  -H "Content-Type: application/json" \
  -d '{"table_id":"test","seat_index":0,"name":"TestBot","hole_cards":["as","kd"]}' -k

curl -s https://test.nuts4poker.com:8080/api/table/latest -k | jq .
```

### 5.3 Recovery Procedures

**Full Bot Restart:**
```bash
# Kill bot process
docker exec <container> pkill -f bot.py

# Wait for cleanup
sleep 3

# Restart bot
docker exec -d <container> bash -c "
    export POKER_USERNAME=<username>
    export POKER_PASSWORD=<password>
    export TABLE_NAME=Belgrade
    export BUYIN_AMOUNT=MIN
    nohup python3 /app/poker_bot_production.py > /tmp/bot.log 2>&1 &
"
```

**Re-inject n4p.js without bot restart:**
```python
# Run inside bot container
from selenium import webdriver

# Assuming driver is still active
injection_script = """
fetch('https://test.nuts4poker.com:8080/n4p.js')
  .then(r => r.text())
  .then(eval);
"""
driver.execute_script(injection_script)
```

**Clear backend snapshot store (if stale data):**
```bash
# SSH to server
ssh -i /home/ploxyz.pem ubuntu@test.nuts4poker.com

# Restart Flask app
ps aux | grep app.py
kill <PID>
cd /opt/plo-equity
nohup venv/bin/python app.py &
```

---

## 6. DEPLOYMENT COMMANDS

### 6.1 Single Bot Deployment

**Deploy to one container (e.g., chrome1 → Kele1 → Belgrade):**
```bash
#!/bin/bash

CONTAINER="chrome1"
USERNAME="Kele1"
PASSWORD="PokerPass123"
TABLE="Belgrade"
BUYIN="MIN"

# Restart container for clean state
docker restart "$CONTAINER"
sleep 5

# Copy latest bot script
docker cp /opt/pokerbet-selenium/poker_bot_production.py "$CONTAINER":/app/bot.py

# Launch bot
docker exec -d "$CONTAINER" bash -c "
    export PATH=/usr/local/bin:\$PATH
    export POKER_USERNAME=$USERNAME
    export POKER_PASSWORD=$PASSWORD
    export TABLE_NAME=$TABLE
    export BUYIN_AMOUNT=$BUYIN
    nohup python3 /app/bot.py > /tmp/bot.log 2>&1 &
"

echo "✅ Bot launched: $USERNAME → $TABLE"
echo "📋 Monitor logs: docker exec $CONTAINER tail -f /tmp/bot.log"
```

### 6.2 All 9 Bots Parallel Deployment

**Deploy all bots to same table:**
```bash
#!/bin/bash
# deploy_all_bots.sh

TABLE="Belgrade"
BUYIN="MIN"

BOTS=(
  "chrome1:Kele1"
  "chrome2:pile"
  "chrome3:lont"
  "chrome4:Kana"
  "chrome5:hele"
  "chrome6:player6"
  "chrome7:player7"
  "chrome8:player8"
  "chrome9:player9"
)

for bot_config in "${BOTS[@]}"; do
  IFS=':' read -r container username <<< "$bot_config"
  
  echo "🚀 [$(date +%H:%M:%S)] Deploying $username to $TABLE..."
  
  # Restart container
  docker restart "$container" 2>/dev/null
  sleep 3
  
  # Copy bot script
  docker cp /opt/pokerbet-selenium/poker_bot_production.py "$container":/app/bot.py
  
  # Launch bot
  docker exec -d "$container" bash -c "
    export PATH=/usr/local/bin:\$PATH
    export POKER_USERNAME=$username
    export POKER_PASSWORD=PokerPass123
    export TABLE_NAME=$TABLE
    export BUYIN_AMOUNT=$BUYIN
    nohup python3 /app/bot.py > /tmp/bot.log 2>&1 &
  "
  
  # Stagger launches (5 seconds)
  sleep 5
done

echo "✅ All 9 bots deployed to $TABLE"
echo "📊 Monitor: https://test.nuts4poker.com:8080"
```

### 6.3 Monitoring Script

**Check status of all bots:**
```bash
#!/bin/bash
# check_all_bots.sh

CONTAINERS=(chrome1 chrome2 chrome3 chrome4 chrome5 chrome6 chrome7 chrome8 chrome9)

echo "╔════════════════════════════════════════════════════════════╗"
echo "║            BOT STATUS CHECK                                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

for container in "${CONTAINERS[@]}"; do
    echo "🤖 $container:"
    
    # Check if container running
    if ! docker ps --format "{{.Names}}" | grep -q "^$container$"; then
        echo "   ❌ Container not running"
        continue
    fi
    
    # Check if bot process active
    bot_pid=$(docker exec "$container" pgrep -f bot.py 2>/dev/null)
    if [ -z "$bot_pid" ]; then
        echo "   ⚠️  Bot process not running"
    else
        echo "   ✅ Bot running (PID: $bot_pid)"
        
        # Show last 3 lines of log
        echo "   📜 Last log lines:"
        docker exec "$container" tail -n 3 /tmp/bot.log 2>/dev/null | sed 's/^/      /'
    fi
    
    echo ""
done

echo "📊 Remote Control UI: https://test.nuts4poker.com:8080"
echo "🔍 API Status: curl -s https://test.nuts4poker.com:8080/api/health -k | jq ."
```

---

## 7. VERIFICATION & TESTING

### 7.1 Pre-Launch Checklist

**Before deploying bots:**
- [ ] Remote Control UI is accessible: `https://test.nuts4poker.com:8080`
- [ ] Flask backend is running on server
- [ ] n4p.js is served at: `https://test.nuts4poker.com:8080/n4p.js`
- [ ] All 9 containers are running: `docker ps`
- [ ] Network connectivity from containers to server
- [ ] Poker site is accessible: `https://www.pokerbet.co.za`
- [ ] Target table exists and has open seats
- [ ] Bot credentials are valid (9 unique accounts)

### 7.2 Post-Launch Verification

**After bots launch:**
1. **Check logs (1 minute):**
   ```bash
   docker exec chrome1 tail -f /tmp/bot.log
   # Look for: "[OK] Seated!" and "[OK] n4p.js injected"
   ```

2. **Verify seating (2 minutes):**
   ```bash
   # All bots should show "selfPlayer detected" in logs
   ```

3. **Check Remote Control UI (3 minutes):**
   - Open: `https://test.nuts4poker.com:8080`
   - Should see 9 seats with player names
   - Green dots on occupied seats
   - Hole cards visible when hands start

4. **Test snapshot reception (5 minutes):**
   ```bash
   curl -s https://test.nuts4poker.com:8080/api/table/latest -k | jq '.table.seats | map(.name)'
   # Should show array of 9 player names
   ```

5. **Test command execution (manual):**
   - Click CALL button on any seat in UI
   - Watch bot logs for action execution
   - Verify command log shows "OK" status

### 7.3 Success Criteria

**✅ System Fully Operational When:**
- All 9 bots logged in and seated at target table
- Remote Control UI shows all 9 seats with names
- Hole cards visible for all bots
- Snapshots updating every 2 seconds (check timestamps)
- Commands sent from UI execute in browsers
- No errors in bot logs for 5+ minutes

### 7.4 Troubleshooting Quick Reference

| Problem | Quick Fix |
|---------|-----------|
| **Bot stuck at login** | Check credentials, ensure no CAPTCHA |
| **Can't find table** | Verify table name matches exactly (case-sensitive) |
| **Buy-in fails** | Check account balance, may need deposit |
| **n4p.js not injecting** | Verify URL accessibility, check CORS |
| **No snapshots in UI** | Check API endpoint, verify n4p.js executing |
| **Commands not executing** | Check token auth, verify n4p.js polling |
| **Bot disconnects** | Check network, may need reconnect logic |

---

## SUMMARY

**This document provides:**
1. ✅ Complete 19-step navigation path from container start to seated
2. ✅ Synchronization mode of operation (polling, snapshots, commands)
3. ✅ Multi-bot coordination for 9-seat table control
4. ✅ Failure points and recovery procedures
5. ✅ Deployment commands for single and parallel bot launches
6. ✅ Verification and testing procedures

**Next Steps:**
1. Review this document
2. Test single-bot deployment first (chrome1 → Belgrade)
3. Verify synchronization (UI shows seat 0 with cards)
4. Deploy remaining 8 bots with stagger
5. Test remote control commands
6. Monitor for 1 hour to ensure stability

**Total Time:** ~5 minutes per bot (staggered) = 45 minutes for full 9-bot deployment

**Ready for Production:** YES (with monitoring for first 24 hours)
