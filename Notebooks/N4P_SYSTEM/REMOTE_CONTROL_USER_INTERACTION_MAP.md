# Remote Control - User Interaction Map
**What Buttons Exist, What They Send, What User Sees**

**Date:** 2026-04-06  
**Purpose:** Complete mapping of UI buttons → API requests → User feedback

---

## 1. AVAILABLE BUTTONS (What User Sees & Clicks)

### 1.1 Per-Seat Action Buttons (8 buttons × 9 seats = 72 total)

**Location:** Each seat card has 8 buttons in 3×3 grid

```
┌─────────────────────────────────┐
│ SEAT 0 - Player1  🟢            │
│ ZAR 200.00                      │
│ ☐ Check/Fold  ☐ Check/Call     │  ← Pre-action checkboxes
├─────────────────────────────────┤
│ [FOLD]  [CHECK] [CALL]          │  ← Row 1: Basic actions
│ [MIN]   [MAX]   [BET]           │  ← Row 2: Betting actions
│ [ARM]   [CASH]                  │  ← Row 3: Special actions
└─────────────────────────────────┘
```

**Button Inventory:**

| Button | Color | Text Label | When Enabled | Purpose |
|--------|-------|------------|--------------|---------|
| **FOLD** | Red | "FOLD" | Always (when your turn) | Fold your hand |
| **CHECK** | Green | "CHECK" | When no bet to call | Check (no money) |
| **CALL** | Blue | "CALL" | When there's a bet | Call current bet |
| **MIN** | Gray | "MIN" | When can bet/raise | Bet minimum amount |
| **MAX** | Orange | "MAX" | When can bet/raise | Raise to maximum (all-in) |
| **BET** | Dark Orange | "BET" | When can bet/raise | Custom bet amount (opens slider) |
| **ARM** | Purple | "ARM" | Always | Pre-arm action (future use) |
| **CASH** | Yellow | "CASH" | Always when seated | Cash out, leave table |

**Pre-Action Checkboxes (2 per seat):**

| Checkbox | Label | Behavior | Mutually Exclusive |
|----------|-------|----------|-------------------|
| ☐ Check/Fold | "Check/Fold" | If no bet: CHECK, If bet exists: FOLD | With Check/Call |
| ☐ Check/Call | "Check/Call" | If no bet: CHECK, If bet exists: CALL | With Check/Fold |

---

### 1.2 Advanced Action Buttons (Global Controls)

**Location:** Right sidebar panel

```
┌─────────────────────────────────┐
│  🎯 ADVANCED ACTIONS            │
├─────────────────────────────────┤
│  [MIN ALL]                      │  ← Set MIN on all active seats
│  [MAX ALL]                      │  ← Set MAX on all active seats
│  [BET / EXECUTE]                │  ← Execute all pending bets
│  ☐ ARM CASHOUT ALL              │  ← Safety checkbox
│  [CASHOUT ALL]                  │  ← Emergency exit
│  [CLEAR ALL COMMANDS]           │  ← Cancel all pending
└─────────────────────────────────┘
```

**Global Button Inventory:**

| Button | Color | When Enabled | Purpose |
|--------|-------|--------------|---------|
| **MIN ALL** | Blue | Always | Set MIN bet on all active seats at once |
| **MAX ALL** | Blue | Always | Set MAX raise on all active seats at once |
| **BET / EXECUTE** | Orange | When pending bets exist | Execute all pending custom bet commands |
| **CASHOUT ALL** | Red | Only when ARM checkbox checked | Cash out all 9 seats (emergency exit) |
| **CLEAR ALL COMMANDS** | Gray | When any pending commands | Cancel all queued commands |

---

## 2. USER CLICKS BUTTON → WHAT GETS SENT

### 2.1 Per-Seat Actions

#### FOLD Button
**User Action:** Clicks "FOLD" on Seat 3

**JavaScript Executes:**
```javascript
sendCommand('tbl_2143037', 3, 'fold')
```

**POST Request:**
```http
POST /api/commands/queue HTTP/1.1
Host: test.nuts4poker.com:8080
Content-Type: application/json

{
  "table_id": "tbl_2143037",
  "seat_index": 3,
  "command_type": "fold"
}
```

**Backend Response:**
```json
{
  "ok": true,
  "command_id": "a7c9e2f1"
}
```

**User Sees:**
- Seat 3 card shows: "⏳ fold" badge
- Command log updates: "12:34 | S3 | fold | PENDING"
- FOLD button disabled until command completes

