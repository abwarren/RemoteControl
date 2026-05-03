// RNGTab.jsx — Random Number Generator for poker sample batches
import { useState, useMemo } from 'react'
import { parseVariant } from '../variantRules.js'

const VARIANTS     = ['PLO4', 'PLO5', 'PLO6', 'PLO7']
const TABLE_SIZES  = [2, 5, 6, 8, 9]
const STREETS      = ['FLOP', 'TURN', 'RIVER']

// Map RNG variant + table size → engine variant key
const ENGINE_VARIANT_MAP = {
  'PLO4-6': 'plo4-6max', 'PLO4-8': 'plo4-8max', 'PLO4-9': 'plo4-9max',
  'PLO5-5': 'plo5-5max', 'PLO5-6': 'plo5-6max', 'PLO5-8': 'plo5-8max', 'PLO5-9': 'plo5-9max',
  'PLO6-5': 'plo6-5max', 'PLO6-6': 'plo6-6max', 'PLO6-8': 'plo6-8max',
  'PLO7-5': 'plo7-5max', 'PLO7-6': 'plo7-6max',
}

// Cards per player — derived from parseVariant at call time, not a static map
function getCPP(variantStr) {
  try { return parseVariant(`${variantStr.toLowerCase()}-2max`).hole_cards } catch { return 0 }
}
// Board cards per street
const BCC = { FLOP: 3, TURN: 4, RIVER: 5 }

function isFeasible(variant, tableSize, street) {
  // Build a temporary engine-style key to parse hole cards via parseVariant
  const engineKey = ENGINE_VARIANT_MAP[`${variant}-${tableSize}`]
  let holeCards = 0
  if (engineKey) {
    try { holeCards = parseVariant(engineKey).hole_cards } catch { holeCards = 0 }
  } else {
    // Fallback: derive hole cards from variant name directly (PLO5 → 5)
    const m = variant.match(/PLO(\d+)/i)
    holeCards = m ? parseInt(m[1], 10) : 0
  }
  return tableSize * holeCards + (BCC[street] || 0) <= 52
}

