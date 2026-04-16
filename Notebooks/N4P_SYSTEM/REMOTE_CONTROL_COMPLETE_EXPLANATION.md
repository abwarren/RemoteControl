# Remote Control - Complete Explanation
**ASCII UI, Data Flow, DOM Selectors, and Control API**

**Date:** 2026-04-06

---

## 1. WHAT "UI FULL ASCII" MEANS

**ASCII = Text-based diagram of the user interface**

This is what YOU (the user) see when you open the remote control in your web browser:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  🎮 N4P // REMOTE TABLE CONTROL                              🔴 [TEST]    │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
     ▲
     └─ Header bar (always at top)


┌────────────────────────────────────────────────────────────────────────────┐
│  📜 RAW HAND LOG                                    [📋 COPY]  [🗑️ CLEAR] │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ PokerStars Hand #123456789: Hold'em No Limit ($0.50/$1.00)          │ │
│  │ Table 'Belgrade' 9-max Seat #3 is the button                         │ │
│  │ Seat 1: Player1 ($200.00 in chips)                                   │ │
│  │ *** HOLE CARDS ***                                                   │ │
│  │ Dealt to Player1 [Ah Kh Qh Jh]                                       │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
     ▲
     └─ Hand history log (PokerStars format)


┌───────────────────────────────────────────────┬────────────────────────────┐
│                                               │  🎯 ADVANCED ACTIONS       │
│  🃏 BOARD DISPLAY                             │                            │
│  ┌─────────────────────────────────────────┐ │  ┌──────────────────────┐ │
│  │   💰 POT: ZAR 150.00                    │ │  │    MIN ALL           │ │
│  │   🌊 FLOP                               │ │  └──────────────────────┘ │
│  │   [A♥] [K♥] [Q♥] [--] [--]             │ │  ┌──────────────────────┐ │
│  └─────────────────────────────────────────┘ │  │    MAX ALL           │ │
│     ▲                                         │  └──────────────────────┘ │
│     └─ Community cards + pot                  │  ┌──────────────────────┐ │
│                                               │  │   BET / EXECUTE      │ │
│  👥 9 PLAYERS (3×3 grid)                     │  └──────────────────────┘ │
│                                               │                            │
│  ┌─────────┬─────────┬─────────┐             │  ☐ ARM CASHOUT ALL         │
│  │ SEAT 0  │ SEAT 1  │ SEAT 2  │             │                            │
│  │ Player1 │ Player2 │ Player3 │             │  ┌──────────────────────┐ │
│  │ 🟢 LIVE │ 🟢 LIVE │ 🔴 IDLE │             │  │   CASHOUT ALL  🚨   │ │
│  │ $200.00 │ $150.00 │ $300.00 │             │  └──────────────────────┘ │
│  │ [🎯 D]  │         │         │             │                            │
│  │ [A♥][K♥]│ [--][--]│ [--][--]│             │  📋 COMMAND LOG            │
│  │ [Q♥][J♥]│         │         │             │  ┌──────────────────────┐ │
│  │         │         │         │             │  │ 12:34 S0 call  PEND  │ │
│  │ ☐CF ☐CC │ ☐CF ☐CC │ ☐CF ☐CC │             │  │ 12:33 S1 check   OK  │ │
│  │         │         │         │             │  │ 12:32 S2 fold    OK  │ │
│  │[FOLD]   │[FOLD]   │[FOLD]   │             │  └──────────────────────┘ │
│  │[CHECK]  │[CHECK]  │[CHECK]  │             │      ▲                     │
│  │[CALL]   │[CALL]   │[CALL]   │             │      └─ Last 20 commands   │
│  │[MIN]    │[MIN]    │[MIN]    │             │                            │
│  │[MAX]    │[MAX]    │[MAX]    │             └────────────────────────────┘
│  │[BET]    │[BET]    │[BET]    │                   ▲
│  │[ARM]    │[ARM]    │[ARM]    │                   └─ Right sidebar (30% width)
│  │[CASH]   │[CASH]   │[CASH]   │
│  └─────────┴─────────┴─────────┘
│     ▲
│     └─ Each seat has 8 buttons + 2 checkboxes
│
│  ┌─────────┬─────────┬─────────┐
│  │ SEAT 3  │ SEAT 4  │ SEAT 5  │
│  │ Empty   │ Player5 │ Player6 │
│  │ ⚪ IDLE │ 🟢 LIVE │ 🟢 LIVE │
│  │ $0.00   │ $100.00 │ $250.00 │
│  └─────────┴─────────┴─────────┘
│
│  ┌─────────┬─────────┬─────────┐
│  │ SEAT 6  │ SEAT 7  │ SEAT 8  │
│  │ Player7 │ Empty   │ Player9 │
│  │ 🟢 LIVE │ ⚪ IDLE │ 🟢 LIVE │
│  │ $180.00 │ $0.00   │ $220.00 │
│  └─────────┴─────────┴─────────┘
│     ▲
│     └─ Total 9 seats in 3×3 grid
│
└───────────────────────────────────────────────┘
```

**This ASCII diagram shows:**
- Layout structure (what goes where)
- Component hierarchy (nested boxes)
- Interactive elements (buttons, checkboxes)
- Data displays (pot, cards, stacks)

**It's NOT the actual code** - it's a visual representation to help you understand the layout.

---

## 2. DATA FLOW: POKER SITE DOM → FLASK

### 2.1 The Complete Journey

```
┌────────────────────────────────────────────────────────────────────┐
│  STEP 1: POKER SITE DOM (PokerBet.co.za)                          │
│  Browser renders poker client in iframe                           │
└────────────────────────────────────────────────────────────────────┘
                          │
                          │ n4p.js reads DOM elements
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│  STEP 2: N4P.JS (INJECTED SCRIPT)                                 │
│  JavaScript code running INSIDE poker client                      │
│  - Finds card elements using CSS selectors                        │
│  - Extracts text content (card ranks/suits)                       │
│  - Gets player info (name, stack, position)                       │
│  - Packages into JSON snapshot                                    │
└────────────────────────────────────────────────────────────────────┘
                          │
                          │ Every 2 seconds
                          │ POST /api/snapshot
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│  STEP 3: FLASK BACKEND (app.py on server)                         │
│  Python Flask application                                         │
│  - Receives JSON snapshot via HTTP POST                           │
│  - Validates data structure                                       │
│  - Stores in in-memory dict (_snapshot_store)                    │
│  - Merges with other bot snapshots                               │
└────────────────────────────────────────────────────────────────────┘
                          │
                          │ Every 1 second
                          │ GET /api/table/latest
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│  STEP 4: REMOTE CONTROL UI (Your Browser)                         │
│  HTML + JavaScript frontend                                       │
│  - Polls Flask API every 1 second                                 │
│  - Gets merged table data (all 9 seats)                          │
│  - Renders seat cards, board, pot                                │
│  - Shows player names, stacks, cards                             │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 Example: Getting Player Cards