---

#### CHECK Button
**User Action:** Clicks "CHECK" on Seat 0

**POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 0,
  "command_type": "check"
}
```

**User Sees:**
- Seat 0: "⏳ check" badge
- Command log: "12:34 | S0 | check | PENDING"

---

#### CALL Button
**User Action:** Clicks "CALL" on Seat 5

**POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 5,
  "command_type": "call"
}
```

**User Sees:**
- Seat 5: "⏳ call" badge
- Command log: "12:34 | S5 | call | PENDING"

---

#### MIN Button
**User Action:** Clicks "MIN" on Seat 2

**POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 2,
  "command_type": "bet_min"
}
```

**User Sees:**
- Seat 2: "⏳ bet_min" badge
- Command log: "12:34 | S2 | bet_min | PENDING"

---

#### MAX Button
**User Action:** Clicks "MAX" on Seat 7

**POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 7,
  "command_type": "raise_max"
}
```

**User Sees:**
- Seat 7: "⏳ raise_max" badge
- Command log: "12:34 | S7 | raise_max | PENDING"

---

#### BET Button (Custom Amount)
**User Action:** Clicks "BET" on Seat 4

**Step 1: Slider Appears**
```
┌─────────────────────────────────┐
│ BET AMOUNT: ZAR 25.00           │
│ ├──────●───────────────────────┤│
│ Min: 5.00        Max: 200.00   │
│ [CONFIRM] [CANCEL]              │
└─────────────────────────────────┘
```

**Step 2: User drags slider to 50.00**

**Step 3: User clicks CONFIRM**

**POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 4,
  "command_type": "bet_custom",
  "value": 50.00
}
```

**User Sees:**
- Seat 4: "⏳ bet_custom (50.00)" badge
- Slider collapses
- Command log: "12:34 | S4 | bet_custom | PENDING"
- Amount shown in badge: "(50.00)"

---

#### CASH (Cashout) Button
**User Action:** Clicks "CASH" on Seat 1

**Confirmation Modal:**
```
╔═══════════════════════════════════╗
║  Confirm Cashout                  ║
║                                   ║
║  Cash out Player2 from Seat 1?    ║
║  Current stack: ZAR 150.00        ║
║                                   ║
║  [YES]  [NO]                      ║
╚═══════════════════════════════════╝
```

**If YES, POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 1,
  "command_type": "cashout"
}
```

**User Sees:**
- Seat 1: "⏳ cashout" badge
- Command log: "12:34 | S1 | cashout | PENDING"
- After execution: Seat 1 becomes empty (name = null)

---

#### ARM Button
**User Action:** Clicks "ARM" on Seat 6

**Purpose:** Pre-arm action for future use (not implemented yet)

**POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 6,
  "command_type": "pre_action_arm",
  "value": true
}
```

**User Sees:**
- ARM button changes color (purple → bright purple)
- Seat 6: "ARMED" indicator
- Future actions will be pre-armed

---

#### Check/Fold Checkbox
**User Action:** Checks ☑ Check/Fold on Seat 8

**POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 8,
  "command_type": "pre_action_check_fold",
  "value": true
}
```

**User Sees:**
- Checkbox ☑ Check/Fold checked
- Checkbox ☐ Check/Call auto-unchecks (mutually exclusive)
- Seat 8: Pre-action indicator "CF" shown
- Command log: "12:34 | S8 | check_fold | PENDING"

**If User Unchecks:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 8,
  "command_type": "clear_preaction"
}
```

---

#### Check/Call Checkbox
**User Action:** Checks ☑ Check/Call on Seat 3

**POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_index": 3,
  "command_type": "pre_action_check_call",
  "value": true
}
```

**User Sees:**
- Checkbox ☑ Check/Call checked
- Checkbox ☐ Check/Fold auto-unchecks
- Seat 3: Pre-action indicator "CC" shown
- Command log: "12:34 | S3 | check_call | PENDING"

---

### 2.2 Global Actions

#### MIN ALL Button
**User Action:** Clicks "MIN ALL"

**Confirmation Modal:**
```
╔═══════════════════════════════════╗
║  Set MIN on All Active Seats?     ║
║                                   ║
║  6 active seats will bet MIN      ║
║  (Seats 0, 1, 3, 5, 6, 8)         ║
║                                   ║
║  [CONFIRM]  [CANCEL]              ║
╚═══════════════════════════════════╝
```

