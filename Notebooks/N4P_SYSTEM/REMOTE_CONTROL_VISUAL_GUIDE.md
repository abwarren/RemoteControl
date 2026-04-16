# Remote Control UI - Visual Guide & Backend Integration
**What It Is, How It Works, Why It Exists**

**Date:** 2026-04-06

---

## THE PURPOSE

**Problem:** You have 9 poker players (bots) running in Chrome containers, all playing at the same table. You need to control all of them from one place.

**Solution:** A web dashboard that lets you see all 9 players at once and send commands (FOLD, CALL, RAISE, etc.) to any seat remotely.

**Why:** Manual switching between 9 Chrome windows is impossible during live play. This dashboard gives you "god mode" control over the entire table.

---

## THE UI (What You See)

### Full Screen View

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  🎮 N4P // REMOTE TABLE CONTROL                              🔴 [TEST]      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  📜 RAW HAND LOG                                    [📋 COPY]  [🗑️ CLEAR]   │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PokerStars Hand #123456789: Hold'em No Limit ($0.50/$1.00)            │ │
│  │ Table 'Belgrade' 9-max Seat #3 is the button                           │ │
│  │ Seat 1: Player1 ($200.00 in chips)                                     │ │
│  │ Seat 2: Player2 ($150.00 in chips)                                     │ │
│  │ Player1: posts small blind $0.50                                       │ │
│  │ Player2: posts big blind $1.00                                         │ │
│  │ *** HOLE CARDS ***                                                     │ │
│  │ Dealt to Player1 [Ah Kh Qh Jh]                                         │ │
│  │ Player3: folds                                                         │ │
│  │ Player1: raises $10 to $15                                             │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────┬──────────────────────────────┐
│                                               │  🎯 ADVANCED ACTIONS         │
│  🃏 BOARD                                     │                              │
│  ┌─────────────────────────────────────────┐ │  ┌────────────────────────┐ │
│  │   💰 POT: ZAR 150.00                    │ │  │    MIN ALL             │ │
│  │   🌊 FLOP                               │ │  └────────────────────────┘ │
│  │   [A♥] [K♥] [Q♥] [--] [--]             │ │  ┌────────────────────────┐ │
│  └─────────────────────────────────────────┘ │  │    MAX ALL             │ │
│                                               │  └────────────────────────┘ │
│  👥 PLAYERS (9 SEATS)                        │  ┌────────────────────────┐ │
│                                               │  │   BET / EXECUTE        │ │
│  ┌─────────┬─────────┬─────────┐             │  └────────────────────────┘ │
│  │ SEAT 0  │ SEAT 1  │ SEAT 2  │             │                              │
│  │ Player1 │ Player2 │ Player3 │             │  ☐ ARM CASHOUT ALL           │
│  │ 🟢 LIVE │ 🟢 LIVE │ 🔴 IDLE │             │                              │
│  │ $200.00 │ $150.00 │ $300.00 │             │  ┌────────────────────────┐ │
│  │ [🎯 D]  │         │         │             │  │   CASHOUT ALL  🚨     │ │
│  │ [A♥][K♥]│ [--][--]│ [--][--]│             │  └────────────────────────┘ │
│  │ [Q♥][J♥]│         │         │             │                              │
│  │         │         │         │             │  📋 COMMAND LOG              │
│  │ ☐CF ☐CC │ ☐CF ☐CC │ ☐CF ☐CC │             │  ┌────────────────────────┐│
│  │         │         │         │             │  │ 12:34 S0 call  PENDING ││
│  │[FOLD]   │[FOLD]   │[FOLD]   │             │  │ 12:33 S1 check     OK  ││
│  │[CHECK]  │[CHECK]  │[CHECK]  │             │  │ 12:32 S2 fold      OK  ││
│  │[CALL]   │[CALL]   │[CALL]   │             │  │ 12:31 S0 raise_max OK  ││
│  │[MIN]    │[MIN]    │[MIN]    │             │  │ 12:30 S4 call  PENDING ││
│  │[MAX]    │[MAX]    │[MAX]    │             │  └────────────────────────┘│
│  │[BET]    │[BET]    │[BET]    │             │                              │
│  │[ARM]    │[ARM]    │[ARM]    │             └──────────────────────────────┘
│  │[CASH]   │[CASH]   │[CASH]   │
│  └─────────┴─────────┴─────────┘
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
│
└───────────────────────────────────────────────┘
```

---

## THE COMPONENTS (What Each Part Does)

### 1. HEADER
```
🎮 N4P // REMOTE TABLE CONTROL                              🔴 [TEST]
```

**Purpose:** Branding + environment indicator  
**[TEST] badge:** Red = test environment, Green = production  
**Always visible:** Stays at top even when scrolling

---

### 2. HAND LOG (Top Section)
```
📜 RAW HAND LOG                                    [📋 COPY]  [🗑️ CLEAR]
┌────────────────────────────────────────────────────────────────────┐
│ PokerStars Hand #123456789: Hold'em No Limit ($0.50/$1.00)        │
│ Table 'Belgrade' 9-max Seat #3 is the button                       │
│ Seat 1: Player1 ($200.00 in chips)                                 │
│ *** HOLE CARDS ***                                                 │
│ Dealt to Player1 [Ah Kh Qh Jh]                                     │
│ Player1: raises $10 to $15                                         │
└────────────────────────────────────────────────────────────────────┘
```

**Purpose:** Shows raw hand history in PokerStars format  
**Updates:** Every 2 seconds (polls `/api/hands/recent`)  
**COPY button:** Copies all text to clipboard for later analysis  
**CLEAR button:** Wipes entire hand history  

**Why It Exists:** You need to save hand histories for:
- Post-game analysis
- Bug reports
- Training AI models
- Legal/audit trail

---

### 3. BOARD DISPLAY (Center Top)
```
┌─────────────────────────────────────────┐
│   💰 POT: ZAR 150.00                    │
│   🌊 FLOP                               │
│   [A♥] [K♥] [Q♥] [--] [--]             │
└─────────────────────────────────────────┘
```

**Purpose:** Shows current pot size and community cards  
**Updates:** Every 1 second (polls `/api/table/latest`)  
**Card Colors:**
- ♥ Hearts = RED
- ♦ Diamonds = BLUE
- ♣ Clubs = GREEN
- ♠ Spades = BLACK

**Why 4 Colors:** Easier to see suits at a glance (reduces misreads)

**Street Indicators:**
- PREFLOP (no cards)
- FLOP (3 cards)
- TURN (4 cards)
- RIVER (5 cards)

---

### 4. SEAT CARDS (Main Grid - 9 Seats)

#### 4a. INDIVIDUAL SEAT CARD
```
┌─────────────────────────┐
│ SEAT 0  🟢              │  ← Green = Live, Gray = Empty
│ Player1         [🎯 D]  │  ← [D] = Dealer button
├─────────────────────────┤
│ ZAR 200.00              │  ← Current stack
│ Status: ACTIVE          │  ← EMPTY/IDLE/ACTIVE/PENDING
│ [A♥][K♥][Q♥][J♥]        │  ← Hole cards (PLO = 4 cards)
│ ⏳ raise_max            │  ← Pending command badge
├─────────────────────────┤
│ ☐ Check/Fold            │  ← Pre-action checkboxes
│ ☐ Check/Call            │  ← (mutually exclusive)
├─────────────────────────┤
│ [FOLD]  [CHECK] [CALL]  │  ← Action buttons (3×3 grid)
│ [MIN]   [MAX]   [BET]   │
│ [ARM]   [CASH]          │
└─────────────────────────┘
```

**Purpose:** Each card represents one player at the table

**Status Indicators:**
- 🟢 **GREEN DOT** = Player connected, actively playing
- ⚪ **GRAY DOT** = Seat empty or player idle
- 🔴 **RED BORDER** = Connection lost (snapshot >30s old)
- 🟡 **YELLOW BORDER (blinking)** = It's this player's turn to act

**Hole Cards:**
- Show your cards when you're in a hand
- `[--]` placeholders when cards not visible
- 4 cards for PLO, 2 cards for Hold'em

**Pending Badge:**
- Appears when command is queued
- Shows: ⏳ [command_type]
- Example: "⏳ raise_max" = waiting to raise

---

#### 4b. PRE-ACTION CHECKBOXES
```
☐ Check/Fold
☐ Check/Call
```

**Purpose:** Auto-actions for when it's your turn

**Check/Fold:**
- If no bet: CHECK
- If there's a bet: FOLD

**Check/Call:**
- If no bet: CHECK
- If there's a bet: CALL (any amount)

**Mutually Exclusive:** Checking one unchecks the other

**Disabled When:** 
- Player not active (not in hand)
- Connection lost
- Command already pending

---

#### 4c. ACTION BUTTONS (8 Buttons Per Seat)

```
[FOLD]  [CHECK] [CALL]
[MIN]   [MAX]   [BET]
[ARM]   [CASH]
```

**Button Colors:**
- FOLD = RED (danger)
- CHECK = GREEN (safe)
- CALL = BLUE (neutral)
- MIN = GRAY (minimum bet)
- MAX = ORANGE (maximum raise)
- BET = DARK ORANGE (opens slider for custom amount)
- ARM = PURPLE (pre-arm action)
- CASH = YELLOW (cash out and leave table)

**What Each Button Does:**

| Button | Action | When Available |
|--------|--------|----------------|
| **FOLD** | Fold your hand | Always (on your turn) |
| **CHECK** | Check (no bet) | When no one has bet |
| **CALL** | Call the current bet | When there's a bet to call |
| **MIN** | Bet minimum allowed | When you can bet/raise |
| **MAX** | Raise to maximum (all-in) | When you can bet/raise |
| **BET** | Custom bet amount (opens slider) | When you can bet/raise |
| **ARM** | Pre-arm your next action | Always |
| **CASH** | Cash out and leave table | Always when seated |

**BET Button Slider:**
```
When you click BET:
┌─────────────────────────────────┐
│ BET AMOUNT: ZAR 25.00           │
│ ├──────●───────────────────────┤│
│ Min: 5.00        Max: 200.00   │
│ [CONFIRM] [CANCEL]              │
└─────────────────────────────────┘
```

**Disabled When:**
- Player not active (not your turn)
- Connection lost
- Command already pending

---

### 5. ADVANCED ACTIONS PANEL (Right Sidebar)

```
┌────────────────────────────┐
│  🎯 ADVANCED ACTIONS       │
│                            │
│  ┌──────────────────────┐ │
│  │    MIN ALL           │ │  ← Set MIN bet on ALL active seats
│  └──────────────────────┘ │
│  ┌──────────────────────┐ │
│  │    MAX ALL           │ │  ← Set MAX raise on ALL active seats
│  └──────────────────────┘ │
│  ┌──────────────────────┐ │
│  │   BET / EXECUTE      │ │  ← Execute all pending BET commands
│  └──────────────────────┘ │
│                            │
│  ☐ ARM CASHOUT ALL         │  ← Safety checkbox (must check first)
│                            │
│  ┌──────────────────────┐ │
│  │   CASHOUT ALL  🚨    │ │  ← Emergency: cash out ALL seats
│  └──────────────────────┘ │
│                            │
│  📋 COMMAND LOG            │
│  ┌──────────────────────┐ │
│  │ 12:34 S0 call  PEND  │ │
│  │ 12:33 S1 check   OK  │ │
│  │ 12:32 S2 fold    OK  │ │
│  └──────────────────────┘ │
└────────────────────────────┘
```

**Purpose:** Global controls that affect multiple seats at once

---

#### 5a. MIN ALL Button
```
┌──────────────────────────┐
│    MIN ALL               │
└──────────────────────────┘
```

**What It Does:** Sets MIN bet on ALL active seats at once

**When You'd Use It:** 
- You want all 9 players to bet minimum
- Fast way to build pot without risking much

**What Happens:**
1. Click MIN ALL
2. Confirmation: "Set MIN bet on 6 active seats?" (only counts active players)
3. If YES:
   - Sends command to all active seats
   - Each seat shows pending badge: "⏳ bet_min"
   - Command log shows 6 entries
4. Bots poll backend and execute MIN bets when it's their turn

---

#### 5b. MAX ALL Button
```
┌──────────────────────────┐
│    MAX ALL               │
└──────────────────────────┘
```

**What It Does:** Sets MAX raise on ALL active seats at once

**When You'd Use It:** 
- You have strong hands on multiple seats
- You want to build a huge pot
- All-in strategy

**What Happens:**
1. Click MAX ALL
2. Confirmation: "Raise MAX on 6 active seats?"
3. If YES:
   - Sends command to all active seats
   - Each seat shows pending badge: "⏳ raise_max"
   - Bots execute when it's their turn

---

#### 5c. BET / EXECUTE Button
```
┌──────────────────────────┐
│   BET / EXECUTE          │
└──────────────────────────┘
```

**What It Does:** Executes all pending custom BET commands at once

**Scenario:**
1. You use BET slider on Seat 0 → set 25 ZAR
2. You use BET slider on Seat 2 → set 50 ZAR
3. You use BET slider on Seat 5 → set 75 ZAR
4. Now 3 seats have pending custom bets (not executed yet)
5. Click BET / EXECUTE
6. Confirmation: "Execute 3 pending bets?"
7. If YES → all 3 bets go live

**Why Separate Step:** Prevents accidental bets. You can set amounts, review them, then execute all at once.

---

#### 5d. ARM CASHOUT ALL + CASHOUT ALL Button
```
☐ ARM CASHOUT ALL

