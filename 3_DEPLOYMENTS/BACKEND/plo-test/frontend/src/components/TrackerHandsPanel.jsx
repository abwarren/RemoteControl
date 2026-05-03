// TrackerHandsPanel.jsx
// localStorage-backed persistent tracker hand list
//
// Frontend ledger schema (one record per sample):
// {
//   id:                    string   -- same as sample_id, dedup key
//   sample_id:             string   -- "sample-id00001", shown in UI
//   handtracker_id:        string   -- "handtracker-00001", stored only (not shown)
//   player_name:           string   -- hero display name
//   hole_cards:            string[] -- hero hole cards as 2-char tokens
//   flop_from_player1:     string   -- board sourced from player1 container ("AhKhQh")
//   flop_from_last_player: string   -- board sourced from last player container
//   variant:               string
//   timestamp_utc:         string   -- ISO-8601
//   total_zar:             number   -- sum of all player ZAR, locked at sample time
//   validated:             boolean  -- true only when received from API (d.persisted=true)
//   locked:                boolean  -- true once stored; record is immutable after this
//   state:                 string   -- "validated" | "collecting"
//   render_mode:           string   -- "icons" (validated) | "text" (collecting)
// }
//
// Rendering rules:
//   state="validated",  render_mode="icons"  => hole cards render as CardChip icons
//   state="collecting", render_mode="text"   => hole cards render as plain text tokens
//
// Flop rules:
//   - Flop is rendered ONLY when locked/validated
//   - Lock condition: flop_from_player1 === flop_from_last_player AND flopTokens.length === 3
//   - Locked flop renders as 3 CardIcon icons with class "locked-flop"
//   - If lock condition is false: NO flop section is rendered at all
//   - There is no text fallback, no partial flop, no collecting-mode flop
//
// Lock rules:
//   - total_zar is calculated once (at addTrackedHand call) and never changed
//   - sample_id is the only ID shown in the UI
//   - handtracker_id is stored for backend linkage but not rendered
//   - only validated samples (validated=true) can overwrite the current sample

import { useEffect, useState } from 'react'
import { CardChip } from './CardChip.jsx'
import { parseVariant } from '../variantRules.js'

const LEDGER_KEY         = 'tracker_hands'
const CURRENT_SAMPLE_KEY = 'tracker_current_sample'
const MAX_HANDS          = 200

