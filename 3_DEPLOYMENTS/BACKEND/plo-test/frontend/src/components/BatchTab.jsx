// BatchTab.jsx — Dedicated Batch Run tab
import { useState, useCallback, useMemo } from 'react'
import { startBatchEngine, subscribeStream, fetchResults, downloadResults } from '../api.js'
import LiveLog from './LiveLog.jsx'
import ResultsTable from './ResultsTable.jsx'

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

const PLACEHOLDER = `# Sample 1
AhKhQdJd
Ts9s8c7c
KcQcJhTh
5s5d4h4c
As2s3h4d
7h7d6s6c

# Sample 2
AhKhQdJd9s
Ts9s8c7c6d
KcQcJhTh8h
5s5d4h4c3s
As2s3h4d5c
7h7d6s6c2h`

const COPY_TIMEOUT = 2000

export default function BatchTab({ initialState, onStateChange }) {
  const [variant,  setVariant]  = useState(initialState?.variant || 'plo5-6max')
  const [hands,    setHands]    = useState(initialState?.hands   || '')
  const [names,    setNames]    = useState(initialState?.names   || '')
  const [status,   setStatus]   = useState('idle')
  const [logLines, setLogLines] = useState([])
  const [jobId,    setJobId]    = useState(null)
  const [results,  setResults]  = useState(null)
  const [view,     setView]     = useState('log')
  const [progress, setProgress] = useState({ done: 0, total: 0 })
  const [copied,   setCopied]   = useState(false)

  const notify = (field, val) => onStateChange?.({ variant, hands, names, [field]: val })
  const setV = (v) => { setVariant(v); notify('variant', v) }
  const setH = (v) => { setHands(v);   notify('hands',   v) }
  const setN = (v) => { setNames(v);   notify('names',   v) }

  const holeCards = parseInt(variant.split('')[3]) || 4

  const sampleCount = useMemo(() => {
    return hands.split(/\n\s*\n/).filter(s => s.trim()).length
  }, [hands])

  const copyHands = () => {
    if (!hands.trim()) return
    navigator.clipboard.writeText(hands).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), COPY_TIMEOUT)
    })
  }

  const run = useCallback(async () => {
    if (!hands.trim() || sampleCount < 2) return
    setStatus('running')
    setLogLines([])
    setResults(null)
    setView('log')
    setProgress({ done: 0, total: sampleCount })

    const resp = await startBatchEngine({ variant, hands, names })
    if (resp.error) {
      setStatus('error')
      setLogLines([resp.error])
      return
    }

    const job_id = resp.job_id
    setJobId(job_id)
    setProgress({ done: 0, total: resp.total_samples || sampleCount })
    setLogLines([`Batch started — ${resp.total_samples ?? sampleCount} samples queued\n`])

    const unsub = subscribeStream(job_id, {
      onLine: (line) => {
        setLogLines(prev => [...prev, line])
        if (line.includes('Sample') && line.includes('done')) {
          setProgress(prev => ({ ...prev, done: prev.done + 1 }))
        }
      },
      onDone: async (code) => {
        setLogLines(prev => [...prev, `\n✓ Batch complete (exit ${code})\n`])
        setStatus(code === 0 ? 'done' : 'error')
        setProgress(prev => ({ ...prev, done: prev.total }))
        const res = await fetchResults(job_id)
        if (res.status === 'done' && res.data?.matchups?.length) {
          setResults(res.data)
          setView('results')
        }
      },
      onError: (msg) => {
        setLogLines(prev => [...prev, `\nERR: ${msg}\n`])
        setStatus('error')
      },
    })
    return unsub
  }, [variant, hands, names, sampleCount])

  const progressPct = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0

  return (
    <div className="engine-layout">
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
            Batch Hands
            <span style={{ color: 'var(--text-dim)', fontWeight: 400, marginLeft: 8 }}>
              {holeCards} cards · separate samples with a blank line
            </span>
          </div>
          <div className="field-group">
            <textarea
              rows={16}
              value={hands}
              onChange={e => setH(e.target.value)}
              placeholder={PLACEHOLDER}
              style={{ fontFamily: 'var(--mono)', fontSize: 12 }}
            />
          </div>
          {sampleCount > 0 && (
            <div style={{
              fontSize: 11, padding: '6px 10px', marginBottom: 8, borderRadius: 4,
              background: sampleCount >= 2 ? 'rgba(59, 130, 246, 0.1)' : 'rgba(234, 179, 8, 0.1)',
              border: `1px solid ${sampleCount >= 2 ? 'rgba(59, 130, 246, 0.3)' : 'rgba(234, 179, 8, 0.3)'}`,
              color: sampleCount >= 2 ? 'var(--blue)' : 'var(--yellow)',
            }}>
              {sampleCount >= 2
                ? `${sampleCount} samples detected — all results will be shown`
                : 'Add a second sample (separate with a blank line) to use batch mode'}
            </div>
          )}
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            <button className="btn btn-secondary btn-sm" style={{ flex: 1 }} onClick={() => setH('')}>
              ✕ Clear
            </button>
            <button className="btn btn-ghost btn-sm" style={{ flex: 1 }} onClick={copyHands} disabled={!hands.trim()}>
              {copied ? '✓ Copied' : '⭘ Copy'}
            </button>
            <button
              className="btn btn-primary btn-sm" style={{ flex: 2 }}
              disabled={status === 'running' || sampleCount < 2}
              onClick={run}
            >
              {status === 'running'
                ? `⟳ Running ${progress.done}/${progress.total}…`
                : `▶ Run ${sampleCount >= 2 ? sampleCount + ' Samples' : 'Batch'}`}
            </button>
          </div>
          {(status === 'running' || status === 'done') && progress.total > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ height: 4, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${progressPct}%`,
                  background: status === 'done' ? 'var(--green)' : 'var(--blue)',
                  transition: 'width 0.3s ease',
                }} />
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 3 }}>
                {progress.done} / {progress.total} samples · {progressPct}%
              </div>
            </div>
          )}
          <div style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 8 }}>
            Max 500 samples per batch. Each sample may include an optional flop
            (next line) and turn (line after that).
          </div>
          <div className="field-group">
            <label>Player Names <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>(optional)</span></label>
            <textarea
              rows={4} value={names}
              onChange={e => setN(e.target.value)}
              placeholder={'Player1=Hero\nPlayer2=Villain'}
              style={{ fontFamily: 'var(--mono)', fontSize: 12 }}
            />
          </div>
          <button className="btn btn-secondary btn-sm" style={{ marginBottom: 12 }} onClick={() => setN('')}>
            ✕ Clear Names
          </button>
        </div>
      </div>
      <div className="engine-right" style={{ overflowY: "auto", maxHeight: "calc(100vh - 120px)" }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {status === 'running' && (
              <span className="status-pill running"><span className="pulse">●</span> Running</span>
            )}
            {status === 'done'  && <span className="status-pill done">✓ Done</span>}
            {status === 'error' && <span className="status-pill error">✗ Error</span>}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {status === 'done' && jobId && (
              <button className="btn btn-ghost btn-sm" onClick={() => downloadResults(jobId)}>
                ↓ Download CSV
              </button>
            )}
            {results && (
              <div className="view-toggle">
                <button className={view === 'log'     ? 'active' : ''} onClick={() => setView('log')}>Log</button>
                <button className={view === 'results' ? 'active' : ''} onClick={() => setView('results')}>Results</button>
              </div>
            )}
          </div>
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