┌──────────────────────────┐
│   CASHOUT ALL  🚨        │  (disabled until checkbox checked)
└──────────────────────────┘
```

**Purpose:** Emergency exit from all tables at once

**Why Two-Step Process:** Prevents accidental mass cashout (you could lose thousands)

**How It Works:**
1. Check "☐ ARM CASHOUT ALL" checkbox
2. CASHOUT ALL button turns bright RED + pulsing animation
3. Click CASHOUT ALL
4. **Double Confirmation:**
   - Modal 1: "Are you sure? This will cash out ALL 9 players."
   - Modal 2: Type "CASHOUT" to confirm
5. If confirmed:
   - Sends CASHOUT command to all 9 seats
   - Bots leave tables
   - Your session ends

**When You'd Use It:**
- Something goes wrong (bot acting crazy)
- You need to stop immediately
- Emergency stop button

---

#### 5e. COMMAND LOG
```
┌──────────────────────────┐
│ 📋 COMMAND LOG           │
│ ┌────────────────────┐   │
│ │ 12:34 S0 call PEND │   │
│ │ 12:33 S1 check  OK │   │
│ │ 12:32 S2 fold   OK │   │
│ │ 12:31 S0 raise  OK │   │
│ │ 12:30 S4 call PEND │   │
│ └────────────────────┘   │
└──────────────────────────┘
```

**Purpose:** Shows last 20 commands sent to players

**Format:** `[Time] [Seat] [Command] [Status]`

**Status Values:**
- **PENDING** (yellow) = Queued, waiting for bot to poll
- **OK** (green) = Executed successfully
- **FAILED** (red) = Execution failed (with reason)

**Updates:** Automatically when commands are sent

---

## THE BACKEND (How Data Flows)

### Architecture Overview

```
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│   YOUR BROWSER   │  HTTP   │   FLASK BACKEND  │  n4p.js │  9 CHROME BOTS   │
│  (This UI)       │◄───────►│   (app.py)       │◄───────►│  (Player tabs)   │
└──────────────────┘         └──────────────────┘         └──────────────────┘
        ▲                            │                            ▲
        │                            ▼                            │
        │                    ┌──────────────┐                    │
        │                    │  IN-MEMORY   │                    │
        └────────────────────│    STORES    │────────────────────┘
                             │              │
                             │ • snapshots  │  (seat states)
                             │ • commands   │  (action queue)
                             │ • tables     │  (merged view)
                             │ • hands      │  (hand history)
                             └──────────────┘