**Step 1: Poker Site DOM Structure**
```html
<!-- This is what exists in PokerBet.co.za poker client -->
<div class="player self-player">
  <div class="player-name">Player1</div>
  <div class="player-stack">$200.00</div>
  <div class="player-cards">
    <div class="card icon-layer2-h-a_p-c-d"></div>  <!-- Ace of Hearts -->
    <div class="card icon-layer2-h-k_p-c-d"></div>  <!-- King of Hearts -->
    <div class="card icon-layer2-d-q_p-c-d"></div>  <!-- Queen of Diamonds -->
    <div class="card icon-layer2-c-j_p-c-d"></div>  <!-- Jack of Clubs -->
  </div>
</div>
```

**Step 2: n4p.js Extracts Data**
```javascript
// In n4p.js (running inside poker client)

function extractCards() {
  // Find all card elements
  let cardElements = document.querySelectorAll('[class*="icon-layer2"]');
  
  let cards = [];
  
  for (let elem of cardElements) {
    let className = elem.className;
    
    // Parse pattern: icon-layer2-{suit}-{rank}_p-c-d
    let match = className.match(/icon-layer2-([hdcs])-([akqjt2-9])/);
    
    if (match) {
      let suit = match[1];  // h, d, c, s
      let rank = match[2];  // a, k, q, j, t, 2-9
      
      // Convert to standard format
      let card = rank.toUpperCase() + suit;  // "Ah", "Kh", "Qd", "Jc"
      cards.push(card);
    }
  }
  
  return cards;  // ["Ah", "Kh", "Qd", "Jc"]
}

function extractPlayerInfo() {
  // Get player name
  let nameElem = document.querySelector('.player-name');
  let name = nameElem ? nameElem.textContent : null;
  
  // Get stack amount
  let stackElem = document.querySelector('.player-stack');
  let stackText = stackElem ? stackElem.textContent : "$0.00";
  let stack = parseFloat(stackText.replace(/[$,]/g, ''));
  
  return { name, stack };
}

function sendSnapshot() {
  let cards = extractCards();
  let player = extractPlayerInfo();
  
  let snapshot = {
    table_id: getCurrentTableId(),  // e.g., "tbl_2143037"
    seat_index: getSeatIndex(),      // e.g., 3
    name: player.name,               // "Player1"
    stack_zar: player.stack,         // 200.00
    hole_cards: cards.slice(0, 4),   // First 4 = hole cards
    board_cards: cards.slice(4),     // Rest = board cards
    status: "playing",
    timestamp: Math.floor(Date.now() / 1000)
  };
  
  // Send to Flask backend
  fetch('https://test.nuts4poker.com:8080/api/snapshot', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(snapshot)
  });
}

// Run every 2 seconds
setInterval(sendSnapshot, 2000);
```

