// ParserTab.jsx -- Batch results parser with market model analysis
import { useState, useMemo, useCallback } from 'react'

const STORAGE_KEY = 'plo_parser'
const FIELD_MAP = {
  underdog_name:    'BUY',
  favourite_name:   'REVERSE BUYER',
  und_raw:          'PRICE',
  und_real:         'Reverse Buy Hit %',
  fav_raw:          'RvsPrice',
  fav_real:         'HitRate %',
  disparity:        'EV',
  underdog_hand:    'BUY Hand',
  favourite_hand:   'REVERSE BUYER Hand',
}

const loadState = () => {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null') } catch { return null }
}
const saveState = (s) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)) } catch {}
}

// ── Detect sample blocks from raw text ──
function detectSamples(text) {
  if (!text.trim()) return []
  const blocks = text.split(/(?:\n\s*){2,}|\n-{3,}\n|\n={3,}\n/)
    .map(b => b.trim()).filter(Boolean)
  return blocks
}

// ── Parse one sample block ──
function parseSampleBlock(block, sampleId) {
  const sample = { sample_id: sampleId, raw: block, pairs: [], players: [],
    sections: [], errors: [], street: 'UNKNOWN', winner: null }

  // Detect sections
  if (/Street\s+\S+/.test(block)) sample.sections.push('header')
  if (/Player\s+\d+/i.test(block)) sample.sections.push('player_list')
  if (sample.street !== 'PREFLOP') sample.sections.push('flop')
  if (/ALL MATCHUPS/.test(block)) sample.sections.push('ranked_table')

  // Extract street
  const sm = block.match(/Street\s{5,}(\S+)/)
  if (sm) sample.street = sm[1]

  // Extract players
  const pp = [...block.matchAll(/Player\s+(\d+)\s+(\w{8,10})\s+\(([^)]+)\)/g)]
  const seen = new Set()
  pp.forEach(m => {
    const slot = parseInt(m[1])
    if (!seen.has(slot)) { seen.add(slot); sample.players.push({ slot, hand: m[2], name: m[3].trim() }) }
  })

  // Extract matchup rows
  const ranked = block.split('ALL MATCHUPS')
  const section = ranked.length > 1 ? ranked[1] : block
  const rowRx = /^\s{2,}(\d+)\s{2,}(\d+)\s+(\w+)\s+\(([^)]+?)\)\s+(\w+)\s+\(([^)]+?)\)\s+([\d.]+)%\s+([\d.]+)%\s+([+\-]?\s*[\d.]+)%\s+([\d.]+)%\s+([\d.]+)%/gm
  let m
  while ((m = rowRx.exec(section)) !== null) {
    try {
      sample.pairs.push({
        rank: parseInt(m[1]), pair_num: parseInt(m[2]),
        underdog_hand: m[3], underdog_name: m[4].trim(),
        favourite_hand: m[5], favourite_name: m[6].trim(),
        und_raw: parseFloat(m[7]), und_real: parseFloat(m[8]),
        disparity: parseFloat(m[9].replace(/\s/g, '')),
        fav_raw: parseFloat(m[10]), fav_real: parseFloat(m[11]),
        sample_id: sampleId,
      })
    } catch (e) { sample.errors.push(`Row parse: ${e.message}`) }
  }

  if (sample.pairs.length) {
    sample.sections.push('matchup_rows', 'final_result')
    sample.winner = [...sample.pairs].sort((a, b) => a.disparity - b.disparity)[0]
  }
  return sample
}

// ── Validate sample ──
const REQUIRED = ['header','player_list','flop','matchup_rows','ranked_table','final_result']
function validateSample(s) {
  const missing = REQUIRED.filter(r => !s.sections.includes(r))
  return { sample_id: s.sample_id, ok: !missing.length, missing, found: s.sections,
    pair_count: s.pairs.length, player_count: s.players.length, errors: s.errors }
}

// ── Normalize row to market model ──
function normalizeRow(row) {
  return {
    ...row,
    BUY:                row.underdog_name,
    'REVERSE BUYER':    row.favourite_name,
    PRICE:              row.und_raw,
    'Reverse Buy Hit %':row.und_real,
    RvsPrice:           row.fav_raw,
    'HitRate %':        row.fav_real,
    EV:                 row.disparity,
    'BUY Hand':         row.underdog_hand,
    'REVERSE BUYER Hand': row.favourite_hand,
  }
}