```

### The Flow (Step by Step)

#### SCENARIO 1: Bot Sends Snapshot (Every 1-2 seconds)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Step 1: Chrome bot detects cards in iframe                         │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  n4p.js (injected in browser)  │
         │  - Reads icon-layer2 classes   │
         │  - Extracts cards: [Ah,Kh,Qh]  │
         │  - Gets stack, pot, dealer     │
         └────────────────────────────────┘
                          │
                          ▼
         POST /api/snapshot
         {
           "table_id": "bot_1",
           "seat_index": 0,
           "name": "Player1",
           "stack_zar": 200.0,
           "hole_cards": ["Ah", "Kh", "Qh", "Jh"],
           "board_cards": ["Ah", "Kh", "Qh"],
           "status": "playing",
           "timestamp": 1712400000
         }
                          │
                          ▼
         ┌────────────────────────────────┐
         │  Flask Backend (app.py)        │
         │  - Validates JSON              │
         │  - Stores in _snapshot_store   │
         │  - Merges into _merged_tables  │
         │  - Returns OK                  │
         └────────────────────────────────┘
```

**Backend Storage:**
```python
_snapshot_store = {
  "bot_1:0": {
    "seat_index": 0,
    "name": "Player1",
    "stack_zar": 200.0,
    "hole_cards": ["Ah", "Kh", "Qh", "Jh"],
    "status": "playing",
    "last_seen": 1712400000
  }
}

_merged_tables = {
  "bot_1": {
    "table_id": "bot_1",
    "seats": [
      { /* seat 0 data */ },
      { /* seat 1 data */ },
      ...
    ],
    "board": ["Ah", "Kh", "Qh"],
    "pot_zar": 150.0
  }
}
```