export default function RNGTab({ onSendToEngine }) {
  const [variant,     setVariant]     = useState('PLO5')
  const [tableSize,   setTableSize]   = useState(6)
  const [street,      setStreet]      = useState('FLOP')
  const [sampleCount, setSampleCount] = useState(10)
  const [loading,     setLoading]     = useState(false)
  const [output,      setOutput]      = useState('')
  const [meta,        setMeta]        = useState(null)
  const [error,       setError]       = useState('')
  const [copied,      setCopied]      = useState(false)

  // Derive hole cards for the active PLO variant via parseVariant
  const holeCardsForVariant = useMemo(() => {
    const m = variant.match(/PLO(\d+)/i)
    return m ? parseInt(m[1], 10) : 0
  }, [variant])

  const feasible     = useMemo(() => isFeasible(variant, tableSize, street), [variant, tableSize, street])
  const cardsNeeded  = useMemo(() => tableSize * holeCardsForVariant + (BCC[street] || 0), [variant, tableSize, street, holeCardsForVariant])
  const engineVariant = ENGINE_VARIANT_MAP[`${variant}-${tableSize}`] || null

  const generate = async () => {
    if (!feasible) return
    setLoading(true); setError(''); setOutput(''); setMeta(null)
    try {
      const res  = await fetch('/api/rng/generate', {
        method:  'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Auth-Token': localStorage.getItem('auth_token') || '',
        },
        body: JSON.stringify({
          variant,
          table_size:   tableSize,
          street,
          sample_count: sampleCount,
        }),
      })
      const data = await res.json()
      if (!data.ok) { setError(data.error || 'Generation failed'); return }
      setOutput(data.output)
      setMeta({
        variant:      data.variant,
        table_size:   data.table_size,
        street:       data.street,
        sample_count: data.sample_count,
        total_cards:  data.total_cards,
      })
    } catch (e) {
      setError('Network error: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = () => {
    navigator.clipboard.writeText(output).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const sendToEngine = () => {
    if (!output || !engineVariant) return
    onSendToEngine({ hands: output, variant: engineVariant })
  }

  return (
    <div className="engine-layout">
      {/* ── Left: controls ── */}
      <div className="engine-left">

        {/* Variant */}
        <div className="panel">
          <div className="panel-title">Variant</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {VARIANTS.map(v => (
              <button
                key={v}
                className={`btn btn-sm ${variant === v ? 'btn-primary' : 'btn-ghost'}`}
                style={{ letterSpacing: 1 }}
                onClick={() => setVariant(v)}
              >
                {v}
              </button>
            ))}
          </div>
          <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-dim)' }}>
          {holeCardsForVariant} hole cards per player
          </div>
        </div>

        {/* Table Size */}
        <div className="panel">
          <div className="panel-title">Table Size</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6 }}>
            {TABLE_SIZES.map(s => {
              const ok = isFeasible(variant, s, street)
              return (
                <button
                  key={s}
                  className={`btn btn-sm ${tableSize === s ? 'btn-primary' : 'btn-ghost'}`}
                  style={{ opacity: ok ? 1 : 0.35 }}
                  onClick={() => setTableSize(s)}
                  title={ok ? `${s}-max` : `Exceeds 52-card deck`}
                >
                  {s}
                </button>
              )
            })}
          </div>
          <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-dim)' }}>
            {tableSize}-max table
          </div>
        </div>

        {/* Street */}
        <div className="panel">
          <div className="panel-title">Street</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
            {STREETS.map(s => {
              const ok = isFeasible(variant, tableSize, s)
              return (
                <button
                  key={s}
                  className={`btn btn-sm ${street === s ? 'btn-primary' : 'btn-ghost'}`}
                  style={{ opacity: ok ? 1 : 0.35, fontSize: 10 }}
                  onClick={() => setStreet(s)}
                  title={ok ? `${BCC[s]} board cards` : 'Exceeds 52-card deck'}
                >
                  {s}
                </button>
              )
            })}
          </div>
          <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-dim)' }}>
            {BCC[street]} board cards
          </div>
        </div>

        {/* Sample Count */}
        <div className="panel">
          <div className="panel-title">Sample Count</div>
          <input
            type="number"
            min={1}
            max={1000}
            value={sampleCount}
            onChange={e => setSampleCount(Math.min(1000, Math.max(1, parseInt(e.target.value) || 1)))}
          />
          <div style={{ marginTop: 6, fontSize: 10, color: 'var(--text-dim)' }}>
            1 – 1000 samples per run
          </div>
        </div>

        {/* Deck feasibility summary */}
        <div className={`panel`} style={{
          borderColor: feasible ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)',
          background:  feasible ? '#061310' : '#120608',
        }}>
          <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Players</span>
              <span>{tableSize} × {holeCardsForVariant} = {tableSize * holeCardsForVariant} cards</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Board</span>
              <span>{BCC[street]} cards</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--border)', paddingTop: 4, marginTop: 2 }}>
              <span style={{ color: 'var(--text-muted)' }}>Total needed</span>
              <span style={{ fontWeight: 700, color: feasible ? 'var(--accent)' : 'var(--red)' }}>
                {cardsNeeded} / 52
              </span>
            </div>
            {!feasible && (
              <div style={{ color: 'var(--red)', fontSize: 10, marginTop: 4 }}>
                ✗ Exceeds 52-card deck — reduce players or street
              </div>
            )}
            {feasible && (
              <div style={{ color: 'var(--accent)', fontSize: 10, marginTop: 4 }}>
                ✓ Valid configuration
              </div>
            )}
          </div>
        </div>

        {/* Generate button */}
        <button
          className="btn btn-primary"
          style={{ width: '100%' }}
          disabled={!feasible || loading}
          onClick={generate}
        >
          {loading ? '⟳  Generating...' : `⚄  Generate ${sampleCount} Sample${sampleCount !== 1 ? 's' : ''}`}
        </button>

        {/* Send to Engine — below Generate so it's never obscured by overlays */}
        {output && engineVariant && (
          <button
            className="btn btn-primary"
            style={{ width: '100%', marginTop: 6 }}
            onClick={sendToEngine}
            title={`Send to Engine tab as ${engineVariant}`}
          >
            ▶ Send to Engine
          </button>
        )}

        {error && (
          <div style={{
            padding: '8px 12px', borderRadius: 5, fontSize: 11,
            background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.3)',
            color: 'var(--red)',
          }}>
            ✗ {error}
          </div>
        )}
      </div>

      {/* ── Right: output ── */}
      <div className="engine-right">
        {/* Meta bar */}
        {meta && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 8, flexWrap: 'wrap', gap: 8,
          }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span className="status-pill done">✓ {meta.sample_count} samples</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', alignSelf: 'center' }}>
                {meta.variant} · {meta.table_size}-max · {meta.street} · {meta.total_cards} cards/sample
              </span>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="btn btn-ghost btn-sm" onClick={copyToClipboard}>
                {copied ? '✓ Copied' : '⎘ Copy'}
              </button>
            </div>
          </div>
        )}

        {/* Output area */}
        {!output && !loading && (
          <div className="panel" style={{
            flex: 1, color: 'var(--text-dim)', fontSize: 12,
            textAlign: 'center', padding: '60px 20px',
          }}>
            <div style={{ fontSize: 28, marginBottom: 12 }}>⚄</div>
            Configure your variant and click Generate.<br /><br />
            <span style={{ fontSize: 11 }}>
              Each sample is a freshly shuffled deck deal.<br />
              Output is cards-only, blank-line separated,<br />
              ready to paste directly into the Engine tab.
            </span>
          </div>
        )}

        {loading && (
          <div className="panel" style={{
            flex: 1, color: 'var(--text-muted)', fontSize: 12,
            textAlign: 'center', padding: '60px 20px',
          }}>
            <span className="pulse">●</span> Generating {sampleCount} samples...
          </div>
        )}

        {output && !loading && (
          <textarea
            readOnly
            value={output}
            style={{
              flex: 1,
              background: '#050810',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              color: '#8ea3c3',
              fontFamily: 'var(--mono)',
              fontSize: 11,
              lineHeight: 1.6,
              padding: '10px 12px',
              resize: 'none',
              outline: 'none',
              overflowY: 'auto',
              whiteSpace: 'pre',
            }}
          />
        )}
      </div>
    </div>
  )
}