**Step 3: Flask Receives and Stores**
```python
# In /opt/plo-equity/app.py

_snapshot_store = {}  # In-memory storage

@app.route('/api/snapshot', methods=['POST'])
def receive_snapshot():
    data = request.get_json()
    
    # Validate required fields
    required = ['table_id', 'seat_index', 'timestamp']
    for field in required:
        if field not in data:
            return jsonify({'ok': False, 'error': f'Missing {field}'}), 400
    
    # Store with key: "table_id:seat_index"
    key = f"{data['table_id']}:{data['seat_index']}"
    _snapshot_store[key] = {
        'seat_index': data['seat_index'],
        'name': data.get('name'),
        'stack_zar': data.get('stack_zar', 0),
        'hole_cards': data.get('hole_cards', []),
        'board_cards': data.get('board_cards', []),
        'status': data.get('status', 'idle'),
        'timestamp': data['timestamp']
    }
    
    print(f"[SNAPSHOT] {key} -> {data['name']} (${data.get('stack_zar', 0)})")
    
    return jsonify({'ok': True})
```

**Storage Example:**
```python
_snapshot_store = {
  "tbl_2143037:0": {
    "seat_index": 0,
    "name": "Player1",
    "stack_zar": 200.00,
    "hole_cards": ["Ah", "Kh", "Qd", "Jc"],
    "board_cards": ["As", "Ks", "Qh"],
    "status": "playing",
    "timestamp": 1775432100
  },
  "tbl_2143037:1": {
    "seat_index": 1,
    "name": "Player2",
    "stack_zar": 150.00,
    "hole_cards": ["6c", "Kh", "9d", "Th"],
    "board_cards": ["As", "Ks", "Qh"],
    "status": "playing",
    "timestamp": 1775432101
  }
}
```

**Step 4: Remote Control UI Gets Data**
```javascript
// In static/index.html

function fetchTableData() {
  fetch('/api/table/latest')
    .then(r => r.json())
    .then(data => {
      if (data.ok && data.table) {
        renderTable(data.table);
      }
    });
}

// Poll every 1 second
setInterval(fetchTableData, 1000);
```