/* -- Ledger storage ---------------------------------------------------- */
function loadLedger() {
  try {
    const raw = localStorage.getItem(LEDGER_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function saveLedger(hands) {
  try { localStorage.setItem(LEDGER_KEY, JSON.stringify(hands)) } catch {}
}

/* -- Current sample storage -------------------------------------------- */
function loadCurrentSample() {
  try {
    const raw = localStorage.getItem(CURRENT_SAMPLE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function saveCurrentSample(sample) {
  try { localStorage.setItem(CURRENT_SAMPLE_KEY, JSON.stringify(sample)) } catch {}
}

/* -- lock_current_frontend_sample --------------------------------------
   Sets state="validated", render_mode="icons", locked=true.
   Writes to current sample slot. A locked record is never mutated.
   Returns the locked record.
----------------------------------------------------------------------- */
function lockCurrentFrontendSample(sample) {
  const locked = {
    ...sample,
    state:       'validated',
    render_mode: 'icons',
    locked:      true,
  }
  saveCurrentSample(locked)
  window.dispatchEvent(new Event('tracker_current_sample_locked'))
  return locked
}

/* -- should_overwrite_current_sample -----------------------------------
   Returns true only when safe to replace the current sample:
     - no current sample exists yet, OR
     - the candidate is validated (from API, d.persisted=true) and
       has a server-assigned sample_id
   Partial or unvalidated data must never overwrite a valid sample.
----------------------------------------------------------------------- */
function shouldOverwriteCurrentSample(newCandidate) {
  const current = loadCurrentSample()
  if (!current) return true
  if (!newCandidate.validated) return false
  if (!newCandidate.sample_id) return false
  return true
}

/* -- store_frontend_ledger ---------------------------------------------
   Prepend to ledger, trim to MAX_HANDS, dedup by id, fire event.
----------------------------------------------------------------------- */
function storeFrontendLedger(sample) {
  const ledger = loadLedger()
  if (ledger.find(h => h.id === sample.id)) return
  const updated = [sample, ...ledger].slice(0, MAX_HANDS)
  saveLedger(updated)
  window.dispatchEvent(new Event('tracker_hand_added'))
}

/* -- addTrackedHand ----------------------------------------------------
   Public entry point called by tracker_v2.js after a successful POST.

   Pipeline:
     1. Build immutable record with state/render_mode decided by validated flag
     2. Check shouldOverwriteCurrentSample  -- reject if guard fails
     3. lockCurrentFrontendSample           -- state="validated", render_mode="icons"
     4. storeFrontendLedger                 -- prepend, fire event

   If validation_passed => state="validated", render_mode="icons"
   Else                 => state="collecting", render_mode="text"
   (In practice addTrackedHand is only called when validated=true,
    so collecting state is the pre-call / fallback path.)
----------------------------------------------------------------------- */
export function addTrackedHand(hand) {
  if (!hand || !hand.id) return

  const isValidated = hand.validated === true

  // Derive variant rules before building the record — mandatory gate
  let rules = null
  try {
    rules = parseVariant(hand.variant || 'plo5-6max')
  } catch {
    // Unrecognised variant key: fall back to plo5-6max rules so storage still works
    rules = parseVariant('plo5-6max')
  }

  const record = {
    id:                    hand.id,
    sample_id:             hand.sample_id             || hand.id,
    handtracker_id:        hand.handtracker_id         || null,
    player_name:           hand.player_name            || '?',
    hole_cards:            hand.hole_cards             || [],
    flop_from_player1:     hand.flop_from_player1      || '',
    flop_from_last_player: hand.flop_from_last_player  || '',
    variant:               hand.variant                || '',
    timestamp_utc:         hand.timestamp_utc          || new Date().toISOString(),
    total_zar:             typeof hand.total_zar === 'number' ? hand.total_zar : null,
    validated:             isValidated,
    // State and render_mode are set provisionally here;
    // lockCurrentFrontendSample will overwrite to "validated"/"icons" if guard passes.
    state:       isValidated ? 'validated'  : 'collecting',
    render_mode: isValidated ? 'icons'      : 'text',
    locked:      false,
  }

  if (!shouldOverwriteCurrentSample(record)) return

  const locked = lockCurrentFrontendSample(record)
  storeFrontendLedger(locked)
}

export function clearTrackedHands() {
  localStorage.removeItem(LEDGER_KEY)
  localStorage.removeItem(CURRENT_SAMPLE_KEY)
}

/* -- Card token helpers ------------------------------------------------ */

// Split a 10-char hand string or 6-char flop string into ["Ah","Kd",...] tokens
function splitCardString(str) {
  if (!str) return []
  const tokens = []
  for (let i = 0; i + 1 < str.length; i += 2) tokens.push(str.slice(i, i + 2))
  return tokens
}

// Render a card token as a chip icon (validated state)
function CardIcon({ card }) {
  return <CardChip rank={card.slice(0, -1)} suit={card.slice(-1).toLowerCase()} />
}

// Render a card token as plain text (collecting state — hole cards only)
function CardText({ card }) {
  return <span className="tracker-card-text">{card}</span>
}

/* -- Component --------------------------------------------------------- */
export default function TrackerHandsPanel() {
  const [hands, setHands]         = useState([])
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    const refresh = () => setHands(loadLedger())
    refresh()
    window.addEventListener('tracker_hand_added', refresh)
    window.addEventListener('tracker_current_sample_locked', refresh)
    return () => {
      window.removeEventListener('tracker_hand_added', refresh)
      window.removeEventListener('tracker_current_sample_locked', refresh)
    }
  }, [])

  const remove = (id) => {
    const updated = loadLedger().filter(h => h.id !== id)
    saveLedger(updated)
    setHands(updated)
  }

  const clearAll = () => {
    clearTrackedHands()
    setHands([])
  }

  if (hands.length === 0) return null

  return (
    <div className="tracker-panel">
      <div className="tracker-panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="tracker-panel-title">TRACKED HANDS</span>
          <span className="tracker-count">{hands.length}</span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => setCollapsed(c => !c)}>
            {collapsed ? 'Show' : 'Hide'}
          </button>
          <button className="btn btn-danger btn-sm" onClick={clearAll}>
            Clear All
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="tracker-hand-list">
          {hands.map(hand => {
            const useIcons = hand.render_mode === 'icons'
            const holeTokens = hand.hole_cards || []
            const flopTokens = splitCardString(hand.flop_from_player1)

            // Flop is locked only when both cross-auth values exist,
            // are identical, and produce exactly 3 parsed cards.
            const lockedFlop =
              !!hand.flop_from_player1 &&
              !!hand.flop_from_last_player &&
              hand.flop_from_player1 === hand.flop_from_last_player &&
              flopTokens.length === 3

            return (
              <div
                key={hand.id}
                className={[
                  'tracker-hand-card',
                  hand.locked    ? 'locked'    : '',
                  hand.validated ? 'validated' : '',
                ].filter(Boolean).join(' ')}
              >
                {/* Header row */}
                <div className="tracker-hand-top">
                  <span className="tracker-player">{hand.player_name}</span>
                  <span className="tracker-variant">{hand.variant}</span>
                  <span className={`tracker-state-badge ${hand.state || 'collecting'}`}>
                    {hand.state || 'collecting'}
                  </span>
                  <span className="tracker-time">
                    {new Date(hand.timestamp_utc).toLocaleTimeString()}
                  </span>
                  <button
                    className="tracker-remove"
                    onClick={() => remove(hand.id)}
                    title="Remove"
                  >x</button>
                </div>

                {/* Hole cards -- icons when validated, text when collecting */}
                <div className="tracker-cards">
                  {holeTokens.map((c, i) =>
                    useIcons
                      ? <CardIcon key={i} card={c} />
                      : <CardText key={i} card={c} />
                  )}
                </div>

                {/* Flop -- rendered ONLY when locked (cross-auth validated, 3 cards) */}
                {lockedFlop && (
                  <div className="tracker-flop locked-flop">
                    <span className="tracker-flop-label">BOARD</span>
                    <div className="tracker-flop-cards">
                      {flopTokens.map((c, i) => (
                        <CardIcon key={i} card={c} />
                      ))}
                    </div>
                  </div>
                )}

                {/* sample_id -- frontend ID only */}
                {hand.sample_id && (
                  <div className="tracker-sample-id">{hand.sample_id}</div>
                )}

                {/* total_zar -- locked at sample time */}
                {hand.total_zar !== null && hand.total_zar !== undefined && (
                  <div className="tracker-zar">
                    ZAR {hand.total_zar.toLocaleString('en-ZA', {
                      minimumFractionDigits: 0,
                      maximumFractionDigits: 2,
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
