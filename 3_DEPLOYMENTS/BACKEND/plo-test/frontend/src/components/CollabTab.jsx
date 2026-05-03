// CollabTab.jsx — Real-time collaborative session tab
import { useState, useEffect, useRef, useCallback } from 'react'
import { createSession, subscribeStream, fetchResults } from '../api.js'
import { useSocket } from '../useSocket.js'
import LiveLog from './LiveLog.jsx'
import ResultsTable from './ResultsTable.jsx'

const VARIANTS = [
  { value: 'plo4-6max', label: 'PLO4 · 6-Max' },
  { value: 'plo4-8max', label: 'PLO4 · 8-Max' },
  { value: 'plo4-9max', label: 'PLO4 · 9-Max' },
  { value: 'plo5-6max', label: 'PLO5 · 6-Max' },
  { value: 'plo6-5max', label: 'PLO6 · 5-Max' },
  { value: 'plo6-6max', label: 'PLO6 · 6-Max' },
  { value: 'plo7-5max', label: 'PLO7 · 5-Max' },
  { value: 'plo7-6max', label: 'PLO7 · 6-Max' },
]

export default function CollabTab() {
  const { emit, on, off, connected } = useSocket()

  // Session state
  const [sessionId,   setSessionId]   = useState('')
  const [joinInput,   setJoinInput]   = useState('')
  const [username,    setUsername]    = useState(() => `User_${Math.random().toString(36).slice(2,6)}`)
  const [inSession,   setInSession]   = useState(false)
  const [shareUrl,    setShareUrl]    = useState('')
  const [users,       setUsers]       = useState([])
  const [lastUpdated, setLastUpdated] = useState(null)
  const [copied,      setCopied]      = useState(false)

  // Shared fields
  const [variant,  setVariantLocal]  = useState('plo5-6max')
  const [hands,    setHandsLocal]    = useState('')
  const [names,    setNamesLocal]    = useState('')

  // Engine state
  const [logLines,  setLogLines]  = useState([])
  const [engineStatus, setEngineStatus] = useState('idle')
  const [results,  setResults]    = useState(null)
  const [view,     setView]       = useState('log')
  const [jobId,    setJobId]      = useState(null)
  const [engineBy, setEngineBy]   = useState(null)

  const sessionIdRef = useRef(sessionId)
  const usernameRef  = useRef(username)
  useEffect(() => { sessionIdRef.current = sessionId }, [sessionId])
  useEffect(() => { usernameRef.current  = username  }, [username])

  // ── Auto-join from URL param ─────────────────────────────────────────────
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const s = params.get('s')
    if (s) { setJoinInput(s); setSessionId(s) }
  }, [])

  // ── Socket.IO event handlers ─────────────────────────────────────────────
  useEffect(() => {
    if (!connected) return

    const handlers = {
      init_state: (state) => {
        setVariantLocal(state.variant || 'plo5-6max')
        setHandsLocal(state.hands    || '')
        setNamesLocal(state.names    || '')
        setUsers(state.users         || [])
      },
      field_updated: ({ field, value, updated_by }) => {
        if (field === 'variant') setVariantLocal(value)
        if (field === 'hands')   setHandsLocal(value)
        if (field === 'names')   setNamesLocal(value)
        setLastUpdated(updated_by)
      },
      user_joined: ({ users }) => setUsers(users),
      user_left:   ({ users }) => setUsers(users),
      engine_started: ({ job_id, started_by }) => {
        setJobId(job_id)
        setEngineBy(started_by)
        setEngineStatus('running')
        setLogLines([])
        setResults(null)
        setView('log')

        subscribeStream(job_id, {
          onLine: (line) => setLogLines(prev => [...prev, line]),
          onDone: async (code) => {
            setLogLines(prev => [...prev, `\n✓ Engine exited (code ${code})\n`])
            setEngineStatus(code === 0 ? 'done' : 'error')
            const res = await fetchResults(job_id)
            if (res.status === 'done' && res.data?.matchups?.length) {
              setResults(res.data)
              setView('results')
            }
          },
          onError: (msg) => {
            setLogLines(prev => [...prev, `\nERR: ${msg}\n`])
            setEngineStatus('error')
          },
        })
      },
    }

    Object.entries(handlers).forEach(([ev, fn]) => on(ev, fn))
    return () => Object.keys(handlers).forEach(ev => off(ev, handlers[ev]))
  }, [connected, on, off])

  // ── Session create / join ─────────────────────────────────────────────────
  const handleCreate = async () => {
    const data = await createSession()
    setSessionId(data.session_id)
    setShareUrl(data.share_url)
    joinRoom(data.session_id)
  }

  const handleJoin = () => {
    if (!joinInput.trim()) return
    setSessionId(joinInput.trim())
    setShareUrl(`${window.location.origin}?s=${joinInput.trim()}`)
    joinRoom(joinInput.trim())
  }

  const joinRoom = (sid) => {
    emit('join', { session_id: sid, username: usernameRef.current })
    setInSession(true)
    // Update URL without reload
    const url = new URL(window.location)
    url.searchParams.set('s', sid)
    window.history.replaceState({}, '', url)
  }

  const leaveSession = () => {
    emit('leave', { session_id: sessionIdRef.current, username: usernameRef.current })
    setInSession(false)
    setSessionId('')
    setShareUrl('')
    setUsers([])
    setLogLines([])
    setResults(null)
    setEngineStatus('idle')
    const url = new URL(window.location)
    url.searchParams.delete('s')
    window.history.replaceState({}, '', url)
  }

  // ── Broadcast field changes to room ──────────────────────────────────────
  const broadcastField = useCallback((field, value) => {
    if (!sessionIdRef.current) return
    emit('update_field', {
      session_id: sessionIdRef.current,
      field, value,
      username: usernameRef.current,
    })
  }, [emit])

  const setVariant = (v) => { setVariantLocal(v); broadcastField('variant', v) }
  const setHands   = (v) => { setHandsLocal(v);   broadcastField('hands', v) }
  const setNames   = (v) => { setNamesLocal(v);   broadcastField('names', v) }

  // ── Run engine for whole session ──────────────────────────────────────────
  const runEngine = () => {
    if (!hands.trim()) return
    emit('run_session_engine', {
      session_id: sessionIdRef.current,
      username:   usernameRef.current,
    })
  }

  const copyShare = () => {
    navigator.clipboard.writeText(shareUrl).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  // ── Pre-session UI ────────────────────────────────────────────────────────
  if (!inSession) {
    return (
      <div style={{ maxWidth: 480, margin: '40px auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="panel">
          <div className="panel-title">Your Name</div>
          <input
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            placeholder="Enter your display name"
          />
        </div>

        <div className="panel">
          <div className="panel-title">Create New Session</div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
            Start a shared session. Share the link with others to collaborate in real time.
          </p>
          <button className="btn btn-primary" style={{ width: '100%' }} onClick={handleCreate} disabled={!connected}>
            + Create Session
          </button>
        </div>

        <div className="panel">
          <div className="panel-title">Join Existing Session</div>
          <div className="fix-row">
            <input
              type="text"
              value={joinInput}
              onChange={e => setJoinInput(e.target.value)}
              placeholder="Session ID (e.g. a3f9k2p7)"
              onKeyDown={e => e.key === 'Enter' && handleJoin()}
            />
            <button className="btn btn-outline btn-sm" onClick={handleJoin} disabled={!joinInput.trim() || !connected}>
              Join
            </button>
          </div>
        </div>

        {!connected && (
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontSize: 11 }}>
            <span className="pulse">●</span> Connecting to server...
          </div>
        )}
      </div>
    )
  }

  // ── In-session UI ─────────────────────────────────────────────────────────
  return (
    <div className="collab-layout">
      {/* ── Sidebar ── */}
      <div className="collab-sidebar">
        {/* Session info */}
        <div className="panel">
          <div className="panel-title">Session</div>
          <div className="session-id-box">{sessionId}</div>
          {shareUrl && (
            <div style={{ marginTop: 8 }}>
              <div className="share-url">{shareUrl}</div>
              <button className="copy-btn" style={{ marginTop: 6, width: '100%' }} onClick={copyShare}>
                {copied ? '✓ Copied!' : '⎘ Copy Link'}
              </button>
            </div>
          )}
          <button className="btn btn-ghost btn-sm" style={{ width: '100%', marginTop: 8 }} onClick={leaveSession}>
            Leave Session
          </button>
        </div>

        {/* Users online */}
        <div className="panel">
          <div className="panel-title">Online ({users.length})</div>
          <div className="user-list">
            {users.map((u, i) => (
              <div key={i} className="user-pill">
                <span className={`user-dot ${u === username ? 'self' : ''}`} />
                <span>{u}{u === username ? ' (you)' : ''}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Variant */}
        <div className="panel">
          <div className="panel-title">Variant</div>
          <select value={variant} onChange={e => setVariant(e.target.value)}>
            {VARIANTS.map(v => (
              <option key={v.value} value={v.value}>{v.label}</option>
            ))}
          </select>
        </div>

        {/* Run button */}
        <button
          className="btn btn-primary"
          style={{ width: '100%' }}
          disabled={engineStatus === 'running' || !hands.trim()}
          onClick={runEngine}
        >
          {engineStatus === 'running' ? '⟳  Running...' : '▶  Run for All'}
        </button>

        {engineBy && engineStatus !== 'idle' && (
          <div className="collab-updated">Started by <span className="collab-tag">{engineBy}</span></div>
        )}
        {lastUpdated && (
          <div className="collab-updated">Last edit by <span className="collab-tag">{lastUpdated}</span></div>
        )}
      </div>

      {/* ── Main: shared inputs + output ── */}
      <div className="collab-main">
        <div className="panel">
          <div className="panel-title">Shared Hands File</div>
          <textarea
            rows={12}
            value={hands}
            onChange={e => setHands(e.target.value)}
            placeholder="All users see and edit this together..."
          />
        </div>

        <div className="panel">
          <div className="panel-title">Shared Name Mapping <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>(optional)</span></div>
          <textarea
            rows={4}
            value={names}
            onChange={e => setNames(e.target.value)}
            placeholder={'Player1=Hero\nPlayer2=Villain'}
          />
        </div>

        {/* Engine output */}
        {engineStatus !== 'idle' && (
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {engineStatus === 'running' && <span className="status-pill running"><span className="pulse">●</span> Running</span>}
                {engineStatus === 'done'    && <span className="status-pill done">✓ Done</span>}
                {engineStatus === 'error'   && <span className="status-pill error">✗ Error</span>}
              </div>
              {results && (
                <div className="view-toggle">
                  <button className={view === 'log'     ? 'active' : ''} onClick={() => setView('log')}>Log</button>
                  <button className={view === 'results' ? 'active' : ''} onClick={() => setView('results')}>Results</button>
                </div>
              )}
            </div>

            {view === 'log' || !results ? (
              <LiveLog lines={logLines} status={engineStatus} />
            ) : (
              <ResultsTable data={results} jobId={jobId} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