---

#### SCENARIO 2: You Click CALL Button on Seat 0

```
┌─────────────────────────────────────────────────────────────────────┐
│ Step 1: You click CALL button in UI                                │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
         JavaScript: sendCommand("bot_1", 0, "call")
                          │
                          ▼
         POST /api/commands/queue
         {
           "table_id": "bot_1",
           "seat_index": 0,
           "command_type": "call"
         }
                          │
                          ▼
         ┌────────────────────────────────┐
         │  Flask Backend                 │
         │  - Generates seat token        │
         │  - Creates command:            │
         │    {                           │
         │      id: "abc123",             │
         │      type: "call",             │
         │      status: "pending"         │
         │    }                           │
         │  - Stores in _command_queue    │
         └────────────────────────────────┘
                          │
                          ▼
         Response: { "ok": true, "command_id": "abc123" }
                          │
                          ▼
         ┌────────────────────────────────┐
         │  UI Updates                    │
         │  - Seat 0 shows: ⏳ call       │
         │  - Command log: "12:34 S0      │
         │    call PENDING"               │
         └────────────────────────────────┘
```

**Backend Storage:**
```python
_command_queue = {
  "<seat_token_for_bot_1_seat_0>": {
    "id": "abc123",
    "type": "call",
    "status": "pending",
    "queued_at": 1712400000
  }
}
```

