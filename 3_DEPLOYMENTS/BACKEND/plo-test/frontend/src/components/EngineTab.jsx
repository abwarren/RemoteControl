// EngineTab.jsx — Run Engine tab
import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { startEngine, startBatchEngine, subscribeStream, fetchResults } from '../api.js'
import LiveLog from './LiveLog.jsx'
import ResultsTable from './ResultsTable.jsx'

const COPY_TIMEOUT = 2000

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

const HANDS_PLACEHOLDER = {
  'plo4-6max': `AhKhQdJd
Ts9s8c7c
KcQcJhTh
5s5d4h4c
As2s3h4d
7h7d6s6c`,
  'plo4-8max': `AhKhQdJd
Ts9s8c7c
KcQcJhTh
5s5d4h4c
As2s3h4d
7h7d6s6c
JsThKcQd
2h3c4s5d`,
  'plo4-9max': `AhKhQdJd
Ts9s8c7c
KcQcJhTh
5s5d4h4c
As2s3h4d
7h7d6s6c
JsThKcQd
2h3c4s5d
9h8d7s6c`,
  'plo5-6max': `AhKhQdJd9s
Ts9s8c7c6d
KcQcJhTh8h
5s5d4h4c3s
As2s3h4d5c
7h7d6s6c2h`,
  'plo6-5max': `AhKhQdJd9s8s
Ts9s8c7c6d5d
KcQcJhTh8h7h
5s5d4h4c3s2s
As2s3h4d5c6h`,
  'plo6-6max': `AhKhQdJd9s8s
Ts9s8c7c6d5d
KcQcJhTh8h7h
5s5d4h4c3s2s
As2s3h4d5c6h
7h7d6s6c2h3h`,
  'plo7-5max': `AhKhQdJd9s8s7s
Ts9s8c7c6d5d4d
KcQcJhTh8h7h6h
5s5d4h4c3s2s9h
As2s3h4d5c6h7d`,
  'plo7-6max': `AhKhQdJd9s8s7s
Ts9s8c7c6d5d4d
KcQcJhTh8h7h6h
5s5d4h4c3s2s9h
As2s3h4d5c6h7d
7h7d6s6c2h3h9d`,
}

// Helper: Get player count for variant
const getPlayerCount = (variant) => VARIANTS.find(v => v.value === variant)?.label.match(/(\d+)-Max/)?.[1] || 6

// Helper: Detect variant from hand length
const HAND_LEN_TO_PLO = { 8: 'plo4', 10: 'plo5', 12: 'plo6', 14: 'plo7' }
const PLO_MAX_OPTIONS = { plo4: [6,8,9], plo5: [5,6,8,9], plo6: [5,6,8], plo7: [5,6] }
function detectVariant(handsText) {
  const lines = handsText.split('\n').map(l => l.trim()).filter(Boolean)
  if (lines.length < 2) return null
  const firstLen = lines[0].length
  const ploType = HAND_LEN_TO_PLO[firstLen]
  if (!ploType) return null
  const handCount = lines.filter(l => l.length === firstLen).length
  const available = PLO_MAX_OPTIONS[ploType]
  let bestMax = available[available.length - 1]
  for (const mx of available) { if (mx >= handCount) { bestMax = mx; break } }
  return `${ploType}-${bestMax}max`
}

// Helper: Parse names string to object {Player1: "name1", Player2: "name2", ...}
const parseNames = (namesStr) => {
  const obj = {}
  if (!namesStr) return obj
  namesStr.split('\n').forEach(line => {
    const [key, val] = line.split('=').map(s => s.trim())
    if (key && val) obj[key] = val
  })
  return obj
}

// Helper: Convert names object back to string
const namesToString = (namesObj) => {
  return Object.entries(namesObj)
    .map(([k, v]) => `${k}=${v}`)
    .join('\n')
}

