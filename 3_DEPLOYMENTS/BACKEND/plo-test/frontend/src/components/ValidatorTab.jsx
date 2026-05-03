// ValidatorTab.jsx — Hand Validator tab
import { useState, useEffect, useRef } from 'react'
import { validateHands, fixCard } from '../api.js'
import { parseVariant } from '../variantRules.js'
import { HandChips } from './CardChip.jsx'
import { io } from 'socket.io-client'

const VARIANTS = [
  { value: 'plo4-6max', label: 'PLO4 · 6-Max' },
  { value: 'plo4-8max', label: 'PLO4 · 8-Max' },
  { value: 'plo4-9max', label: 'PLO4 · 9-Max' },
  { value: 'plo5-5max', label: 'PLO5 · 5-Max' },
  { value: 'plo5-6max', label: 'PLO5 · 6-Max' },
  { value: 'plo5-8max', label: 'PLO5 · 8-Max' },
  { value: 'plo5-9max', label: 'PLO5 · 9-Max' },
  { value: 'plo6-5max', label: 'PLO6 · 5-Max' },
  { value: 'plo6-6max', label: 'PLO6 · 6-Max' },
  { value: 'plo6-8max', label: 'PLO6 · 8-Max' },
  { value: 'plo7-5max', label: 'PLO7 · 5-Max' },
  { value: 'plo7-6max', label: 'PLO7 · 6-Max' },
]