---

#### SCENARIO 3: Bot Polls for Commands (Every 1-2 seconds)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Step 1: n4p.js polls backend for commands                           │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
         GET /api/commands/pending?token=<seat_token>
                          │
                          ▼
         ┌────────────────────────────────┐
         │  Flask Backend                 │
         │  - Looks up token in queue     │
         │  - Returns command if pending  │
         └────────────────────────────────┘
                          │
                          ▼
         Response: { 
           "ok": true, 
           "command": { "id": "abc123", "type": "call" }
         }
                          │
                          ▼
         ┌────────────────────────────────┐
         │  n4p.js (in Chrome bot)        │
         │  - Receives command: "call"    │
         │  - Finds CALL button in DOM    │
         │  - Clicks button:              │
         │    document.querySelector(     │
         │      '.action-call'            │
         │    ).click()                   │
         └────────────────────────────────┘
                          │
                          ▼
         POST /api/commands/ack
         {
           "token": "<seat_token>",
           "command_id": "abc123"
         }
                          │
                          ▼
         ┌────────────────────────────────┐
         │  Flask Backend                 │
         │  - Marks command as "acked"    │
         │  - Removes from queue          │
         └────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  UI Updates (on next poll)     │
         │  - Seat 0: ⏳ badge disappears │
         │  - Command log: "12:34 S0      │
         │    call OK"                    │
         └────────────────────────────────┘