// ── Main Component ──
export default function ParserTab() {
  const saved = loadState()
  const [rawText,    setRawText]    = useState(saved?.rawText    || '')
  const [blocks,     setBlocks]     = useState(saved?.blocks     || [])
  const [samples,    setSamples]    = useState(saved?.samples    || [])
  const [validated,  setValidated]  = useState(saved?.validated  || [])
  const [pairs,      setPairs]      = useState(saved?.pairs      || [])
  const [winners,    setWinners]    = useState(saved?.winners    || [])
  const [filtered,   setFiltered]   = useState(saved?.filtered   || [])
  const [normalized, setNormalized] = useState(saved?.normalized || false)
  const [errors,     setErrors]     = useState(saved?.errors     || [])
  const [view,       setView]       = useState('pairs')
  const [filter,     setFilter]     = useState('all')
  const [status,     setStatus]     = useState('')

  const persist = useCallback((updates) => {
    const next = { rawText, blocks, samples, validated, pairs, winners, filtered, normalized, errors, ...updates }
    saveState(next)
  }, [rawText, blocks, samples, validated, pairs, winners, filtered, normalized, errors])

  // ── GROUP 1: Parse ──
  const doDetect = () => {
    const b = detectSamples(rawText)
    setBlocks(b)
    setStatus(`Detected ${b.length} sample blocks`)
    persist({ blocks: b })
  }

  const doParse = () => {
    if (!blocks.length) { setStatus('Detect samples first'); return }
    const parsed = blocks.map((b, i) => parseSampleBlock(b, i + 1))
    setSamples(parsed)
    const allPairs = parsed.flatMap(s => s.pairs)
    setPairs(allPairs)
    setFiltered(allPairs)
    const allErrors = parsed.flatMap(s => s.errors.map(e => ({ sample_id: s.sample_id, error: e })))
    setErrors(allErrors)
    setStatus(`Parsed ${parsed.length} samples, ${allPairs.length} pairs, ${allErrors.length} errors`)
    persist({ samples: parsed, pairs: allPairs, filtered: allPairs, errors: allErrors })
  }

  const doValidate = () => {
    if (!samples.length) { setStatus('Parse first'); return }
    const v = samples.map(validateSample)
    setValidated(v)
    const ok = v.filter(x => x.ok).length
    setStatus(`Validated: ${ok}/${v.length} samples OK`)
    persist({ validated: v })
  }

  const doNormalize = () => {
    if (!pairs.length) { setStatus('No pairs to normalize'); return }
    const norm = pairs.map(normalizeRow)
    setPairs(norm)
    setFiltered(norm)
    setNormalized(true)
    setStatus(`Normalized ${norm.length} rows to market model`)
    persist({ pairs: norm, filtered: norm, normalized: true })
  }

  const doClear = () => {
    setRawText(''); setBlocks([]); setSamples([]); setValidated([])
    setPairs([]); setWinners([]); setFiltered([]); setNormalized(false)
    setErrors([]); setStatus('Cleared'); setFilter('all')
    localStorage.removeItem(STORAGE_KEY)
  }

  // placeholder for parts 2-4
  const doBuildPairs = () => {
    if (!samples.length) { setStatus('Parse first'); return }
    const all = samples.flatMap(s => s.pairs)
    setPairs(all); setFiltered(all); setView('pairs')
    setStatus(`Built pair dataset: ${all.length} rows from ${samples.length} samples`)
    persist({ pairs: all, filtered: all })
  }

  const doBestPair = () => {
    if (!samples.length) { setStatus('Parse first'); return }
    const best = samples.map(s => s.winner).filter(Boolean)
      .sort((a, b) => (a.disparity ?? a.EV ?? 0) - (b.disparity ?? b.EV ?? 0))
    best.forEach((w, i) => { w.global_rank = i + 1 })
    setWinners(best); setView('winners')
    setStatus(`Extracted ${best.length} sample winners, ranked by EV`)
    persist({ winners: best })
  }

  const doCompare = () => {
    if (!samples.length) { setStatus('Parse first'); return }
    const best = samples.map(s => s.winner).filter(Boolean)
      .sort((a, b) => (a.disparity ?? a.EV ?? 0) - (b.disparity ?? b.EV ?? 0))
    best.forEach((w, i) => { w.global_rank = i + 1 })
    setWinners(best); setFiltered(best); setView('winners')
    setStatus(`Comparing ${best.length} sample winners head-to-head`)
    persist({ winners: best, filtered: best })
  }
  const doFilter = (mode) => {
    const source = pairs.length ? pairs : []
    const ev = (r) => r.disparity ?? r.EV ?? 0
    let result
    switch (mode) {
      case 'all':         result = source; break
      case 'winners':     result = source.filter(r => r.rank === 1); break
      case 'pos_ev':      result = source.filter(r => ev(r) > 0.5); break
      case 'neg_ev':      result = source.filter(r => ev(r) < -0.5); break
      case 'near_zero':   result = source.filter(r => Math.abs(ev(r)) <= 0.5); break
      case 'top_buy':     result = [...source].filter(r => ev(r) < 0).sort((a,b) => ev(a) - ev(b)).slice(0, 20); break
      case 'top_reverse': result = [...source].filter(r => ev(r) > 0).sort((a,b) => ev(b) - ev(a)).slice(0, 20); break
      case 'buy':         result = source.filter(r => ev(r) < 0); break
      case 'reverse':     result = source.filter(r => ev(r) > 0); break
      default:            result = source
    }
    setFiltered(result); setFilter(mode); setView('pairs')
    const labels = {
      all: 'Keep Keep Keep All Pairs', winners: 'Keep Keep Keep Winners Only', pos_ev: 'Positive EV',
      neg_ev: 'Negative EV', near_zero: 'Near Fair Pricing',
      top_buy: 'Top 20 BUY', top_reverse: 'Top 20 REVERSE',
      buy: 'All BUY', reverse: 'All REVERSE',
    }
    setStatus(`Filter: ${labels[mode] || mode} - ${result.length} rows`)
    persist({ filtered: result })
  }
  const doShowErrors   = () => { setView('errors'); setStatus(`${errors.length} parse errors`) }

  const BtnGroup = ({ title, children }) => (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--text-dim)',
        fontFamily: 'var(--display)', marginBottom: 4, fontWeight: 700 }}>{title}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>{children}</div>
    </div>
  )

  const Btn = ({ onClick, disabled, active, children }) => (
    <button className={`btn btn-sm ${active ? 'btn-primary' : 'btn-secondary'}`}
      style={{ fontSize: 10, padding: '4px 8px' }} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  )

  const pairCount = filtered.length
  const sampleCount = samples.length

  return (
    <div className="engine-layout">

      {/* ── LEFT PANEL ── */}
      <div className="engine-left">
        <div className="panel">
          <div className="panel-title">Batch Output</div>
          <div className="field-group">
            <textarea rows={12} value={rawText}
              onChange={e => { setRawText(e.target.value); persist({ rawText: e.target.value }) }}
              placeholder="Paste raw batch engine output here..."
              style={{ fontFamily: 'var(--mono)', fontSize: 11 }} />
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 6 }}>
            {rawText.length > 0 ? `${rawText.length.toLocaleString()} chars` : 'Waiting for input'}
          </div>
        </div>

        {/* GROUP 1: Parse */}
        <div className="panel">
          <BtnGroup title="Parse">
            <Btn onClick={doDetect} disabled={!rawText.trim()}>Detect Samples</Btn>
            <Btn onClick={doParse} disabled={!blocks.length}>Parse Batch Results</Btn>
            <Btn onClick={doValidate} disabled={!samples.length}>Validate Batch</Btn>
            <Btn onClick={doNormalize} disabled={!pairs.length} active={normalized}>Normalize Fields</Btn>
          </BtnGroup>

          {/* GROUP 2: Build */}
          <BtnGroup title="Build">
            <Btn onClick={doBuildPairs} disabled={!samples.length}>Build BUY Dataset</Btn>
            <Btn onClick={doBestPair} disabled={!pairs.length}>Build Winner Dataset</Btn>
            <Btn onClick={doCompare} disabled={!pairs.length}>Compare Sample Winners</Btn>
          </BtnGroup>

          {/* GROUP 3: Filter */}
          <BtnGroup title="Filter">
            <Btn onClick={() => doFilter('all')} active={filter==='all'}>All Pairs</Btn>
            <Btn onClick={() => doFilter('winners')} active={filter==='winners'}>Winners Only</Btn>
            <Btn onClick={() => doFilter('top_buy')} active={filter==='top_buy'}>Top BUY Trades</Btn>
            <Btn onClick={() => doFilter('top_reverse')} active={filter==='top_reverse'}>Top REVERSE Trades</Btn>
            <Btn onClick={() => doFilter('pos_ev')}>Lowest EV</Btn>
            <Btn onClick={() => doFilter('neg_ev')}>Highest EV</Btn>
            <Btn onClick={() => doFilter('near_zero')}>Near Fair Pricing</Btn>
            <Btn onClick={() => doFilter('by_price')} active={filter==='by_price'}>Price Filter</Btn>
            <Btn onClick={() => doFilter('by_hitrate')} active={filter==='by_hitrate'}>HitRate Filter</Btn>
            <Btn onClick={() => doFilter('by_rvsprice')} active={filter==='by_rvsprice'}>RvsPrice Filter</Btn>
            <Btn onClick={() => doFilter('rank_buy_ev')} disabled={!pairs.length}>Rank BUY EV</Btn>
            <Btn onClick={() => doFilter('rank_rev_ev')} disabled={!pairs.length}>Rank REVERSE EV</Btn>
          </BtnGroup>

                    {/* GROUP 4: Diagnostics */}
          <BtnGroup title="Diagnostics">
            <Btn onClick={doShowErrors} disabled={!errors.length}>Show Parse Errors ({errors.length})</Btn>
            <Btn onClick={doClear}>Clear Parsed Data</Btn>
          </BtnGroup>
        </div>

        {/* Status */}
        {status && (
          <div style={{ fontSize: 10, padding: '6px 10px', borderRadius: 4, marginBottom: 6,
            background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)',
            color: 'var(--blue, #3b82f6)', fontFamily: 'var(--mono)' }}>
            {status}
          </div>
        )}

        {/* Quick stats + batch summary */}
        {sampleCount > 0 && (() => {
          const evs = pairs.map(r => r.disparity ?? r.EV ?? 0).filter(v => v !== 0)
          const buyCount = evs.filter(v => v < 0).length
          const revCount = evs.filter(v => v > 0).length
          const nearZero = evs.filter(v => Math.abs(v) <= 0.5).length
          const avgEv = evs.length ? (evs.reduce((a, b) => a + b, 0) / evs.length) : 0
          const minEv = evs.length ? Math.min(...evs) : 0
          const maxEv = evs.length ? Math.max(...evs) : 0
          const validCount = samples.filter(s => s.pairs.length > 0 && !s.errors.length).length

          return (
            <div className="panel" style={{ fontSize: 11, fontFamily: 'var(--mono)' }}>
              <div className="panel-title">Batch Summary</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px' }}>
                <span style={{ color: 'var(--text-dim)' }}>Samples</span>
                <span>{sampleCount} <span style={{ color: 'var(--green,#22c55e)' }}>({validCount} valid)</span></span>

                <span style={{ color: 'var(--text-dim)' }}>Total Pairs</span><span>{pairs.length}</span>
                <span style={{ color: 'var(--text-dim)' }}>Showing</span><span>{filtered.length}</span>

                <span style={{ color: 'var(--text-dim)' }}>Normalized</span>
                <span style={{ color: normalized ? 'var(--green,#22c55e)' : 'var(--text-dim)' }}>
                  {normalized ? 'YES' : 'NO'}
                </span>

                <td colSpan={2} style={{ borderTop: '1px solid var(--border)', height: 1 }} />
                <td colSpan={2} style={{ height: 1 }} />

                <span style={{ color: 'var(--green,#22c55e)' }}>BUY edge</span>
                <span style={{ color: 'var(--green,#22c55e)' }}>{buyCount}</span>

                <span style={{ color: 'var(--red,#ef4444)' }}>REVERSE edge</span>
                <span style={{ color: 'var(--red,#ef4444)' }}>{revCount}</span>

                <span style={{ color: 'var(--text-dim)' }}>Near zero</span><span>{nearZero}</span>

                <td colSpan={2} style={{ height: 1 }} />
                <td colSpan={2} style={{ height: 1 }} />

                <span style={{ color: 'var(--text-dim)' }}>Avg EV</span>
                <span style={{ color: avgEv < 0 ? 'var(--green,#22c55e)' : 'var(--red,#ef4444)' }}>
                  {avgEv > 0 ? '+' : ''}{avgEv.toFixed(4)}%
                </span>

                <span style={{ color: 'var(--text-dim)' }}>Best EV</span>
                <span style={{ color: 'var(--green,#22c55e)', fontWeight: 700 }}>{minEv.toFixed(4)}%</span>

                <span style={{ color: 'var(--text-dim)' }}>Worst EV</span>
                <span style={{ color: 'var(--red,#ef4444)' }}>+{maxEv.toFixed(4)}%</span>
              </div>
            </div>
          )
        })()}
      </div>

      {/* ── RIGHT PANEL (placeholder for parts 2-4) ── */}
      <div className="engine-right">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div className="view-toggle">
            <button className={view === 'pairs'   ? 'active' : ''} onClick={() => setView('pairs')}>Pairs</button>
            <button className={view === 'winners' ? 'active' : ''} onClick={() => setView('winners')}>Winners</button>
            <button className={view === 'errors'  ? 'active' : ''} onClick={() => setView('errors')}>Errors</button>
            <button className={view === 'valid'   ? 'active' : ''} onClick={() => setView('valid')}>Validation</button>
          </div>
          <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>
            {pairCount} rows
          </span>
        </div>

        {/* Pairs table placeholder */}
        {view === 'pairs' && filtered.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, fontFamily: 'var(--mono)' }}>
              <thead>
                <tr style={{ color: 'var(--text-dim)', fontSize: 9, letterSpacing: 1,
                  textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: '5px 6px', textAlign: 'left' }}>S#</th>
                  <th style={{ padding: '5px 6px', textAlign: 'left' }}>
                    {normalized ? 'BUY' : 'Underdog'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'left' }}>
                    {normalized ? 'REVERSE BUYER' : 'Favourite'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'right' }}>
                    {normalized ? 'PRICE' : 'Und Raw'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'right' }}>
                    {normalized ? 'Rev Buy Hit %' : 'Und Real'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'right' }}>
                    {normalized ? 'EV' : 'Disparity'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'right' }}>
                    {normalized ? 'RvsPrice' : 'Fav Raw'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'right' }}>
                    {normalized ? 'HitRate %' : 'Fav Real'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.slice(0, 200).map((r, i) => {
                  const ev = r.disparity ?? r.EV ?? 0
                  const evColor = ev < 0 ? 'var(--green,#22c55e)' : ev > 0 ? 'var(--red,#ef4444)' : 'var(--text-dim)'
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)',
                      background: i % 2 ? 'rgba(255,255,255,0.02)' : 'transparent' }}>
                      <td style={{ padding: '5px 6px', color: 'var(--text-dim)' }}>{r.sample_id}</td>
                      <td style={{ padding: '5px 6px' }}>{normalized ? r.BUY : r.underdog_name}</td>
                      <td style={{ padding: '5px 6px' }}>{normalized ? r['REVERSE BUYER'] : r.favourite_name}</td>
                      <td style={{ padding: '5px 6px', textAlign: 'right' }}>
                        {(normalized ? r.PRICE : r.und_raw)?.toFixed(2)}%
                      </td>
                      <td style={{ padding: '5px 6px', textAlign: 'right' }}>
                        {(normalized ? r['Reverse Buy Hit %'] : r.und_real)?.toFixed(2)}%
                      </td>
                      <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 600, color: evColor }}>
                        {ev > 0 ? '+' : ''}{ev?.toFixed(4)}%
                      </td>
                      <td style={{ padding: '5px 6px', textAlign: 'right' }}>
                        {(normalized ? r.RvsPrice : r.fav_raw)?.toFixed(2)}%
                      </td>
                      <td style={{ padding: '5px 6px', textAlign: 'right' }}>
                        {(normalized ? r['HitRate %'] : r.fav_real)?.toFixed(2)}%
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {filtered.length > 200 && (
              <div style={{ padding: 8, textAlign: 'center', fontSize: 10, color: 'var(--text-dim)' }}>
                Showing 200 of {filtered.length} rows
              </div>
            )}
          </div>
        )}

        {view === 'pairs' && !filtered.length && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 200, color: 'var(--text-dim)', fontFamily: 'var(--mono)', fontSize: 12 }}>
            Paste batch output on the left, then click Detect &rarr; Parse
          </div>
        )}

        {/* Errors view */}
        {view === 'errors' && (
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
            {errors.length === 0 ? (
              <div style={{ color: 'var(--green,#22c55e)', padding: 20, textAlign: 'center' }}>
                No parse errors
              </div>
            ) : errors.map((e, i) => (
              <div key={i} style={{ padding: '6px 10px', borderBottom: '1px solid var(--border)',
                color: 'var(--red,#ef4444)' }}>
                Sample {e.sample_id}: {e.error}
              </div>
            ))}
          </div>
        )}

        {/* Validation view */}
        {view === 'valid' && (
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
            {validated.length === 0 ? (
              <div style={{ color: 'var(--text-dim)', padding: 20, textAlign: 'center' }}>
                Click Validate Batch first
              </div>
            ) : validated.map((v, i) => (
              <div key={i} style={{ padding: '6px 10px', borderBottom: '1px solid var(--border)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Sample {v.sample_id}</span>
                <span style={{ color: v.ok ? 'var(--green,#22c55e)' : 'var(--red,#ef4444)' }}>
                  {v.ok ? 'OK' : `Missing: ${v.missing.join(', ')}`}
                </span>
                <span style={{ color: 'var(--text-dim)' }}>{v.pair_count} pairs</span>
              </div>
            ))}
          </div>
        )}

        {/* Winners table */}
        {view === 'winners' && winners.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, fontFamily: 'var(--mono)' }}>
              <thead>
                <tr style={{ color: 'var(--text-dim)', fontSize: 9, letterSpacing: 1,
                  textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: '5px 6px', textAlign: 'center' }}>Rank</th>
                  <th style={{ padding: '5px 6px', textAlign: 'center' }}>S#</th>
                  <th style={{ padding: '5px 6px', textAlign: 'left' }}>
                    {normalized ? 'BUY' : 'Underdog'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'left' }}>
                    {normalized ? 'BUY Hand' : 'Und Hand'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'left' }}>
                    {normalized ? 'REVERSE BUYER' : 'Favourite'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'left' }}>
                    {normalized ? 'REV Hand' : 'Fav Hand'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'right' }}>
                    {normalized ? 'PRICE' : 'Und Raw'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'right' }}>
                    {normalized ? 'Rev Buy Hit %' : 'Und Real'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700 }}>
                    {normalized ? 'EV' : 'Disparity'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'right' }}>
                    {normalized ? 'RvsPrice' : 'Fav Raw'}
                  </th>
                  <th style={{ padding: '5px 6px', textAlign: 'right' }}>
                    {normalized ? 'HitRate %' : 'Fav Real'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {winners.map((r, i) => {
                  const ev = r.disparity ?? r.EV ?? 0
                  const evColor = ev < 0 ? 'var(--green,#22c55e)' : ev > 0 ? 'var(--red,#ef4444)' : 'var(--text-dim)'
                  const isBest = i === 0
                  const isWorst = i === winners.length - 1
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)',
                      background: isBest ? 'rgba(16,185,129,0.06)' :
                                  isWorst ? 'rgba(239,68,68,0.06)' :
                                  i % 2 ? 'rgba(255,255,255,0.02)' : 'transparent' }}>
                      <td style={{ padding: '5px 6px', textAlign: 'center', fontWeight: 700,
                        color: isBest ? 'var(--green,#22c55e)' : isWorst ? 'var(--red,#ef4444)' : 'var(--text-dim)' }}>
                        {r.global_rank ?? i + 1}
                      </td>
                      <td style={{ padding: '5px 6px', textAlign: 'center', color: '#3b82f6' }}>{r.sample_id}</td>
                      <td style={{ padding: '5px 6px' }}>{normalized ? r.BUY : r.underdog_name}</td>
                      <td style={{ padding: '5px 6px', color: 'var(--text-dim)', fontSize: 10 }}>
                        {normalized ? r['BUY Hand'] : r.underdog_hand}
                      </td>
                      <td style={{ padding: '5px 6px' }}>{normalized ? r['REVERSE BUYER'] : r.favourite_name}</td>
                      <td style={{ padding: '5px 6px', color: 'var(--text-dim)', fontSize: 10 }}>
                        {normalized ? r['REVERSE BUYER Hand'] : r.favourite_hand}
                      </td>
                      <td style={{ padding: '5px 6px', textAlign: 'right' }}>
                        {(normalized ? r.PRICE : r.und_raw)?.toFixed(2)}%
                      </td>
                      <td style={{ padding: '5px 6px', textAlign: 'right' }}>
                        {(normalized ? r['Reverse Buy Hit %'] : r.und_real)?.toFixed(2)}%
                      </td>
                      <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700, color: evColor }}>
                        {ev > 0 ? '+' : ''}{ev?.toFixed(4)}%
                      </td>
                      <td style={{ padding: '5px 6px', textAlign: 'right' }}>
                        {(normalized ? r.RvsPrice : r.fav_raw)?.toFixed(2)}%
                      </td>
                      <td style={{ padding: '5px 6px', textAlign: 'right' }}>
                        {(normalized ? r['HitRate %'] : r.fav_real)?.toFixed(2)}%
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        {view === 'winners' && !winners.length && (
          <div style={{ color: 'var(--text-dim)', padding: 20, textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 12 }}>
            Click "Build Winner Dataset" to populate
          </div>
        )}
      </div>
    </div>
  )
}
