# Remote Control UI - Complete Specification
**Visual Layout & Component Architecture**

**Date:** 2026-04-06  
**Status:** Planning Document  
**Purpose:** Detailed UI/UX specification for 9-player remote control system

---

## Table of Contents
1. [Overall Layout Structure](#1-overall-layout-structure)
2. [Component Hierarchy](#2-component-hierarchy)
3. [Detailed Component Specs](#3-detailed-component-specs)
4. [Color Scheme & Theming](#4-color-scheme--theming)
5. [Responsive Design](#5-responsive-design)
6. [Interaction Patterns](#6-interaction-patterns)
7. [State Management](#7-state-management)

---

## 1. Overall Layout Structure

### 1.1 Desktop Layout (1920×1080)

```
┌────────────────────────────────────────────────────────────────────────┐
│  HEADER                                                        [TEST]   │
│  N4P // REMOTE TABLE CONTROL                                           │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  RAW HAND LOG                                     [COPY]  [CLEAR]      │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ PokerStars Hand #123456789: Hold'em No Limit ($0.50/$1.00)      │ │
│  │ Table 'Belgrade' 9-max Seat #3 is the button                     │ │
│  │ Seat 1: Player1 ($200.00 in chips)                               │ │
│  │ ...                                                               │ │
│  │                                                                   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────┬───────────────────────────┐
│                                            │  ADVANCED ACTIONS         │
│  BOARD DISPLAY                             │                           │
│  ┌──────────────────────────────────────┐ │  [MIN ALL]                │
│  │   POT: ZAR 150.00                    │ │  [MAX ALL]                │
│  │   FLOP                               │ │  [BET / EXECUTE]          │
│  │   [A♥] [K♥] [Q♥] [--] [--]          │ │                           │
│  └──────────────────────────────────────┘ │  ☐ ARM CASHOUT ALL        │
│                                            │  [CASHOUT ALL]            │
│  9-SEAT GRID (3×3)                         │                           │
│  ┌─────────┬─────────┬─────────┐          │  COMMAND LOG              │
│  │ SEAT 0  │ SEAT 1  │ SEAT 2  │          │  ┌─────────────────────┐ │
│  │ Player1 │ Player2 │ Player3 │          │  │ 12:34 | S0 | CALL   │ │
│  │ $200.00 │ $150.00 │ $300.00 │          │  │ 12:33 | S1 | CHECK  │ │
│  │ [A♥][K♥]│ [--][--]│ [--][--]│          │  │ 12:32 | S2 | FOLD   │ │
│  │ [DEALER]│         │         │          │  └─────────────────────┘ │
│  ├─────────┼─────────┼─────────┤          └───────────────────────────┘
│  │ SEAT 3  │ SEAT 4  │ SEAT 5  │
│  │ Empty   │ Player5 │ Player6 │
│  │ $0.00   │ $100.00 │ $250.00 │
│  ├─────────┼─────────┼─────────┤
│  │ SEAT 6  │ SEAT 7  │ SEAT 8  │
│  │ Player7 │ Empty   │ Player9 │
│  │ $180.00 │ $0.00   │ $220.00 │
│  └─────────┴─────────┴─────────┘
└────────────────────────────────────────────┘
```

### 1.2 Tablet Layout (768×1024)

```
┌─────────────────────────────────────────┐
│  HEADER                           [TEST]│
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  HAND LOG (COLLAPSED)       [EXPAND]    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  BOARD    POT: $150  [A♥][K♥][Q♥]      │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  9-SEAT GRID (2×5)                      │
│  ┌─────────────┬─────────────┐          │
│  │   SEAT 0    │   SEAT 1    │          │
│  ├─────────────┼─────────────┤          │
│  │   SEAT 2    │   SEAT 3    │          │
│  ├─────────────┼─────────────┤          │
│  │   SEAT 4    │   SEAT 5    │          │
│  ├─────────────┼─────────────┤          │
│  │   SEAT 6    │   SEAT 7    │          │
│  ├─────────────┼─────────────┤          │
│  │   SEAT 8    │             │          │
│  └─────────────┴─────────────┘          │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  ADVANCED ACTIONS (BOTTOM BAR)          │
│  [MIN ALL] [MAX ALL] [BET] [CASHOUT]   │
└─────────────────────────────────────────┘
```

### 1.3 Mobile Layout (375×667)

```
┌──────────────────────────┐
│  N4P REMOTE      [TEST]  │
└──────────────────────────┘

┌──────────────────────────┐
│  POT: $150  FLOP         │
│  [A♥][K♥][Q♥]           │
└──────────────────────────┘

┌──────────────────────────┐
│  SEAT 0 - Player1 ●      │
│  $200.00 [DEALER]        │
│  [A♥][K♥][Q♥][J♥]       │
│  ☐CF ☐CC                 │
│  [FD][CK][CL][MN][MX]    │
│  [BET][ARM][CASH]        │
├──────────────────────────┤
│  SEAT 1 - Empty ○        │
│  $0.00                   │
│  ...                     │
└──────────────────────────┘

[▼ ADVANCED ACTIONS]
```

---

## 2. Component Hierarchy

### 2.1 DOM Structure

```
body
├── .header
│   ├── h1 "N4P // REMOTE TABLE CONTROL"
│   └── .test-badge "TEST"
│
├── .hand-log-container
│   ├── .hand-log-header
│   │   ├── h3 "RAW HAND LOG"
│   │   └── .hand-log-buttons
│   │       ├── button.btn-copy "COPY"
│   │       └── button.btn-clear-log "CLEAR"
│   └── textarea#hand-log-textarea
│
├── .main-layout-wrapper
│   ├── .table-section (LEFT - 70% width)
│   │   ├── .board-container
│   │   │   ├── .street-display "FLOP"
│   │   │   ├── .pot-display "POT: ZAR 150.00"
│   │   │   └── .board-cards
│   │   │       ├── .card.red "A♥"
│   │   │       ├── .card.red "K♥"
│   │   │       └── .card.red "Q♥"
│   │   │
│   │   └── .seats-grid (3×3 grid)
│   │       ├── .seat-card [×9]
│   │       │   ├── .seat-header
│   │       │   │   ├── .seat-title "SEAT 0"
│   │       │   │   ├── .status-dot.live
│   │       │   │   └── .dealer-marker "DEALER"
│   │       │   ├── .seat-info
│   │       │   │   ├── .player-name "Player1"
│   │       │   │   ├── .stack "ZAR 200.00"
│   │       │   │   ├── .status-text "ACTIVE"
│   │       │   │   └── .hole-cards
│   │       │   │       └── .hole-card.red "A♥" [×4 for PLO]
│   │       │   ├── .pre-actions
│   │       │   │   ├── input#cf-0 [checkbox]
│   │       │   │   ├── label "Check/Fold"
│   │       │   │   ├── input#cc-0 [checkbox]
│   │       │   │   └── label "Check/Call"
│   │       │   ├── .action-buttons (3×3 grid)
│   │       │   │   ├── button.btn-fold "FOLD"
│   │       │   │   ├── button.btn-check "CHECK"
│   │       │   │   ├── button.btn-call "CALL"
│   │       │   │   ├── button.btn-min "MIN"
│   │       │   │   ├── button.btn-max "MAX"
│   │       │   │   ├── button.btn-bet "BET"
│   │       │   │   ├── button.btn-arm "ARM"
│   │       │   │   └── button.btn-cashout "CASH"
│   │       │   ├── .bet-slider-container (conditional)
│   │       │   │   ├── input[type=range]#bet-slider-0
│   │       │   │   └── .bet-value-display "ZAR 25.00"
│   │       │   └── .pending-badge "⏳ raise_max"
│   │
│   └── .advanced-actions-panel (RIGHT - 30% width)
│       ├── h3 "ADVANCED ACTIONS"
│       ├── .global-buttons
│       │   ├── button.btn-global-min "MIN ALL"
│       │   ├── button.btn-global-max "MAX ALL"
│       │   ├── button.btn-execute-all "BET / EXECUTE"
│       │   ├── .arm-cashout-container
│       │   │   ├── input#arm-cashout-all [checkbox]
│       │   │   └── label "ARM CASHOUT ALL"
│       │   ├── button.btn-cashout-all "CASHOUT ALL" [disabled]
│       │   └── button.btn-clear-all "CLEAR ALL COMMANDS"
│       │
│       └── .command-log
│           ├── h4 "COMMAND LOG"
│           └── #log-container
│               └── .log-entry [×20]
│                   ├── span "12:34 | Seat 0 | call"
│                   └── span "PENDING"
```

---

## 3. Detailed Component Specs

### 3.1 Seat Card Component

**Dimensions:** 280px × 420px (desktop)  
**Border:** 3px solid (color varies by state)  
**Background:** rgba(255, 255, 255, 0.15)  
**Border Radius:** 8px  
**Padding:** 12px

#### 3.1.1 Seat Header

```
┌────────────────────────────────────┐
│ SEAT 0 ●                  [DEALER] │
└────────────────────────────────────┘
```

- **Seat Title:** "SEAT 0" through "SEAT 8"
- **Status Dot:** 
  - Green (live): `#4caf50` with glow shadow
  - Gray (offline): `#666`
- **Dealer Marker:** 
  - Background: `#ffc107` (gold)
  - Text: Black, bold, uppercase "DEALER"
  - Only shown when `is_dealer === true`

#### 3.1.2 Seat Info

```
┌────────────────────────────────────┐
│ Player1                            │
│ ZAR 200.00                         │
│ Status: ACTIVE                     │
│ [A♥] [K♥] [Q♥] [J♥]               │
│ ⏳ raise_max                       │
└────────────────────────────────────┘
```

- **Player Name:** 
  - Empty seats: "Empty" (opacity 0.5)
  - Occupied: Player username
  - Font: Bold, 1em
- **Stack:** 
  - Format: "ZAR XXX.XX"
  - Font: 0.85em
  - Color: White
- **Status Text:**
  - EMPTY: Gray, seat not occupied
  - OCCUPIED: White, player seated but not in hand
  - ACTIVE: Green, player in current hand
  - PENDING: Yellow, command queued
  - DISCONNECTED: Red, snapshot stale (>30s)
- **Hole Cards:** 
  - 4-color deck (inverted):
    - Hearts (♥): Red `#ff0000`
    - Diamonds (♦): Blue `#0066ff`
    - Clubs (♣): Green `#00aa00`
    - Spades (♠): Black `#000000`
  - Display: 2 cards (Hold'em) or 4 cards (PLO)
  - Hidden cards: `[--]` gray placeholder
- **Pending Badge:**
  - Background: `#ff6b35` (orange)
  - Icon: ⏳ (hourglass)
  - Text: Command type (e.g., "raise_max")
  - Only shown when `pending_cmd !== null`

#### 3.1.3 Pre-Actions Section

```
┌────────────────────────────────────┐
│ ☐ Check/Fold                       │
│ ☐ Check/Call                       │
└────────────────────────────────────┘
```

- **Checkboxes:** 14px × 14px
- **Mutually Exclusive:** Checking one unchecks the other
- **Disabled State:** When `!canAct` (not active or disconnected)
- **Checked State:** 
  - Background: `#4caf50` (green)
  - Border: 2px solid `#2e7d32`

#### 3.1.4 Action Buttons Grid (3×3)

```
┌──────┬──────┬──────┐
│ FOLD │ CHK  │ CALL │
├──────┼──────┼──────┤
│ MIN  │ MAX  │ BET  │
├──────┼──────┼──────┤
│ ARM  │ CASH │      │
└──────┴──────┴──────┘
```

**Button Specs:**
- **Size:** 80px × 36px
- **Font:** 0.7em, bold, uppercase
- **Border:** None
- **Border Radius:** 4px
- **Hover:** 
  - Transform: `translateY(-1px)`
  - Shadow: `0 3px 6px rgba(0, 0, 0, 0.3)`
- **Disabled:** 
  - Opacity: 0.5
  - Cursor: not-allowed

**Button Colors:**

| Button | Background | Text | Purpose |
|--------|------------|------|---------|
| FOLD | `#f44336` (red) | White | Fold hand |
| CHECK | `#4caf50` (green) | White | Check (no bet) |
| CALL | `#2196f3` (blue) | White | Call current bet |
| MIN | `#607d8b` (gray) | White | Bet minimum |
| MAX | `#ff9800` (orange) | White | Raise maximum |
| BET | `#ff6f00` (dark orange) | White | Custom bet (opens slider) |
| ARM | `#9c27b0` (purple) | White | Pre-arm action |
| CASH | `#ffc107` (yellow) | Black | Cash out |

#### 3.1.5 Bet Slider (Conditional)

**Shown When:** BET button is clicked

```
┌────────────────────────────────────┐
│ BET AMOUNT: ZAR 25.00              │
│ ├──────●─────────────────────────┤ │
│ Min: 5.00          Max: 200.00    │
│ [CONFIRM] [CANCEL]                 │
└────────────────────────────────────┘
```

- **Slider:** 
  - Type: `<input type="range">`
  - Min: Current minimum bet
  - Max: Player's stack
  - Step: 0.50 (ZAR)
  - Width: 100%
  - Height: 8px
  - Thumb: 16px circle, `#ff9800` (orange)
- **Value Display:** 
  - Format: "ZAR XX.XX"
  - Font: 1em, bold
  - Color: `#ffc107` (gold)
- **Confirm Button:** Green `#4caf50`
- **Cancel Button:** Gray `#666`

#### 3.1.6 Seat Card State Borders

| State | Border Color | Animation |
|-------|--------------|-----------|
| Empty | Transparent | None |
| Occupied (idle) | `#4caf50` (green, solid) | None |
| Active (your turn) | `#ffc107` (gold) | Blink yellow↔red |
| Stale (disconnected) | `#ff5722` (red) | None |
| Pending command | `#ff6b35` (orange) | Pulse glow |

**Blink Animation:**
```css
@keyframes blink-border {
  0%, 100% {
    border-color: #ffc107;
    box-shadow: 0 0 20px #ffc107;
  }
  50% {
    border-color: #ff5722;
    box-shadow: 0 0 40px #ff5722;
  }
}
```

---

### 3.2 Board Display Component

**Location:** Above seat grid, centered  
**Dimensions:** 600px × 120px  
**Background:** rgba(255, 255, 255, 0.1)  
**Border Radius:** 10px  
**Padding:** 20px

```
┌────────────────────────────────────────────────┐
│              POT: ZAR 150.00                   │
│                   FLOP                         │
│   [A♥] [K♥] [Q♥] [--] [--]                    │
└────────────────────────────────────────────────┘
```

#### 3.2.1 Pot Display
- **Font:** 1.5em, bold
- **Color:** `#ffc107` (gold)
- **Format:** "POT: ZAR XXX.XX"

#### 3.2.2 Street Display
- **Font:** 1em, uppercase
- **Background:** rgba(255, 255, 255, 0.2)
- **Padding:** 8px 16px
- **Border Radius:** 5px
- **Values:** "PREFLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN"

#### 3.2.3 Board Cards
- **Display:** 5 card slots (flex row, gap 10px)
- **Card Size:** 50px × 70px
- **Empty Slot:** `[--]` gray placeholder
- **Order:** 
  - Slots 0-2: Flop
  - Slot 3: Turn
  - Slot 4: River

---

### 3.3 Advanced Actions Panel

**Location:** Right sidebar (30% width)  
**Background:** rgba(0, 0, 0, 0.4)  
**Border Radius:** 10px  
**Padding:** 20px

```
┌─────────────────────────────────┐
│    ADVANCED ACTIONS             │
│                                 │
│  ┌───────────────────────────┐ │
│  │      MIN ALL              │ │
│  └───────────────────────────┘ │
│  ┌───────────────────────────┐ │
│  │      MAX ALL              │ │
│  └───────────────────────────┘ │
│  ┌───────────────────────────┐ │
│  │    BET / EXECUTE          │ │
│  └───────────────────────────┘ │
│                                 │
│  ☐ ARM CASHOUT ALL              │
│                                 │
│  ┌───────────────────────────┐ │
│  │    CASHOUT ALL            │ │
│  └───────────────────────────┘ │
│                                 │
│  ┌───────────────────────────┐ │
│  │    CLEAR ALL COMMANDS     │ │
│  └───────────────────────────┘ │
└─────────────────────────────────┘
```

#### 3.3.1 Global Action Buttons

**Button Specs:**
- **Width:** 100%
- **Height:** 50px
- **Font:** 1.1em, bold, uppercase
- **Margin:** 10px 0
- **Border Radius:** 8px
- **Hover:** Scale(1.02) + shadow

| Button | Color | Action | Confirmation |
|--------|-------|--------|--------------|
| MIN ALL | `#2196f3` (blue) | Set MIN on all active seats | None |
| MAX ALL | `#2196f3` (blue) | Set MAX on all active seats | None |
| BET / EXECUTE | `#ff9800` (orange) | Execute all pending BET commands | "Execute X pending bets?" |
| CASHOUT ALL | `#f44336` (red) | Cash out all seats | **Requires ARM checkbox** |
| CLEAR ALL COMMANDS | `#666` (gray) | Clear all pending commands | "Clear all pending commands?" |

#### 3.3.2 ARM CASHOUT ALL Checkbox

**Purpose:** Safety mechanism to prevent accidental mass cashout

- **Default State:** Unchecked
- **When Checked:** 
  - CASHOUT ALL button becomes enabled
  - Button changes to bright red `#ff0000`
  - Button shows pulsing glow animation
- **Auto-Uncheck:** After CASHOUT ALL is clicked (if confirmed)

---

### 3.4 Command Log Component

**Location:** Bottom of advanced actions panel  
**Max Height:** 300px  
**Overflow:** Scroll (auto)  
**Background:** rgba(0, 0, 0, 0.4)  
**Border Radius:** 10px  
**Padding:** 20px

```
┌─────────────────────────────────┐
│    COMMAND LOG                  │
│  ┌───────────────────────────┐ │
│  │ 12:34 | S0 | call  PENDING│ │
│  │ 12:33 | S1 | check    OK  │ │
│  │ 12:32 | S2 | fold     OK  │ │
│  │ 12:31 | S0 | raise_max OK │ │
│  └───────────────────────────┘ │
└─────────────────────────────────┘
```

#### 3.4.1 Log Entry Format

- **Display:** Last 20 commands (newest first)
- **Entry Background:** rgba(255, 255, 255, 0.1)
- **Border Radius:** 5px
- **Padding:** 8px
- **Font:** 0.9em, monospace
- **Layout:** Flexbox, space-between

**Entry Structure:**
```
[Timestamp] | Seat [N] | [Command Type]     [Status]
12:34:56    | S0       | raise_max          PENDING
```

**Status Colors:**
- PENDING: `#ffc107` (yellow)
- OK/ACKED: `#4caf50` (green)
- FAILED: `#f44336` (red)

---

### 3.5 Hand Log Component

**Location:** Top of page, above board  
**Height:** 300px (default, resizable)  
**Background:** `#1a1a1a` (black terminal)  
**Border:** 2px solid `#333`  
**Border Radius:** 5px

```
┌────────────────────────────────────────────────┐
│  RAW HAND LOG              [COPY]  [CLEAR]     │
│  ┌──────────────────────────────────────────┐ │
│  │ PokerStars Hand #123456789: Hold'em...  │ │
│  │ Table 'Belgrade' 9-max Seat #3 button   │ │
│  │ Seat 1: Player1 ($200 in chips)         │ │
│  │ Seat 2: Player2 ($150 in chips)         │ │
│  │ ...                                      │ │
│  │ *** HOLE CARDS ***                       │ │
│  │ Dealt to Player1 [Ah Kh Qh Jh]          │ │
│  │ Player2: folds                           │ │
│  │ Player1: raises $10 to $15               │ │
│  │ ...                                      │ │
│  └──────────────────────────────────────────┘ │
└────────────────────────────────────────────────┘
```

#### 3.5.1 Textarea Specs

- **Font:** 'Courier New', monospace
- **Font Size:** 13px
- **Color:** `#0f0` (green terminal text)
- **Background:** `#1a1a1a`
- **Resize:** Vertical only
- **Readonly:** true
- **Auto-scroll:** To bottom (newest hand)

#### 3.5.2 Action Buttons

**COPY Button:**
- **Color:** `#4caf50` (green)
- **Action:** Copy entire log to clipboard
- **Feedback:** Button text changes to "COPIED!" for 1 second

**CLEAR Button:**
- **Color:** `#f44336` (red)
- **Action:** Clear all hand history
- **Confirmation:** "Clear all hand history?"

---

## 4. Color Scheme & Theming

### 4.1 Primary Colors

| Element | Color | Hex | Usage |
|---------|-------|-----|-------|
| **Primary Blue** | Blue | `#2196f3` | CALL, MIN ALL, MAX ALL |
| **Success Green** | Green | `#4caf50` | CHECK, confirmed actions, live indicator |
| **Danger Red** | Red | `#f44336` | FOLD, CASHOUT, critical actions |
| **Warning Orange** | Orange | `#ff9800` | MAX, BET, pending states |
| **Gold** | Yellow | `#ffc107` | Pot, dealer marker, ARM CASHOUT |
| **Purple** | Purple | `#9c27b0` | Check/Call pre-action, ARM button |
| **Gray** | Gray | `#607d8b` | MIN button, disabled states, empty seats |

### 4.2 Background Gradient

**Body:**
```css
background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
```

**Overlay Transparency:**
- Header: `rgba(0, 0, 0, 0.3)`
- Table Container: `rgba(0, 0, 0, 0.4)`
- Seat Cards: `rgba(255, 255, 255, 0.15)`
- Board Display: `rgba(255, 255, 255, 0.1)`

### 4.3 4-Color Deck (Inverted)

**Card Suit Colors:**
- ♥ Hearts: **Red** `#ff0000`
- ♦ Diamonds: **Blue** `#0066ff`
- ♣ Clubs: **Green** `#00aa00`
- ♠ Spades: **Black** `#000000`

**Rationale:** Easier to distinguish suits at a glance, reduces misreads

---

## 5. Responsive Design

### 5.1 Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Desktop | ≥1200px | 3×3 seat grid, right sidebar |
| Tablet | 768-1199px | 2×5 seat grid, bottom action bar |
| Mobile | <768px | 1-column stack, collapsible panels |

### 5.2 Seat Grid Responsive

**Desktop (≥1200px):**
```css
.seats-grid {
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
}
```

**Tablet (768-1199px):**
```css
.seats-grid {
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
```

**Mobile (<768px):**
```css
.seats-grid {
  grid-template-columns: 1fr;
  gap: 8px;
}
```

### 5.3 Advanced Actions Panel Responsive

**Desktop:** Right sidebar (30% width)  
**Tablet:** Bottom fixed bar (buttons in row)  
**Mobile:** Collapsible drawer (swipe up to expand)

---

## 6. Interaction Patterns

### 6.1 Button Click Flow

**Standard Action Button:**
1. User clicks button (e.g., CALL)
2. Button disabled + loading spinner (200ms)
3. POST request to `/api/commands/queue`
4. Response received:
   - Success: Button re-enabled, command added to log
   - Error: Button re-enabled, error toast shown
5. Seat card shows pending badge: "⏳ call"
6. Command log updated: "12:34 | S0 | call | PENDING"

**Pre-Action Checkbox:**
1. User checks "Check/Fold"
2. Other checkbox ("Check/Call") auto-unchecks
3. POST request with `pre_action_check_fold`
4. Checkbox border changes to green (confirmed)
5. On uncheck: POST `clear_preaction`

**Bet Slider:**
1. User clicks BET button
2. Slider appears below action buttons
3. User drags slider to desired amount
4. Value display updates in real-time
5. User clicks CONFIRM:
   - POST `bet_custom` with value
   - Slider collapses
6. User clicks CANCEL:
   - Slider collapses, no action

### 6.2 Global Action Flow

**MIN ALL / MAX ALL:**
1. User clicks MIN ALL
2. Confirmation modal: "Set MIN bet on all 6 active seats?"
3. If confirmed:
   - POST `/api/commands/queue-batch` with seat_indices
   - All active seats get pending badge
   - Command log shows 6 entries
4. If canceled: No action

**BET / EXECUTE:**
1. User sets custom bets on 3 seats (via BET slider)
2. 3 seats show pending badges: "⏳ bet_custom (25.00)"
3. User clicks BET / EXECUTE
4. Confirmation modal: "Execute 3 pending bets?"
5. If confirmed:
   - POST `/api/commands/execute-all`
   - All 3 bets transition to "EXECUTING" status
   - n4p.js polls and executes bets in browser
6. If canceled: Bets remain queued

**CASHOUT ALL:**
1. User checks "ARM CASHOUT ALL" checkbox
2. CASHOUT ALL button turns bright red + pulsing glow
3. User clicks CASHOUT ALL
4. **Double confirmation:**
   - Modal 1: "Are you sure? This will cash out ALL 9 players."
   - Modal 2: "Type 'CASHOUT' to confirm"
5. If confirmed:
   - POST `/api/commands/cashout-all` with `confirm: true`
   - All seats get CASHOUT command
   - ARM checkbox auto-unchecks
6. If canceled: ARM remains checked, no action

### 6.3 Polling & Real-Time Updates

**Table State Polling:**
- **Endpoint:** GET `/api/table/latest`
- **Interval:** 1000ms (1 second)
- **On Success:** 
  - Update all seat cards
  - Update board display
  - Update pot
- **On Error:** 
  - Show "Waiting for table..." message
  - Display empty 9-seat grid

**Hand Log Polling:**
- **Endpoint:** GET `/api/hands/recent?limit=20`
- **Interval:** 2000ms (2 seconds)
- **On Update:** 
  - Append new hands to textarea
  - Auto-scroll to bottom

**Command Log Refresh:**
- **Trigger:** After any command is queued
- **Action:** Prepend new entry to log (max 20 entries)

---

## 7. State Management

### 7.1 Seat State Model

```javascript
{
  seatNo: 0,                    // 0-8
  name: "Player1",              // or null
  stack: 200.00,                // ZAR
  occupied: true,               // has player
  active: true,                 // status === 'playing'
  pending: true,                // has pending command
  pendingCmd: "raise_max",      // command type
  error: null,                  // command error message
  stale: false,                 // last_seen_ago > 30s
  holeCards: ["Ah", "Kh", "Qh", "Jh"],
  isDealer: false,
  isHero: true,                 // this is your seat (local player)
  canAct: true                  // occupied && active && !stale
}
```

### 7.2 Global UI State

```javascript
{
  armCashoutAll: false,         // ARM CASHOUT ALL checkbox state
  activeBetSlider: null,        // seat index with open bet slider, or null
  pendingBetCount: 0,           // count of seats with pending bet_custom
  commandLogEntries: [],        // last 20 command log entries
  handLogContent: "",           // raw hand log text
  lastPollTime: 1712400000      // timestamp of last successful poll
}
```

### 7.3 State Transitions

**Seat State Flow:**
```
EMPTY → OCCUPIED (player joins)
OCCUPIED → ACTIVE (hand starts, player in hand)
ACTIVE → PENDING (command queued)
PENDING → ACTIVE (command executed/acked)
ACTIVE → OCCUPIED (hand ends, player out of hand)
OCCUPIED → STALE (connection lost, no snapshot >30s)
STALE → OCCUPIED (connection restored)
OCCUPIED → EMPTY (player leaves table)
```

**Command State Flow:**
```
(User clicks button)
  ↓
QUEUED → sent to backend
  ↓
PENDING → waiting for n4p.js poll
  ↓
EXECUTING → n4p.js executing in browser
  ↓
ACKED → command completed successfully
  or
FAILED → command execution failed
```

---

## 8. Accessibility

### 8.1 Keyboard Navigation

- **Tab Order:** Header → Hand Log → Board → Seats (0-8) → Advanced Actions
- **Seat Focus:** Highlight border + shadow on focus
- **Button Focus:** Blue outline 2px
- **Keyboard Shortcuts:**
  - `F` = FOLD (on focused seat)
  - `K` = CHECK (on focused seat)
  - `C` = CALL (on focused seat)
  - `M` = MIN (on focused seat)
  - `X` = MAX (on focused seat)
  - `Space` = Confirm bet slider
  - `Esc` = Cancel bet slider / close modals

### 8.2 Screen Reader Support

- **ARIA Labels:**
  - Seat cards: `aria-label="Seat 0, Player1, Stack 200 ZAR, Status Active"`
  - Action buttons: `aria-label="Fold hand"`
  - Status dots: `aria-label="Player connected"` / `"Player offline"`
- **Live Regions:**
  - Command log: `aria-live="polite"` (announce new commands)
  - Pot display: `aria-live="polite"` (announce pot changes)

### 8.3 Color Contrast

- **Text on Dark Background:** Minimum 4.5:1 contrast ratio
- **Button Text:** Minimum 7:1 contrast ratio
- **Status Indicators:** Use icons + color (not color alone)

---

## 9. Error States & Feedback

### 9.1 Network Error

**Display:** Toast notification (top-right)
```
┌─────────────────────────────────┐
│ ⚠️ Connection lost             │
│ Retrying in 5 seconds...        │
└─────────────────────────────────┘
```

**Seat Card Behavior:**
- All borders change to red (stale state)
- All buttons disabled
- Status text: "DISCONNECTED"

### 9.2 Command Failure

**Display:** Toast notification + log entry
```
┌─────────────────────────────────┐
│ ❌ Command failed: raise_max    │
│ Reason: Not enough chips        │
└─────────────────────────────────┘
```

**Command Log:**
```
12:34 | S0 | raise_max | FAILED (Not enough chips)
```

**Seat Card Behavior:**
- Pending badge changes to red: "❌ raise_max"
- Badge auto-clears after 5 seconds

### 9.3 API Timeout

**Threshold:** 5 seconds  
**Display:** Loading spinner on affected button  
**Fallback:** After 5s, re-enable button and show error toast

---

## 10. Future Enhancements (Phase 2)

### 10.1 WebSocket Support

Replace polling with WebSocket for real-time updates:
- Instant command acknowledgment
- Live pot updates during betting
- Reduced server load

### 10.2 Multi-Table Support

Display multiple tables in tabs:
- Tab bar at top: [Table 1] [Table 2] [Table 3]
- Switch between tables without page reload
- Aggregate command log across all tables

### 10.3 Hand Replay

Click on hand log entry to open replay modal:
- Step through hand action by action
- Visual animation of cards dealt
- Pot size updates per street

### 10.4 Seat Presets

Save and load seat action templates:
- "Tight-Aggressive": Auto-fold <JJ, auto-raise AA/KK
- "Passive": Auto-check/call everything
- "Emergency Exit": Auto-cashout all seats

---

## Summary

This UI specification provides:
- Complete visual layout with ASCII diagrams
- Detailed component hierarchy
- Exact dimensions, colors, and spacing
- Responsive breakpoints (desktop/tablet/mobile)
- Interaction patterns and state flows
- Accessibility guidelines
- Error handling UI

**Next Steps:**
1. Review this spec with stakeholders
2. Create high-fidelity mockups in Figma (optional)
3. Implement HTML/CSS based on this spec
4. Wire up JavaScript event handlers
5. Test on multiple devices and screen sizes

**Estimated Implementation Time:** 2-3 days (frontend only)