**Flask Returns Merged Data:**
```python
@app.route('/api/table/latest', methods=['GET'])
def get_latest_table():
    # Merge all snapshots for this table
    table = _merge_table('tbl_2143037')
    return jsonify({'ok': True, 'table': table})

def _merge_table(table_id):
    seats = []
    for i in range(9):
        key = f"{table_id}:{i}"
        snapshot = _snapshot_store.get(key)
        
        if snapshot:
            seats.append(snapshot)
        else:
            seats.append({
                'seat_index': i,
                'name': None,
                'stack_zar': 0,
                'hole_cards': [],
                'status': 'empty'
            })
    
    return {
        'table_id': table_id,
        'seats': seats,
        'board': seats[0]['board_cards'] if seats[0] else [],
        'pot_zar': 150.00  # Calculate from bets
    }
```

**UI Renders:**
```javascript
function renderTable(table) {
  let html = '';
  
  for (let seat of table.seats) {
    html += `
      <div class="seat-card">
        <div class="seat-header">
          <span>SEAT ${seat.seat_index}</span>
          <span class="status-dot ${seat.name ? 'live' : 'offline'}"></span>
        </div>
        <div class="seat-info">
          <div>${seat.name || 'Empty'}</div>
          <div>ZAR ${seat.stack_zar.toFixed(2)}</div>
          <div class="hole-cards">
            ${seat.hole_cards.map(card => formatCard(card)).join('')}
          </div>
        </div>
        <div class="action-buttons">
          <button onclick="sendCommand('${table.table_id}', ${seat.seat_index}, 'fold')">FOLD</button>
          <button onclick="sendCommand('${table.table_id}', ${seat.seat_index}, 'check')">CHECK</button>
          <button onclick="sendCommand('${table.table_id}', ${seat.seat_index}, 'call')">CALL</button>
          <!-- ... more buttons ... -->
        </div>
      </div>
    `;
  }
  
  document.getElementById('seats-container').innerHTML = html;
}
```

---

## 3. DOM SELECTORS USED BY N4P.JS

### 3.1 Card Extraction Selectors

**Pattern:** `icon-layer2-{suit}-{rank}_p-c-d`

**Suits:**
- `h` = Hearts (♥)
- `d` = Diamonds (♦)
- `c` = Clubs (♣)
- `s` = Spades (♠)

**Ranks:**
- `a` = Ace
- `k` = King
- `q` = Queen
- `j` = Jack
- `t` = Ten
- `2-9` = Number cards

**CSS Selector:**
```javascript
document.querySelectorAll('[class*="icon-layer2"]')
```

**Example DOM:**
```html
<div class="card icon-layer2-h-a_p-c-d"></div>  <!-- Ace of Hearts -->
<div class="card icon-layer2-s-k_p-c-d"></div>  <!-- King of Spades -->
<div class="card icon-layer2-d-q_p-c-d"></div>  <!-- Queen of Diamonds -->
<div class="card icon-layer2-c-j_p-c-d"></div>  <!-- Jack of Clubs -->
```

**Extraction Logic:**
```javascript
let cardElements = document.querySelectorAll('[class*="icon-layer2"]');

for (let elem of cardElements) {
  let className = elem.className;  // "card icon-layer2-h-a_p-c-d"
  
  // Extract suit and rank
  let match = className.match(/icon-layer2-([hdcs])-([akqjt2-9])/);
  
  if (match) {
    let suit = match[1];  // "h"
    let rank = match[2];  // "a"
    
    let card = rank.toUpperCase() + suit;  // "Ah"
    console.log('Found card:', card);
  }
}
```

### 3.2 Player Info Selectors

**Player Name:**
```javascript
let nameElem = document.querySelector('.player-name');
let name = nameElem ? nameElem.textContent.trim() : null;
```

**Player Stack:**
```javascript
let stackElem = document.querySelector('.player-stack');
let stackText = stackElem ? stackElem.textContent : "$0.00";
let stack = parseFloat(stackText.replace(/[$,]/g, ''));
```

**Seat Index:**
```javascript
let seatElem = document.querySelector('.self-player');
let seatAttr = seatElem ? seatElem.getAttribute('data-seat') : null;
let seatIndex = parseInt(seatAttr) || 0;
```

**Dealer Button:**
```javascript
let dealerElem = document.querySelector('.dealer-marker');
let isDealer = dealerElem !== null;
```

### 3.3 Table Info Selectors