**If CONFIRM, POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_indices": [0, 1, 3, 5, 6, 8],
  "command_type": "bet_min"
}
```

**Backend Response:**
```json
{
  "ok": true,
  "command_ids": ["a1", "b2", "c3", "d4", "e5", "f6"],
  "queued_count": 6
}
```

**User Sees:**
- All 6 active seats show: "⏳ bet_min" badge
- Command log shows 6 entries:
  ```
  12:34 | S0 | bet_min | PENDING
  12:34 | S1 | bet_min | PENDING
  12:34 | S3 | bet_min | PENDING
  12:34 | S5 | bet_min | PENDING
  12:34 | S6 | bet_min | PENDING
  12:34 | S8 | bet_min | PENDING
  ```
- MIN ALL button disabled for 3 seconds (prevent spam)

---

#### MAX ALL Button
**User Action:** Clicks "MAX ALL"

**Confirmation Modal:**
```
╔═══════════════════════════════════╗
║  Raise MAX on All Active Seats?   ║
║                                   ║
║  6 active seats will go ALL-IN    ║
║  Total: ZAR 1,200.00              ║
║                                   ║
║  [CONFIRM]  [CANCEL]              ║
╚═══════════════════════════════════╝
```

**If CONFIRM, POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "seat_indices": [0, 1, 3, 5, 6, 8],
  "command_type": "raise_max"
}
```

**User Sees:**
- All 6 active seats: "⏳ raise_max" badge
- Command log: 6 entries for raise_max
- MAX ALL button disabled temporarily

---

#### BET / EXECUTE Button
**User Action:**
1. Sets custom bet on Seat 0 (25.00)
2. Sets custom bet on Seat 2 (50.00)
3. Sets custom bet on Seat 5 (75.00)
4. Clicks "BET / EXECUTE"

**Confirmation Modal:**
```
╔═══════════════════════════════════╗
║  Execute Pending Bets?            ║
║                                   ║
║  Seat 0: ZAR 25.00                ║
║  Seat 2: ZAR 50.00                ║
║  Seat 5: ZAR 75.00                ║
║                                   ║
║  Total: ZAR 150.00                ║
║                                   ║
║  [EXECUTE]  [CANCEL]              ║
╚═══════════════════════════════════╝
```

**If EXECUTE, POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "action": "execute_all"
}
```

**Backend Response:**
```json
{
  "ok": true,
  "executed_count": 3,
  "failed_count": 0
}
```

**User Sees:**
- Seat 0, 2, 5: Badges change from "⏳ bet_custom" → "EXECUTING"
- Command log updates: "bet_custom | EXECUTING"
- After 1-2 seconds: Badges change to "✓ bet_custom | OK"
- Bets are executed in browsers

---

#### CASHOUT ALL Button
**User Action:**
1. Checks ☑ ARM CASHOUT ALL checkbox
2. CASHOUT ALL button turns bright red + pulsing
3. Clicks "CASHOUT ALL"

**Double Confirmation:**

**Modal 1:**
```
╔═════════════════════════════════════╗
║  ⚠️  EMERGENCY CASHOUT ALL          ║
║                                     ║
║  This will cash out ALL 9 players   ║
║  and leave the table.               ║
║                                     ║
║  Are you sure?                      ║
║                                     ║
║  [YES, CONTINUE]  [NO, CANCEL]      ║
╚═════════════════════════════════════╝
```

**If YES, Modal 2:**
```
╔═════════════════════════════════════╗
║  Final Confirmation                 ║
║                                     ║
║  Type "CASHOUT" to confirm:         ║
║  [_________________]                ║
║                                     ║
║  [CONFIRM]  [CANCEL]                ║
╚═════════════════════════════════════╝
```

**If User types "CASHOUT" and clicks CONFIRM, POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "action": "cashout_all",
  "confirm": true
}
```

**Backend Response:**
```json
{
  "ok": true,
  "cashed_out_seats": [0, 1, 2, 3, 4, 5, 6, 7, 8]
}
```

**User Sees:**
- All 9 seats: "⏳ cashout" badge
- Command log: 9 cashout entries
- ARM CASHOUT ALL checkbox auto-unchecks
- After execution: All seats become empty
- Table view shows "Waiting for players..."

---

#### CLEAR ALL COMMANDS Button
**User Action:** Clicks "CLEAR ALL COMMANDS"

