// App.jsx — main application shell with tab navigation
import { useState, useEffect, useRef, useCallback } from 'react'
import { io } from 'socket.io-client'
import EngineTab          from './components/EngineTab.jsx'
import ValidatorTab       from './components/ValidatorTab.jsx'
import CollabTab          from './components/CollabTab.jsx'
import TrackerHandsPanel, { addTrackedHand } from './components/TrackerHandsPanel.jsx'
import LoginScreen        from './components/LoginScreen.jsx'
import RNGTab             from './components/RNGTab.jsx'
import TrackerScriptTab   from './components/TrackerScriptTab.jsx'
import BatchTab          from './components/BatchTab.jsx'
import ParserTab         from './components/ParserTab.jsx'
import AIMLTab           from './components/AIMLTab.jsx'
import RemoteTab         from './components/RemoteTab.jsx'

const TABS = [
  { id: 'engine',    label: '▶  Engine' },
  { id: 'validator', label: '✓  Validator' },
  { id: 'rng',       label: '⚄  RNG' },
  { id: 'collab',    label: '⟳  Collaborate' },
  { id: 'tracker',   label: '⊙  Tracker' },
    { id: 'batch',    label: '⚡  Batch' },
  { id: 'parser',   label: '⊞  Parser' },
  { id: 'aiml',     label: '🧠  AI / ML' },
  { id: 'remote',   label: '📡  Remote' },
]