```

---

#### SCENARIO 4: UI Polls for Table Updates (Every 1 second)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Step 1: JavaScript polls backend for latest table state            │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
         GET /api/table/latest
                          │
                          ▼
         ┌────────────────────────────────┐
         │  Flask Backend                 │
         │  - Merges all seat snapshots   │
         │  - Adds pending commands       │
         │  - Calculates last_seen_ago    │
         │  - Returns full table JSON     │
         └────────────────────────────────┘
                          │
                          ▼
         Response: {
           "ok": true,
           "table": {
             "table_id": "bot_1",
             "seats": [
               {
                 "seat_index": 0,
                 "name": "Player1",
                 "stack_zar": 200.0,
                 "hole_cards": ["Ah", "Kh"],
                 "status": "playing",
                 "last_seen_ago": 2.5,
                 "pending_cmd": null  // was "call", now acked
               },
               // ... 8 more seats
             ],
             "board": ["Ah", "Kh", "Qh"],
             "pot_zar": 150.0
           }
         }
                          │
                          ▼
         ┌────────────────────────────────┐
         │  JavaScript: renderTable()     │
         │  - Updates all 9 seat cards    │
         │  - Updates board cards         │
         │  - Updates pot display         │
         │  - Updates status dots         │
         │  - Enables/disables buttons    │
         └────────────────────────────────┘
```

---

## THE DATA FLOW (Complete Picture)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         POLLING LOOPS                               │
└─────────────────────────────────────────────────────────────────────┘

        ┌──────────────┐
        │   UI POLLS   │  Every 1 second
        │   /table/    │──────────┐
        │   latest     │          │
        └──────────────┘          ▼
               ▲           ┌──────────────┐
               │           │    FLASK     │
               └───────────│   BACKEND    │
                           └──────────────┘
               ┌───────────│              │
               │           └──────────────┘
               ▼                  ▲
        ┌──────────────┐          │
        │  BOT POLLS   │  Every 1-2 seconds
        │  /commands/  │──────────┘
        │  pending     │
        └──────────────┘

        ┌──────────────┐
        │  BOT SENDS   │  Every 1-2 seconds
        │  /snapshot   │──────────┐
        └──────────────┘          │
                                  ▼
                          ┌──────────────┐
                          │    FLASK     │
                          │   BACKEND    │
                          └──────────────┘