**Confirmation Modal:**
```
╔═══════════════════════════════════╗
║  Clear All Pending Commands?      ║
║                                   ║
║  This will cancel:                ║
║  - 5 pending commands             ║
║                                   ║
║  [CLEAR ALL]  [CANCEL]            ║
╚═══════════════════════════════════╝
```

**If CLEAR ALL, POST Request:**
```json
{
  "table_id": "tbl_2143037",
  "action": "clear_all"
}
```

**Backend Response:**
```json
{
  "ok": true,
  "cleared_count": 5
}
```

**User Sees:**
- All pending badges (⏳) disappear from seat cards
- Command log entries change from "PENDING" → "CANCELLED"
- Command queue cleared

---

## 3. BACKEND RESPONSE → USER FEEDBACK

### 3.1 Command Queue Response

**Success Response:**
```json
{
  "ok": true,
  "command_id": "a7c9e2f1"
}
```

**User Sees:**
- ✅ Command queued successfully
- Seat card shows pending badge: "⏳ [command_type]"
- Command log entry: "[time] | S[N] | [command] | PENDING"
- Button re-enabled after 200ms

---

**Error Response:**
```json
{
  "ok": false,
  "error": "Player not active",
  "details": "Seat 3 is not in hand"
}
```

**User Sees:**
- ❌ Toast notification (top-right):
  ```
  ┌─────────────────────────────────┐
  │ ❌ Command Failed               │
  │ Player not active               │
  │ Seat 3 is not in hand           │
  └─────────────────────────────────┘
  ```
- Command log entry: "[time] | S3 | [command] | FAILED"
- Button re-enabled immediately

---

### 3.2 Command Execution (n4p.js → Backend → UI)

**Flow:**
```
1. User clicks CALL button
   ↓
2. UI sends POST /api/commands/queue
   ↓
3. Backend queues command
   ↓
4. n4p.js polls GET /api/commands/pending
   ↓
5. n4p.js finds "call" command
   ↓
6. n4p.js clicks CALL button in browser
   ↓
7. n4p.js sends POST /api/commands/ack
   ↓
8. Backend removes command from queue
   ↓
9. UI polls GET /api/table/latest
   ↓
10. UI updates: pending badge → clear
    ↓
11. Command log: "PENDING" → "OK"
```

**Timing:**
- User clicks button: 0ms
- POST response: 50-100ms
- Badge appears: 100ms
- n4p.js polls: 1000ms (every 1 second)
- n4p.js executes: 1100ms
- n4p.js ACKs: 1200ms
- UI polls: 2000ms (every 1 second)
- Badge clears: 2100ms
- **Total time: ~2 seconds**

---

### 3.3 Real-Time Updates (Polling)

**UI Polls Backend Every 1 Second:**
```javascript
setInterval(() => {
  fetch('/api/table/latest')
    .then(r => r.json())
    .then(data => {
      renderTable(data.table);  // Update UI
    });
}, 1000);
```

**Backend Returns:**
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
        "status": "playing",
        "pending_cmd": null,
        "last_seen_ago": 2.5
      }
      // ... 8 more seats
    ],
    "board": ["As", "Ks", "Qh"],
    "pot_zar": 150.00,
    "street": "flop"
  }
}
```

**User Sees Updates:**
- Seat cards refresh (names, stacks, cards)
- Board cards update (flop → turn → river)
- Pot display updates
- Pending badges clear when commands execute
- Status dots change (🟢 active → ⚪ idle)
- Dealer button moves

---

## 4. COMPLETE USER INTERACTION EXAMPLE

### Scenario: User Wants to Raise MAX on Seat 3

**Step 1: User clicks "MAX" button on Seat 3**
```
User clicks: [MAX] button (orange)
```

**Step 2: JavaScript sends POST request**
```http
POST /api/commands/queue
{
  "table_id": "tbl_2143037",
  "seat_index": 3,
  "command_type": "raise_max"
}
```

**Step 3: Backend responds**
```json
{
  "ok": true,
  "command_id": "f7e2a9c1"
}
```

**Step 4: User sees immediate feedback**
```
✅ Seat 3 card updates:
   - Shows badge: "⏳ raise_max"
   - MAX button disabled
   - Command log entry: "12:34 | S3 | raise_max | PENDING"