**Pot Amount:**
```javascript
let potElem = document.querySelector('.pot-display');
let potText = potElem ? potElem.textContent : "$0.00";
let pot = parseFloat(potText.replace(/[^0-9.]/g, ''));
```

**Street (Flop/Turn/River):**
```javascript
let streetElem = document.querySelector('.street-indicator');
let street = streetElem ? streetElem.textContent.toLowerCase() : 'preflop';
```

**Community Cards:**
```javascript
let boardElements = document.querySelectorAll('.board-card [class*="icon-layer2"]');
let boardCards = [];

for (let elem of boardElements) {
  let card = extractCardFromClass(elem.className);
  boardCards.push(card);
}
```

---

## 4. BUTTONS ON REMOTE CONTROL UI

### 4.1 Per-Seat Buttons (in each seat card)

**8 Action Buttons:**

1. **FOLD** (Red)
   - CSS: `.btn-fold`
   - onClick: `sendCommand(tableId, seatIndex, 'fold')`
   - Sends: `POST /api/commands/queue` with `command_type: "fold"`

2. **CHECK** (Green)
   - CSS: `.btn-check`
   - onClick: `sendCommand(tableId, seatIndex, 'check')`
   - Sends: `POST /api/commands/queue` with `command_type: "check"`

3. **CALL** (Blue)
   - CSS: `.btn-call`
   - onClick: `sendCommand(tableId, seatIndex, 'call')`
   - Sends: `POST /api/commands/queue` with `command_type: "call"`

4. **MIN** (Gray)
   - CSS: `.btn-min`
   - onClick: `sendCommand(tableId, seatIndex, 'bet_min')`
   - Sends: `POST /api/commands/queue` with `command_type: "bet_min"`

5. **MAX** (Orange)
   - CSS: `.btn-max`
   - onClick: `sendCommand(tableId, seatIndex, 'raise_max')`
   - Sends: `POST /api/commands/queue` with `command_type: "raise_max"`

6. **BET** (Dark Orange)
   - CSS: `.btn-bet`
   - onClick: Opens slider, then `sendCommand(tableId, seatIndex, 'bet_custom', {value: amount})`
   - Sends: `POST /api/commands/queue` with `command_type: "bet_custom"`, `value: 50.00`

7. **ARM** (Purple)
   - CSS: `.btn-arm`
   - onClick: `sendCommand(tableId, seatIndex, 'pre_action_arm')`
   - Sends: `POST /api/commands/queue` with `command_type: "pre_action_arm"`

8. **CASH** (Yellow)
   - CSS: `.btn-cashout`
   - onClick: `sendCommand(tableId, seatIndex, 'cashout')`
   - Sends: `POST /api/commands/queue` with `command_type: "cashout"`

**2 Pre-Action Checkboxes:**

9. **Check/Fold Checkbox**
   - HTML: `<input type="checkbox" id="cf-0">`
   - onChange: `togglePreAction(tableId, seatIndex, 'check_fold', checked)`
   - Sends: `POST /api/commands/queue` with `command_type: "pre_action_check_fold"`

10. **Check/Call Checkbox**
    - HTML: `<input type="checkbox" id="cc-0">`
    - onChange: `togglePreAction(tableId, seatIndex, 'check_call', checked)`
    - Sends: `POST /api/commands/queue` with `command_type: "pre_action_check_call"`

### 4.2 Global Action Buttons (in Advanced Actions panel)

11. **MIN ALL** (Blue)
    - CSS: `.btn-global-min`
    - onClick: `setAllMin(tableId)`
    - Sends: `POST /api/commands/queue-batch` with `command_type: "bet_min"` for all active seats

12. **MAX ALL** (Blue)
    - CSS: `.btn-global-max`
    - onClick: `setAllMax(tableId)`
    - Sends: `POST /api/commands/queue-batch` with `command_type: "raise_max"` for all active seats

13. **BET / EXECUTE** (Orange)
    - CSS: `.btn-execute-all`
    - onClick: `executePendingBets(tableId)`
    - Sends: `POST /api/commands/execute-all`