```

---

## KEY BACKEND ENDPOINTS

| Endpoint | Method | Purpose | Who Calls It |
|----------|--------|---------|--------------|
| `/api/snapshot` | POST | Bot sends seat state | Bots (n4p.js) |
| `/api/table/latest` | GET | Get current table state | UI (JavaScript) |
| `/api/commands/queue` | POST | Queue command for bot | UI (user clicks button) |
| `/api/commands/pending` | GET | Get pending commands | Bots (n4p.js) |
| `/api/commands/ack` | POST | Acknowledge command done | Bots (n4p.js) |
| `/api/commands/queue-batch` | POST | Queue commands for multiple seats | UI (MIN ALL, MAX ALL) |
| `/api/commands/execute-all` | POST | Execute all pending bets | UI (BET / EXECUTE) |
| `/api/commands/cashout-all` | POST | Cash out all seats | UI (CASHOUT ALL) |
| `/api/hands/recent` | GET | Get hand history | UI (hand log) |

---

## TIMING DIAGRAM (Real-Time Example)

```
TIME    UI ACTION           BACKEND STATE         BOT ACTION          POKER SITE
────────────────────────────────────────────────────────────────────────────────
12:00   User clicks CALL    Command queued        -                   -
12:01   -                   pending: "call"       Bot polls           -
12:01   -                   -                     Gets "call" cmd     -
12:01   -                   -                     Clicks CALL btn     Player calls
12:02   -                   -                     Sends ACK           -
12:02   -                   Command cleared       -                   -
12:02   UI polls            Returns cleared       -                   -
12:02   Badge disappears    -                     -                   -
```

---

## WHY THIS SYSTEM EXISTS

### The Problem Before

**Old Way (Manual):**
```
You have 9 Chrome windows open
┌─────┐ ┌─────┐ ┌─────┐
│ P1  │ │ P2  │ │ P3  │ ...9 windows
└─────┘ └─────┘ └─────┘

During live poker:
- Hand starts
- You need to ACT on Player 1
- Alt+Tab to Player 1 window
- Click CALL
- Alt+Tab to Player 2 window
- Click FOLD
- Alt+Tab to Player 3 window
- Click RAISE
...repeat 9 times per hand

Result: TOO SLOW. You time out. You auto-fold good hands.
```

### The Solution (Remote Control)

**New Way (This UI):**
```
Single dashboard shows all 9 players
┌────────────────────────────────────┐
│  [P1] [P2] [P3]                    │
│  [P4] [P5] [P6]    ONE SCREEN      │
│  [P7] [P8] [P9]                    │
└────────────────────────────────────┘

During live poker:
- Hand starts
- You SEE all 9 players at once
- Click CALL on Player 1 (instant)
- Click FOLD on Player 2 (instant)
- Click RAISE on Player 3 (instant)
- All 9 actions in <5 seconds

Result: FAST. Never timeout. Full control.
```

---

## REAL-WORLD EXAMPLE

**Scenario:** You're playing 9-handed PLO. Flop comes A♥K♥Q♥.

**What You See:**
```
BOARD: [A♥] [K♥] [Q♥]  POT: ZAR 150

SEAT 0: Player1 - [A♠][K♠][Q♠][J♠] - ACTIVE - $200
SEAT 1: Player2 - [2♠][3♠][4♠][5♠] - ACTIVE - $150
SEAT 2: Player3 - [--][--][--][--] - IDLE   - $300
SEAT 3: Empty
SEAT 4: Player5 - [T♠][9♠][8♠][7♠] - ACTIVE - $100
...
```

**Your Strategy:**
- Seat 0 (Player1): You have top two pair → Click RAISE MAX
- Seat 1 (Player2): You have garbage → Click FOLD
- Seat 4 (Player5): You have straight draw → Click CALL

**What Happens:**
1. You click 3 buttons in 2 seconds
2. Commands queue: `raise_max`, `fold`, `call`
3. Bots poll backend
4. n4p.js executes actions when it's their turn
5. Done ✅

**Without This System:** You'd need to switch windows 9 times, probably timeout, lose the hand.

**With This System:** 2 seconds, all actions queued, bots execute perfectly.

---

## SUMMARY

**What It Is:**
- Web dashboard to control 9 poker players from one screen

**How It Works:**
- UI sends commands → Backend queues → Bots poll → n4p.js clicks buttons in browser

**Why It Exists:**
- Impossible to manually switch between 9 Chrome windows during live poker
- This gives you "god mode" control over entire table
- Fast, reliable, never timeout

**Key Concept:**
```
YOU (clicking buttons in UI)
  ↓
BACKEND (Flask, in-memory queue)
  ↓
BOTS (Chrome, polling for commands)
  ↓
POKER SITE (real buttons clicked by n4p.js)
```

**Next Step:** Deploy this UI to production server and connect to live bots