```

**Step 5: n4p.js (in bot's browser) polls for commands (1 second later)**
```http
GET /api/commands/pending?token=<seat_3_token>
```

**Step 6: Backend returns command**
```json
{
  "ok": true,
  "command": {
    "id": "f7e2a9c1",
    "type": "raise_max"
  }
}
```

**Step 7: n4p.js executes in browser**
```javascript
// Find and click RAISE MAX button in poker client
const raiseBtn = document.querySelector(".action-raise-max");
raiseBtn.click();
```

**Step 8: n4p.js acknowledges completion**
```http
POST /api/commands/ack
{
  "token": "<seat_3_token>",
  "command_id": "f7e2a9c1"
}
```

**Step 9: Backend clears command from queue**
```json
{
  "ok": true
}
```

**Step 10: UI polls and updates (1 second after ACK)**
```http
GET /api/table/latest
```

**Step 11: Backend returns updated state**
```json
{
  "table": {
    "seats": [
      {
        "seat_index": 3,
        "pending_cmd": null,  // ← No longer pending
        "stack_zar": 0.00     // ← All-in
      }
    ]
  }
}
```

**Step 12: User sees final result**
```
✅ Seat 3 card updates:
   - Badge disappears (⏳ gone)
   - Stack shows: "ZAR 0.00" (all-in)
   - Status: "ALL-IN"
   - MAX button re-enabled
   - Command log: "12:34 | S3 | raise_max | OK"
```

**Total Time:** ~2 seconds from click to completion

---

## 5. BUTTON AVAILABILITY RULES

### 5.1 When Buttons Are Enabled/Disabled

**All Action Buttons Disabled When:**
- Seat is empty (no player)
- Player is not active (status != "playing")
- Player's turn hasn't come yet
- Connection lost (last_seen > 30s)
- Command already pending for that seat
- Table is not in active hand

**All Action Buttons Enabled When:**
- Seat is occupied (has player name)
- Player status = "playing"
- Player has token (has_token = true)
- No pending command
- Connection healthy (last_seen < 30s)

**Special Cases:**
- **CASH button:** Always enabled when seated (even if not in hand)
- **ARM button:** Always enabled when seated
- **Pre-action checkboxes:** Always enabled when seated
- **BET slider CONFIRM:** Only enabled when amount >= min bet
- **CASHOUT ALL:** Only enabled when ARM checkbox is checked

---

## 6. ERROR HANDLING & USER FEEDBACK

### 6.1 Error Types

**Network Error:**
```
User clicks button → POST fails (timeout or 500)
```

**User Sees:**
```
┌─────────────────────────────────┐
│ ⚠️ Network Error                │
│ Could not reach server          │
│ Retrying...                     │
└─────────────────────────────────┘
```

**Auto-retry:** 3 attempts with 1s delay

---

**Command Invalid:**
```
Backend rejects: "Player not active"
```

**User Sees:**
```
┌─────────────────────────────────┐
│ ❌ Command Failed               │
│ Player not active               │
│ Seat not in current hand        │
└─────────────────────────────────┘
```

**Command log:** "FAILED (Player not active)"

---

**Command Timeout:**
```
Command pending for >10 seconds, no ACK
```

**User Sees:**
```
┌─────────────────────────────────┐
│ ⚠️ Command Timeout              │
│ Seat 3: raise_max timed out     │
│ Bot may not be responding       │
└─────────────────────────────────┘
```

**Auto-action:** Badge changes to "❌ raise_max (timeout)"

---

## SUMMARY

**User Has Access To:**
- **72 action buttons** (8 per seat × 9 seats)
- **18 pre-action checkboxes** (2 per seat × 9 seats)
- **5 global action buttons** (MIN ALL, MAX ALL, BET/EXECUTE, CASHOUT ALL, CLEAR ALL)
- **Total: 95 interactive elements**

**Every Button Click:**
1. Sends POST request to `/api/commands/queue` or `/api/commands/[action]`
2. Gets immediate response (`ok: true` or error)
3. Shows pending badge (⏳) on seat card
4. Adds entry to command log
5. Waits for n4p.js to execute (~1-2 seconds)
6. Updates UI when command completes
7. Shows success (✓) or failure (❌) state

**User Gets Feedback Via:**
- Pending badges on seat cards (⏳ command_type)
- Command log entries (PENDING → OK/FAILED)
- Toast notifications (errors, warnings)
- Visual indicators (button disabled, colors change)
- Real-time updates (stack changes, status changes)

**Response Time:**
- UI feedback: Instant (<100ms)
- Command execution: 1-2 seconds
- UI update: 2-3 seconds total