14. **CASHOUT ALL** (Red)
    - CSS: `.btn-cashout-all`
    - onClick: `cashoutAll(tableId)` (requires ARM checkbox)
    - Sends: `POST /api/commands/cashout-all`

15. **CLEAR ALL COMMANDS** (Gray)
    - CSS: `.btn-clear-all`
    - onClick: `clearAllCommands(tableId)`
    - Sends: `POST /api/commands/clear-all`

**ARM CASHOUT ALL Checkbox:**
16. **ARM CASHOUT ALL**
    - HTML: `<input type="checkbox" id="arm-cashout-all">`
    - Purpose: Enable/disable CASHOUT ALL button (safety)

---

## 5. API THAT CONTROLS BOTS

### 5.1 Command Queue API

**YES, there is an API that controls the bots remotely.**

**API Base URL:** `https://test.nuts4poker.com:8080/api/`

**Core Endpoints:**

| Endpoint | Method | Who Calls | Purpose |
|----------|--------|-----------|---------|
| `/api/commands/queue` | POST | Remote Control UI | Queue command for a bot |
| `/api/commands/pending` | GET | n4p.js (bots) | Poll for commands to execute |
| `/api/commands/ack` | POST | n4p.js (bots) | Acknowledge command completed |
| `/api/snapshot` | POST | n4p.js (bots) | Send table state to backend |
| `/api/table/latest` | GET | Remote Control UI | Get current table state |

### 5.2 Command Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  STEP 1: USER CLICKS BUTTON                                      │
│  User clicks CALL on Seat 3 in Remote Control UI                │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 2: UI SENDS COMMAND                                        │
│  POST /api/commands/queue                                        │
│  {                                                               │
│    "table_id": "tbl_2143037",                                    │
│    "seat_index": 3,                                              │
│    "command_type": "call"                                        │
│  }                                                               │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 3: FLASK BACKEND QUEUES COMMAND                           │
│  _command_queue["<seat_token>"] = {                              │
│    "id": "abc123",                                               │
│    "type": "call",                                               │
│    "status": "pending"                                           │
│  }                                                               │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 4: N4P.JS POLLS FOR COMMANDS (Every 1 second)             │
│  GET /api/commands/pending?token=<seat_token>                    │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 5: BACKEND RETURNS COMMAND                                │
│  {                                                               │
│    "ok": true,                                                   │
│    "command": {                                                  │
│      "id": "abc123",                                             │
│      "type": "call"                                              │
│    }                                                             │
│  }                                                               │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 6: N4P.JS EXECUTES COMMAND IN BROWSER                     │
│  let callBtn = document.querySelector('.action-call');          │
│  callBtn.click();  ← Actually clicks button in poker client    │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 7: N4P.JS ACKNOWLEDGES COMPLETION                          │
│  POST /api/commands/ack                                          │
│  {                                                               │
│    "token": "<seat_token>",                                      │
│    "command_id": "abc123"                                        │
│  }                                                               │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 8: BACKEND CLEARS COMMAND FROM QUEUE                       │
│  del _command_queue["<seat_token>"]                              │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 9: UI POLLS AND SEES COMMAND COMPLETE                      │
│  GET /api/table/latest                                           │
│  Seat 3: pending_cmd = null (no longer pending)                 │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Complete API Reference

#### POST /api/commands/queue
**Purpose:** Queue a command for a specific bot to execute

**Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 3,
  "command_type": "call",
  "value": null  // Optional: for bet amounts
}
```

**Response:**
```json
{
  "ok": true,
  "command_id": "abc123"
}
```

**Command Types:**
- `fold` - Fold hand
- `check` - Check
- `call` - Call bet
- `bet_min` - Bet minimum
- `raise_max` - Raise maximum
- `bet_custom` - Custom bet (requires `value` field)
- `cashout` - Leave table
- `pre_action_check_fold` - Set check/fold pre-action
- `pre_action_check_call` - Set check/call pre-action
- `clear_preaction` - Clear pre-action

---

#### GET /api/commands/pending?token=<seat_token>
**Purpose:** Bot polls for commands to execute

**Request:**
```http
GET /api/commands/pending?token=a7f8e4c2b9d1e6f3
```

**Response (when command exists):**
```json
{
  "ok": true,
  "command": {
    "id": "abc123",
    "type": "call",
    "value": null
  }
}
```

**Response (no command):**
```json
{
  "ok": true,
  "command": null
}
```

---

#### POST /api/commands/ack
**Purpose:** Bot acknowledges command was executed

**Request:**
```json
{
  "token": "a7f8e4c2b9d1e6f3",
  "command_id": "abc123"
}
```

**Response:**
```json
{
  "ok": true
}
```

---

#### POST /api/snapshot
**Purpose:** Bot sends current table state

**Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 3,
  "name": "Player1",
  "stack_zar": 200.00,
  "hole_cards": ["Ah", "Kh", "Qd", "Jc"],
  "board_cards": ["As", "Ks", "Qh"],
  "pot_zar": 150.00,
  "status": "playing",
  "is_dealer": false,
  "timestamp": 1775432100
}
```

**Response:**
```json
{
  "ok": true
}
```

---

#### GET /api/table/latest
**Purpose:** Remote Control UI gets current table state

**Response:**
```json
{
  "ok": true,
  "table": {
    "table_id": "tbl_2143037",
    "seats": [
      {
        "seat_index": 0,
        "name": "Player1",
        "stack_zar": 200.00,
        "hole_cards": ["Ah", "Kh", "Qd", "Jc"],
        "board_cards": ["As", "Ks", "Qh"],
        "status": "playing",
        "is_hero": true,
        "is_dealer": false,
        "pending_cmd": null,
        "last_seen_ago": 2.5
      }
      // ... 8 more seats
    ],
    "board": ["As", "Ks", "Qh"],
    "pot_zar": 150.00,
    "street": "flop",
    "last_updated": 1775432100
  }
}
```

---

## 6. SUMMARY DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│                        COMPLETE SYSTEM                              │
└─────────────────────────────────────────────────────────────────────┘

┌────────────────────┐         ┌────────────────────┐
│  POKER SITE DOM    │         │  REMOTE CONTROL UI │
│  (PokerBet.co.za)  │         │  (Your Browser)    │
│                    │         │                    │
│  Card classes:     │         │  Buttons:          │
│  icon-layer2-h-a   │         │  [FOLD][CHECK]     │
│  icon-layer2-s-k   │         │  [CALL][MIN]       │
│  .player-name      │         │  [MAX][BET]        │
│  .player-stack     │         │  [ARM][CASH]       │
│  .pot-display      │         │                    │
└──────┬─────────────┘         └──────┬─────────────┘
       │                              │
       │ n4p.js reads                 │ User clicks
       │                              │
       ▼                              ▼
┌────────────────────┐         ┌────────────────────┐
│     N4P.JS         │         │  JAVASCRIPT        │
│  (In poker client) │         │  (In remote UI)    │
│                    │         │                    │
│  extractCards()    │         │  sendCommand()     │
│  sendSnapshot()    │         │  fetchTableData()  │
│  pollCommands()    │         │  renderTable()     │
│  executeCommand()  │         │                    │
└──────┬─────────────┘         └──────┬─────────────┘
       │                              │
       │ POST /api/snapshot           │ POST /api/commands/queue
       │ GET /api/commands/pending    │ GET /api/table/latest
       │                              │
       └─────────────┬────────────────┘
                     │
                     ▼
            ┌────────────────────┐
            │  FLASK BACKEND     │
            │  (app.py)          │
            │                    │
            │  _snapshot_store   │
            │  _command_queue    │
            │  _merged_tables    │
            │                    │
            │  Routes:           │
            │  /api/snapshot     │
            │  /api/commands/*   │
            │  /api/table/latest │
            └────────────────────┘
```

**Key Points:**
1. n4p.js reads poker DOM using selectors like `[class*="icon-layer2"]`
2. Data is delivered to Flask via `POST /api/snapshot`
3. Remote Control has 95 interactive elements (buttons + checkboxes)
4. n4p.js responds to commands queued via API
5. Yes, there is an API (`/api/commands/`) that controls bots remotely