function IssueCard({ issue, variant, hands, names, onFixed }) {
  const [replacement, setReplacement] = useState('')
  const [fixing, setFixing] = useState(false)
  const [err, setErr] = useState('')

  const applyFix = async (slot, position) => {
    setFixing(true); setErr('')
    const res = await fixCard({ variant, hands, names, slot, position, replacement })
    setFixing(false)
    if (res.error) { setErr(res.error); return }
    onFixed(res.hands)
    setReplacement('')
  }

  if (issue.type === 'malformed') {
    return (
      <div className="issue-card malformed">
        <div className="issue-title malformed">⚠ Malformed Token</div>
        <div className="issue-detail">
          Player {issue.slot + 1} · <strong>{issue.player_name}</strong>
          &nbsp;·&nbsp; position {issue.position + 1} &nbsp;·&nbsp;
          <code style={{ background: 'var(--surface)', padding: '1px 4px', borderRadius: 3 }}>{issue.token}</code>
          &nbsp;— {issue.detail}
        </div>
        <div className="issue-detail">
          Hand: <HandChips hand={issue.hand_raw} />
        </div>
        <div className="fix-row">
          <input
            type="text"
            placeholder="e.g. Ah"
            value={replacement}
            maxLength={3}
            onChange={e => setReplacement(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && applyFix(issue.slot, issue.position)}
          />
          <button
            className="btn btn-amber btn-sm"
            disabled={!replacement || fixing}
            onClick={() => applyFix(issue.slot, issue.position)}
          >
            {fixing ? '...' : 'Fix'}
          </button>
          {err && <span style={{ color: 'var(--red)', fontSize: 10 }}>{err}</span>}
        </div>
      </div>
    )
  }

  if (issue.type === 'duplicate') {
    return (
      <div className="issue-card duplicate">
        <div className="issue-title duplicate">✗ Duplicate Card</div>
        <div className="issue-detail" style={{ marginBottom: 8 }}>
          <HandChips hand={issue.card} /> appears in {issue.owners.length} hands
        </div>
        {issue.owners.map((owner, i) => (
          <div key={i} style={{ marginBottom: 8, paddingLeft: 8, borderLeft: '2px solid var(--border)' }}>
            <div className="issue-detail">
              Player {owner.slot + 1} · <strong>{owner.name}</strong>
              &nbsp;·&nbsp; position {owner.pos + 1}
              &nbsp;·&nbsp; <HandChips hand={owner.hand_raw} />
            </div>
            <div className="fix-row">
              <input
                type="text"
                placeholder="Replace with..."
                value={i === 0 ? replacement : ''}
                maxLength={3}
                onChange={e => setReplacement(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && applyFix(owner.slot, owner.pos)}
              />
              <button
                className="btn btn-danger btn-sm"
                disabled={!replacement || fixing}
                onClick={() => applyFix(owner.slot, owner.pos)}
              >
                {fixing ? '...' : `Fix P${owner.slot + 1}`}
              </button>
            </div>
          </div>
        ))}
        {err && <div style={{ color: 'var(--red)', fontSize: 10, marginTop: 4 }}>{err}</div>}
      </div>
    )
  }

  return null
}

// ── localStorage keys ───────────────────────────────────────────────────────
const LS_HANDS   = 'validator_hands'
const LS_NAMES   = 'validator_names'
const LS_VARIANT = 'validator_variant'

function lsGet(key, fallback = '') {
  try { return localStorage.getItem(key) ?? fallback } catch { return fallback }
}
function lsSet(key, value) {
  try { localStorage.setItem(key, value) } catch {}
}

export default function ValidatorTab({ sharedState = {}, onStateChange, scannerStatus }) {
  // Initialise from localStorage first, then fall back to sharedState / default
  const [variant,  setVariant]  = useState(() => lsGet(LS_VARIANT, sharedState.variant || 'plo5-6max'))
  const [hands,    setHands]    = useState(() => lsGet(LS_HANDS,   sharedState.hands   || ''))
  const [names,    setNames]    = useState(() => lsGet(LS_NAMES,   sharedState.names   || ''))

  // Track whether the scanner has pushed new data (so we can prefer scanner over stale localStorage)
  const scannerPushed = useRef(false)
  const [result,   setResult]   = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')
  const [socketConnected, setSocketConnected] = useState(false)
  const [launchingPokerReader, setLaunchingPokerReader] = useState(false)
  const [launchStatus, setLaunchStatus] = useState(null)
  const [pokerReaderPath, setPokerReaderPath] = useState(() => {
    return localStorage.getItem('pokerReaderPath') || 'C:\\Users\\pc\\Desktop\\PokerReader\\PokerReader.exe'
  })
  const [showPathConfig, setShowPathConfig] = useState(false)
  const [playerCount, setPlayerCount] = useState(() => {
    const config = {
      'plo4-6max': 6, 'plo4-8max': 8, 'plo4-9max': 9,
      'plo5-5max': 5, 'plo5-6max': 6, 'plo5-8max': 8, 'plo5-9max': 9,
      'plo6-5max': 5, 'plo6-6max': 6, 'plo6-8max': 8,
      'plo7-5max': 5, 'plo7-6max': 6,
    }
    return config[sharedState.variant || 'plo5-6max'] || 6
  })

  // Persist hands/names/variant to localStorage whenever they change
  useEffect(() => { lsSet(LS_HANDS,   hands)   }, [hands])
  useEffect(() => { lsSet(LS_NAMES,   names)   }, [names])
  useEffect(() => { lsSet(LS_VARIANT, variant) }, [variant])

  // Sync from sharedState when scanner pushes new data (takes priority over localStorage)
  useEffect(() => {
    if (sharedState.hands !== undefined && sharedState.hands !== '') {
      scannerPushed.current = true
      setHands(sharedState.hands)
    }
    if (sharedState.variant) {
      setVariant(sharedState.variant)
      // Update player count when variant changes
      const config = {
        'plo4-6max': 6, 'plo4-8max': 8, 'plo4-9max': 9, 'plo5-6max': 6,
        'plo6-5max': 5, 'plo6-6max': 6, 'plo7-5max': 5, 'plo7-6max': 6,
      }
      setPlayerCount(config[sharedState.variant] || 6)
    }
  }, [sharedState.hands, sharedState.variant])

  // Socket connection for PokerReader launcher status
  useEffect(() => {
    const socket = io(window.location.origin, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    })

    socket.on('connect', () => {
      setSocketConnected(true)
    })

    socket.on('disconnect', () => {
      setSocketConnected(false)
    })

    return () => {
      socket.disconnect()
    }
  }, [])

  const updateHands = (newHands) => {
    setHands(newHands)
    onStateChange?.({ hands: newHands })
  }

  const updateNames = (newNames) => {
    setNames(newNames)
    onStateChange?.({ names: newNames })
  }

  const updatePokerReaderPath = (newPath) => {
    setPokerReaderPath(newPath)
    localStorage.setItem('pokerReaderPath', newPath)
  }

  const validate = async () => {
    if (!hands.trim()) return
    setLoading(true); setError(''); setResult(null)
    const res = await validateHands({ variant, hands, names })
    setLoading(false)
    if (res.error) { setError(res.error); return }
    setResult(res)
  }

  const onFixed = (newHands) => {
    updateHands(newHands)
    // Re-run validation after fix
    validateHands({ variant, hands: newHands, names }).then(res => {
      if (!res.error) setResult(res)
    })
  }

  // Derive all structural rules from the active variant — single source of truth
  const rules = (() => {
    try { return parseVariant(variant) } catch { return parseVariant('plo5-6max') }
  })()

  // Get player count for variant — derived from rules, not a hardcoded map
  const getPlayerCount = () => rules.players

  // Convert names object to/from Player1=Name format
  const parseNamesFromText = (text) => {
    const map = {}
    text.split('\n').forEach(line => {
      if (line.includes('=')) {
        const [key, val] = line.split('=').map(s => s.trim())
        if (key && val) map[key] = val
      }
    })
    return map
  }

  const getNamesAsText = () => {
    return Object.entries(parseNamesFromText(names))
      .map(([k, v]) => `${k}=${v}`)
      .join('\n')
  }

  const handlePlayerNameChange = (playerNum, value) => {
    const map = parseNamesFromText(names)
    const key = `Player${playerNum}`
    if (value.trim()) {
      map[key] = value
    } else {
      delete map[key]
    }
    const text = Object.entries(map).map(([k, v]) => `${k}=${v}`).join('\n')
    updateNames(text)
  }

  const getPlayerName = (playerNum) => {
    const map = parseNamesFromText(names)
    return map[`Player${playerNum}`] || ''
  }

  // Launch PokerReader on Windows
  const launchPokerReader = async () => {
    setLaunchingPokerReader(true)
    setLaunchStatus(null)
    try {
      const response = await fetch('/api/launch/pokerreader', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exe_path: pokerReaderPath })
      })
      const data = await response.json()

      if (response.ok || response.status === 202) {
        setLaunchStatus(`✓ PokerReader launching... (${data.command_id})`)
        // Check status after a short delay
        setTimeout(() => {
          fetch(`/api/commands/${data.command_id}/status`)
            .then(r => r.json())
            .then(d => {
              if (d.status === 'completed') {
                setLaunchStatus('✓ PokerReader launched successfully!')
              } else if (d.status === 'executing') {
                setLaunchStatus('⟳ Waiting for executor...')
              }
            })
        }, 1000)
      } else {
        setLaunchStatus('✗ Error: ' + data.error)
      }
    } catch (err) {
      setLaunchStatus('✗ Error: ' + err.message)
    } finally {
      setLaunchingPokerReader(false)
    }
  }

  return (
    <div className="validator-layout">
      {/* ── Left: inputs ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
        <div className="panel">
          <div className="panel-title">Variant & Tools</div>
          <select value={variant} onChange={e => setVariant(e.target.value)}>
            {VARIANTS.map(v => (
              <option key={v.value} value={v.value}>{v.label}</option>
            ))}
          </select>
          {/* PokerReader Path Configuration */}
          <button
            className="btn btn-ghost btn-sm"
            style={{ marginTop: 8, width: '100%', fontSize: 11 }}
            onClick={() => setShowPathConfig(!showPathConfig)}
          >
            {showPathConfig ? '▼ PokerReader Path' : '▶ PokerReader Path'}
          </button>
          {showPathConfig && (
            <div style={{ marginTop: 8, padding: 8, background: 'var(--surface)', borderRadius: 4, border: '1px solid var(--border)' }}>
              <label style={{ fontSize: 10, color: 'var(--text-dim)', display: 'block', marginBottom: 4 }}>
                Executable Path
              </label>
              <input
                type="text"
                value={pokerReaderPath}
                onChange={e => updatePokerReaderPath(e.target.value)}
                placeholder="C:\Users\YourName\Desktop\PokerReader\PokerReader.exe"
                style={{
                  width: '100%',
                  padding: '6px 8px',
                  border: '1px solid var(--border)',
                  borderRadius: 3,
                  fontFamily: 'var(--mono)',
                  fontSize: 11,
                  background: 'var(--bg)',
                  color: 'var(--text)',
                  marginBottom: 6,
                  boxSizing: 'border-box'
                }}
              />
              <div style={{ fontSize: 9, color: 'var(--text-muted)', lineHeight: 1.4 }}>
                💡 Tip: Enter your PokerReader.exe path. It will be saved and used for future launches. Useful for different machines or users.
              </div>
            </div>
          )}

          <button
            className="btn btn-success"
            style={{ marginTop: 8, width: '100%' }}
            disabled={launchingPokerReader}
            onClick={launchPokerReader}
          >
            {launchingPokerReader ? '⟳ Launching...' : '▶ Launch PokerReader'}
          </button>
          {launchStatus && (
            <div style={{
              marginTop: 8,
              padding: 6,
              fontSize: 11,
              borderRadius: 3,
              background: launchStatus.includes('✓') ? 'rgba(34, 197, 94, 0.1)' : launchStatus.includes('✗') ? 'rgba(239, 68, 68, 0.1)' : 'rgba(59, 130, 246, 0.1)',
              color: launchStatus.includes('✓') ? 'var(--green)' : launchStatus.includes('✗') ? 'var(--red)' : 'var(--blue)',
              border: '1px solid ' + (launchStatus.includes('✓') ? 'rgba(34, 197, 94, 0.3)' : launchStatus.includes('✗') ? 'rgba(239, 68, 68, 0.3)' : 'rgba(59, 130, 246, 0.3)'),
            }}>
              {launchStatus}
            </div>
          )}
        </div>

        <div className="panel" style={{ flex: 1 }}>
          <div className="panel-title">
            Hands File
            {scannerStatus && (
              <span style={{
                marginLeft: 'auto',
                fontSize: 11,
                color: 'var(--green)',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
              }}>
                <span style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: 'var(--green)',
                  animation: 'pulse 1.5s infinite',
                }}></span>
                {scannerStatus}
              </span>
            )}
            {socketConnected && !scannerStatus && (
              <span style={{
                marginLeft: 'auto',
                fontSize: 11,
                color: 'var(--text-dim)',
              }}>
                ⦿ Listening for scanner...
              </span>
            )}
          </div>
          <div className="field-group">
            <textarea
              rows={14}
              value={hands}
              onChange={e => updateHands(e.target.value)}
              placeholder="Paste your hands here, one per line... or wait for PokerReader scanner"
            />
            <button
              className="btn btn-secondary btn-sm"
              style={{ marginTop: 8, width: '100%' }}
              onClick={() => { updateHands(''); lsSet(LS_HANDS, '') }}
            >
              ✕ Clear Hands
            </button>
          </div>

          <div className="field-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <label style={{ marginBottom: 0 }}>Player Names <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>(optional)</span></label>
              <div style={{ display: 'flex', gap: 4 }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setPlayerCount(Math.max(2, playerCount - 1))}
                  disabled={playerCount <= 2}
                  title="Remove player"
                >
                  − Player
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setPlayerCount(Math.min(9, playerCount + 1))}
                  disabled={playerCount >= 9}
                  title="Add player"
                >
                  + Player
                </button>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {Array.from({ length: playerCount }, (_, i) => i + 1).map(playerNum => (
                <input
                  key={playerNum}
                  type="text"
                  placeholder={`Player ${playerNum} name (e.g., Hero)`}
                  value={getPlayerName(playerNum)}
                  onChange={e => handlePlayerNameChange(playerNum, e.target.value)}
                  style={{
                    padding: '6px 8px',
                    borderRadius: 3,
                    border: '1px solid var(--border)',
                    background: 'var(--surface)',
                    color: 'var(--text)',
                    fontFamily: 'var(--mono)',
                    fontSize: 12,
                  }}
                />
              ))}
            </div>
            <button
              className="btn btn-secondary btn-sm"
              style={{ marginTop: 8, width: '100%' }}
              onClick={() => { updateNames(''); lsSet(LS_NAMES, '') }}
            >
              ✕ Clear All Names
            </button>
          </div>

          {error && (
            <div style={{ color: 'var(--red)', fontSize: 11, marginBottom: 8 }}>{error}</div>
          )}

          <button
            className="btn btn-amber"
            style={{ width: '100%' }}
            disabled={loading || !hands.trim()}
            onClick={validate}
          >
            {loading ? '⟳  Validating...' : '✓  Validate Hands'}
          </button>
        </div>
      </div>

      {/* ── Right: results ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
        {!result && !loading && (
          <div className="panel" style={{ color: 'var(--text-dim)', fontSize: 12, textAlign: 'center', padding: '40px 20px' }}>
            Paste your hands file and click Validate to check for<br />
            malformed cards and duplicates.
          </div>
        )}

        {result && (
          <>
            {/* Players summary */}
            <div className="panel">
              <div className="panel-title">Parsed Players ({result.players.length})</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {result.players.map(p => (
                  <div key={p.slot} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                    <span style={{ color: 'var(--text-dim)', width: 20, textAlign: 'right', fontSize: 10 }}>P{p.slot + 1}</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 11, width: 80 }}>{p.display_name}</span>
                    <HandChips hand={p.hand_raw} />
                  </div>
                ))}
              </div>

              {result.board_lines.length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <div className="panel-title">Board</div>
                  {result.board_lines.map((line, i) => (
                    <div key={i} style={{ fontSize: 11, color: 'var(--text-muted)' }}>{line}</div>
                  ))}
                </div>
              )}
            </div>

            {/* Issues */}
            {result.clean ? (
              <div className="clean-badge">
                ✓&nbsp; All {result.players.length} hands are clean — no issues found
              </div>
            ) : (
              <div>
                <div className="panel-title" style={{ marginBottom: 8, color: 'var(--amber)' }}>
                  {result.issues.length} Issue{result.issues.length !== 1 ? 's' : ''} Found
                </div>
                <div className="issues-list">
                  {result.issues.map((issue, i) => (
                    <IssueCard
                      key={i}
                      issue={issue}
                      variant={variant}
                      hands={hands}
                      names={names}
                      onFixed={onFixed}
                    />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