export default function EngineTab({ initialState, onStateChange }) {
  const [variant, setVariant] = useState(initialState?.variant || 'plo5-6max')
  const [hands,   setHands]   = useState(initialState?.hands   || '')
  const [names,   setNames]   = useState(initialState?.names   || '')

  // Sync textarea when tracker aggregate pushes new data via socket
  useEffect(() => {
    if (initialState?.hands) setHands(initialState.hands)
  }, [initialState?.hands])

  const [status,  setStatus]  = useState('idle')   // idle | running | done | error
  const [logLines, setLogLines] = useState([])
  const [jobId,   setJobId]   = useState(null)
  const [results, setResults] = useState(null)
  const [view,    setView]    = useState('log')     // log | results
  const [playerCount, setPlayerCount] = useState(() => {
    const config = {
      'plo4-6max': 6, 'plo4-8max': 8, 'plo4-9max': 9,
      'plo5-5max': 5, 'plo5-6max': 6, 'plo5-8max': 8, 'plo5-9max': 9,
      'plo6-5max': 5, 'plo6-6max': 6, 'plo6-8max': 8,
      'plo7-5max': 5, 'plo7-6max': 6,
    }
    return config[initialState?.variant || 'plo5-6max'] || 6
  })
  // batchInfo no longer needed — batch flag is on data.batch_results

  const notify = (field, val) => onStateChange?.({ variant, hands, names, [field]: val })

  const [handsCopied, setHandsCopied] = useState(false)
  const copyHands = () => {
    if (!hands.trim()) return
    navigator.clipboard.writeText(hands).then(() => {
      setHandsCopied(true)
      setTimeout(() => setHandsCopied(false), COPY_TIMEOUT)
    })
  }

  const setV = (v) => {
    setVariant(v)
    notify('variant', v)
    const config = {
      'plo4-6max': 6, 'plo4-8max': 8, 'plo4-9max': 9,
      'plo5-5max': 5, 'plo5-6max': 6, 'plo5-8max': 8, 'plo5-9max': 9,
      'plo6-5max': 5, 'plo6-6max': 6, 'plo6-8max': 8,
      'plo7-5max': 5, 'plo7-6max': 6,
    }
    setPlayerCount(config[v] || 6)
  }
  const setH = (v) => { setHands(v);   notify('hands', v) }
  const setN = (v) => { setNames(v);   notify('names', v) }

  // Count samples (separated by blank lines)
  const sampleCount = useMemo(() => {
    const samples = hands.split(/\n\s*\n/).filter(s => s.trim())
    return samples.length
  }, [hands])

  const run = useCallback(async () => {
    // Read from DOM as fallback — external scripts may set textarea without updating React state
    let handsToRun = hands
    if (!handsToRun.trim()) {
      const ta = document.querySelector('textarea[rows="14"]')
      if (ta && ta.value.trim()) {
        handsToRun = ta.value
        setHands(handsToRun)
      }
    }
    if (!handsToRun.trim()) return
    setStatus('running')
    setLogLines([])
    setResults(null)
    setView('log')

    // Auto-detect variant from hand length, override if mismatch
    const detected = detectVariant(handsToRun)
    const runVariant = detected || variant
    if (detected && detected !== variant) {
      setV(detected)
    }

    const samples = handsToRun.split(/\n\s*\n/).filter(s => s.trim())
    const isBatch = samples.length > 1
    const startFn = isBatch ? startBatchEngine : startEngine
    try {
      const resp = await startFn({ variant: runVariant, hands: handsToRun, names })

      if (resp.error) { setStatus('error'); setLogLines([resp.error]); return }

      const job_id = resp.job_id
      if (!job_id) { setStatus('error'); setLogLines(['No job_id in response']); return }
      setJobId(job_id)

      if (isBatch) {
        setLogLines([`Batch mode: ${resp.total_samples} samples queued\n`])
      }

      const unsub = subscribeStream(job_id, {
        onLine: (line) => setLogLines(prev => [...prev, line]),
        onDone: async (code) => {
          setLogLines(prev => [...prev, `\n✓ Engine exited (code ${code})\n`])
          setStatus(code === 0 ? 'done' : 'error')
          const res = await fetchResults(job_id)
          if (!res || res.error) {
            setLogLines(prev => [...prev, `\nFailed to fetch results: ${res?.error || 'Unknown error'}\n`])
          } else if (res.status === 'done' && res.data?.matchups?.length) {
            setResults(res.data)
            setView('results')
          }
        },
        onError: async (msg) => {
          setLogLines(prev => [...prev, `\nERR: ${msg}\n`])
          setStatus('error')
          const res = await fetchResults(job_id)
          if (res?.status === 'done' && res.data?.matchups?.length) {
            setResults(res.data)
            setView('results')
          }
        },
      })

      return unsub
    } catch (err) {
      setStatus('error')
      setLogLines([`Network error: ${err.message}`])
    }
  }, [variant, hands, names, sampleCount])

  const holeCards = VARIANTS.find(v => v.value === variant)
    ? parseInt(variant.split('')[3])   // plo5 → 5, plo4 → 4
    : 4

  return (
    <div className="engine-layout">
      {/* ── Left: inputs ── */}
      <div className="engine-left">
        <div className="panel">
          <div className="panel-title">Variant</div>
          <div className="field-group">
            <select value={variant} onChange={e => setV(e.target.value)}>
              {VARIANTS.map(v => (
                <option key={v.value} value={v.value}>{v.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="panel" style={{ flex: 1 }}>
          <div className="panel-title">
            Hands File
            <span style={{ color: 'var(--text-dim)', fontWeight: 400, marginLeft: 8 }}>
              one hand per line · {holeCards} cards
            </span>
          </div>
          <div className="field-group">
            <textarea
              rows={14}
              value={hands}
              onChange={e => setH(e.target.value)}
              placeholder={HANDS_PLACEHOLDER[variant]}
              style={{ fontFamily: 'var(--mono)', fontSize: 12 }}
            />
          </div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            <button
              className="btn btn-secondary btn-sm"
              style={{ flex: 1 }}
              onClick={() => setH('')}
            >
              ✕ Clear
            </button>
            <button
              className="btn btn-ghost btn-sm"
              style={{ flex: 1 }}
              onClick={copyHands}
              disabled={!hands.trim()}
            >
              {handsCopied ? '✓ Copied' : '⭘ Copy'}
            </button>
            <button
              className="btn btn-primary btn-sm"
              style={{ flex: 2 }}
              disabled={status === 'running'}
              onClick={run}
            >
              {status === 'running'
                ? (sampleCount > 1 ? `⟳ Running ${sampleCount}...` : '⟳ Running...')
                : (sampleCount > 1 ? `▶ Run ${sampleCount} Samples` : '▶ Run Engine')
              }
            </button>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 8 }}>
            Optional — add flop on next line, turn on line after that.
            <br />Separate multiple samples with a blank line (max 500).
          </div>
          {sampleCount > 1 && (
            <div style={{
              fontSize: 11, padding: '6px 10px', marginBottom: 8,
              borderRadius: 4, background: 'rgba(59, 130, 246, 0.1)',
              border: '1px solid rgba(59, 130, 246, 0.3)', color: 'var(--blue)',
            }}>
              {sampleCount} samples detected — will show only the hand with biggest disparity
            </div>
          )}

          <div className="field-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
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
            <div style={{ display: 'grid', gap: 8 }}>
              {Array.from({ length: playerCount }).map((_, idx) => {
                const playerKey = `Player${idx + 1}`
                const namesObj = parseNames(names)
                const playerName = namesObj[playerKey] || ''
                return (
                  <input
                    key={playerKey}
                    type="text"
                    placeholder={`Player ${idx + 1} name (e.g., Hero)`}
                    value={playerName}
                    onChange={(e) => {
                      const updated = { ...parseNames(names), [playerKey]: e.target.value }
                      setN(namesToString(updated))
                    }}
                    style={{
                      padding: '8px 10px',
                      border: '1px solid var(--border)',
                      borderRadius: '4px',
                      fontFamily: 'var(--mono)',
                      fontSize: '12px',
                      backgroundColor: 'var(--surface)',
                      color: 'var(--text)',
                    }}
                  />
                )
              })}
            </div>
          </div>
          <button
            className="btn btn-secondary btn-sm"
            style={{ marginBottom: 12 }}
            onClick={() => setN('')}
          >
            ✕ Clear All Names
          </button>


        </div>
      </div>

      {/* ── Right: log / results ── */}
      <div className="engine-right">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {status === 'running' && (
              <span className="status-pill running">
                <span className="pulse">●</span> Running
              </span>
            )}
            {status === 'done' && (
              <span className="status-pill done">✓ Done</span>
            )}
            {status === 'error' && (
              <span className="status-pill error">✗ Error</span>
            )}
          </div>

          {results && (
            <div className="view-toggle">
              <button className={view === 'log'     ? 'active' : ''} onClick={() => setView('log')}>Log</button>
              <button className={view === 'results' ? 'active' : ''} onClick={() => setView('results')}>Results</button>
            </div>
          )}
        </div>

        {view === 'log' || !results ? (
          <LiveLog lines={logLines} status={status} />
        ) : (
          <ResultsTable data={results} jobId={jobId} />
        )}
      </div>
    </div>
  )
}