export default function App() {
  // ── Auth state ────────────────────────────────────────────────────────────
  const [authToken,    setAuthToken]    = useState(() => localStorage.getItem('auth_token')    || '')
  const [authUsername, setAuthUsername] = useState(() => localStorage.getItem('auth_username') || '')
  const [authChecked,  setAuthChecked]  = useState(false)

  // ── App state (always declared — hooks must never be conditional) ──────────────
  const params     = new URLSearchParams(window.location.search)
  const hasSession = params.has('s')
  const redirectTab = params.get('redirect')
  const initialTab = redirectTab && TABS.some(t => t.id === redirectTab) ? redirectTab
                   : hasSession ? 'collab' : 'engine'
  const [tab, setTab] = useState(initialTab)

  const [sharedState, setSharedState] = useState({
    variant: 'plo5-6max',
    hands:   '',
    names:   '',
  })

  const [scannerStatus, setScannerStatus] = useState(null)

  // ── Verify stored token on mount ─────────────────────────────────────────
  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (!token) { setAuthChecked(true); return }
    fetch('/api/auth/verify', { headers: { 'X-Auth-Token': token } })
      .then(r => r.json())
      .then(d => {
        if (d.ok) {
          setAuthToken(token)
          setAuthUsername(d.username)
        } else {
          localStorage.removeItem('auth_token')
          localStorage.removeItem('auth_username')
          setAuthToken('')
          setAuthUsername('')
        }
      })
      .catch(() => {})
      .finally(() => setAuthChecked(true))
  }, [])

  // ── SocketIO scanner listener ──────────────────────────────────────────
  useEffect(() => {
    if (!authToken) return   // don't connect socket until logged in
    const socket = io(window.location.origin, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    })
    socket.on('scanner_cards', (data) => {
      console.log('[App socket] scanner_cards received source=', data.source, 'raw=', JSON.stringify(data.raw))
      if (data.raw && data.raw.trim()) {
        // Only update the textarea for aggregate events (complete hand set) or
        // non-tracker scanner events. Individual per-player tracker events
        // (source: 'tracker') have raw: '' so they never reach here — but guard
        // explicitly so partial data can never overwrite a complete set.
        const isTrackerAggregate = data.source === 'tracker_aggregate'
        const isTrackerDirect    = data.source === 'tracker'
        const isNonTracker       = !data.source || !data.source.startsWith('tracker')
        console.log('[App socket] flags:', { isTrackerAggregate, isTrackerDirect, isNonTracker })
        if (isTrackerAggregate || isTrackerDirect || isNonTracker) {
          console.log('[App socket] calling setSharedState with hands:', data.raw)
          setSharedState(prev => ({ ...prev, hands: data.raw }))
        }
        setScannerStatus(`Table ${data.table_id}`)
      } else {
        setScannerStatus(`Table ${data.table_id} cleared`)
      }
            if (data.source === 'tracker' && data.validated && data.player_name) {
        // Use server-provided hole_cards array if available, else parse from raw
        const holeCards = Array.isArray(data.hole_cards) && data.hole_cards.length > 0
          ? data.hole_cards
          : (data.raw ? data.raw.split('\n')[0] : '').match(/.{2}/g) || []
        addTrackedHand({
          id:                    data.sample_id || (data.timestamp + '-' + data.player_name),
          sample_id:             data.sample_id || null,
          handtracker_id:        data.handtracker_id || null,
          player_name:           data.player_name,
          hole_cards:            holeCards,
          flop_from_player1:     data.flop_from_player1 || '',
          flop_from_last_player: data.flop_from_last_player || '',
          variant:               data.variant || 'unknown',
          timestamp_utc:         new Date().toISOString(),
          total_zar:             typeof data.total_zar === 'number' ? data.total_zar : null,
          validated:             true,
        })
        // Auto-populate Player1 name from tracker in shared state
        setSharedState(prev => {
          const existingNames = prev.names || ''
          // Parse existing names, set Player1 to the tracker player name
          const lines = existingNames.split('\n').filter(l => l.trim() && !l.startsWith('Player1='))
          const updated = [`Player1=${data.player_name}`, ...lines].join('\n')
          return { ...prev, names: updated }
        })
      }
    })
    return () => socket.disconnect()
  }, [authToken])

  // ── Auth helpers ───────────────────────────────────────────────────────────
  const handleLogout = useCallback(async (reason = 'manual') => {
    await fetch('/api/logout', {
      method:  'POST',
      headers: { 'X-Auth-Token': localStorage.getItem('auth_token') || '' },
    }).catch(() => {})
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_username')
    setAuthToken('')
    setAuthUsername('')
    if (reason === 'inactivity') {
      // Brief visual cue before login screen appears
      console.info('[Auth] Session expired due to inactivity')
    }
  }, [])

  const handleLogin = (token, username) => {
    setAuthToken(token)
    setAuthUsername(username)
    setAuthChecked(true)
  }

  // ── Inactivity timeout (5 min) ─────────────────────────────────────────────
  const INACTIVITY_MS  = 5 * 60 * 1000   // 5 minutes
  const inactivityRef  = useRef(null)
  const [countdown, setCountdown] = useState(null)   // seconds remaining in warning
  const countdownRef   = useRef(null)
  const WARN_BEFORE_MS = 30 * 1000   // show warning 30 s before logout

  const clearCountdown = useCallback(() => {
    clearInterval(countdownRef.current)
    countdownRef.current = null
    setCountdown(null)
  }, [])

  const resetInactivity = useCallback(() => {
    if (!localStorage.getItem('auth_token')) return
    clearTimeout(inactivityRef.current)
    clearCountdown()
    // Warn 30 s before logout
    inactivityRef.current = setTimeout(() => {
      let secs = Math.round(WARN_BEFORE_MS / 1000)
      setCountdown(secs)
      countdownRef.current = setInterval(() => {
        secs -= 1
        setCountdown(secs)
        if (secs <= 0) {
          clearCountdown()
          handleLogout('inactivity')
        }
      }, 1000)
    }, INACTIVITY_MS - WARN_BEFORE_MS)
  }, [handleLogout, clearCountdown])

  useEffect(() => {
    if (!authToken) { clearTimeout(inactivityRef.current); clearCountdown(); return }
    const EVENTS = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll', 'click']
    EVENTS.forEach(e => window.addEventListener(e, resetInactivity, { passive: true }))
    resetInactivity()   // start timer on login
    return () => {
      EVENTS.forEach(e => window.removeEventListener(e, resetInactivity))
      clearTimeout(inactivityRef.current)
      clearCountdown()
    }
  }, [authToken, resetInactivity, clearCountdown])

  // (engine_flow_controls.js removed — no overlay cleanup needed)

  // ── Render gates (after all hooks) ─────────────────────────────────────────
  if (!authChecked) return null
  if (!authToken)   return <LoginScreen onLogin={handleLogin} />

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="app-logo">
          PLO Equity Engine
          <span>potlimitomaha.xyz</span>
        </div>
        {/* User badge + logout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            fontFamily: 'var(--mono)',
            fontSize: 11,
            color: 'var(--text-muted)',
            letterSpacing: 1,
          }}>
            {authUsername}
          </span>
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleLogout}
            style={{ fontSize: 10, padding: '4px 10px' }}
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* ── Tab bar ── */}
      <nav className="tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`tab-btn ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {/* ── Persistent Tracker Hands Panel ── */}
      <TrackerHandsPanel />

      {/* ── Tab content ── */}
      <main className="tab-content">
        {tab === 'engine'    && (
          <EngineTab
            initialState={sharedState}
            onStateChange={s => setSharedState(prev => ({ ...prev, ...s }))}
          />
        )}
        {tab === 'validator' && (
          <ValidatorTab
            sharedState={sharedState}
            onStateChange={s => setSharedState(prev => ({ ...prev, ...s }))}
            scannerStatus={scannerStatus}
          />
        )}
        {tab === 'collab'    && <CollabTab />}
        {tab === 'rng'       && (
          <RNGTab
            onSendToEngine={({ hands, variant }) => {
              setSharedState(prev => ({ ...prev, hands, variant }))
              setTab('engine')
            }}
          />
        )}
        {tab === 'tracker'  && <TrackerScriptTab />}
                {tab === 'batch'     && <BatchTab />}
        {tab === 'parser'    && <ParserTab />}
        {tab === 'aiml'      && <AIMLTab />}
        {tab === 'remote'    && <RemoteTab />}
      </main>
    </div>
  )
}
