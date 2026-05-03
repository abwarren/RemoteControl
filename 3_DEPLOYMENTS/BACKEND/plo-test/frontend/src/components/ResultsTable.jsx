// ResultsTable.jsx — renders parsed JSON results from /api/results/<job_id>
import { useState, useMemo } from 'react'
import { HandChips } from './CardChip.jsx'
import { downloadResults } from '../api.js'

// EV badge: negative disparity = +EV for BUY, positive = -EV
function formatEvTag(disparity) {
  if (disparity < 0) return '+EV'
  if (disparity > 0) return '-EV'
  return 'NEUTRAL'
}

function DisparityCell({ value, maxAbs }) {
  const pct  = maxAbs > 0 ? Math.min(Math.abs(value) / maxAbs * 100, 100) : 0
  const side = value < 0 ? 'disp-neg' : value > 0 ? 'disp-pos' : ''
  const vcls = value < 0 ? 'neg' : value > 0 ? 'pos' : 'zero'
  const sign = value > 0 ? '+' : ''
  const evTag = formatEvTag(value)
  return (
    <div className="disp-wrap">
      <div className="disp-track">
        {side && <div className={`disp-fill ${side}`} style={{ width: `${pct.toFixed(1)}%` }} />}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <span className={`disp-val ${vcls}`}>{sign}{value.toFixed(4)}%</span>
        <span style={{
          fontSize: 8, fontWeight: 700, letterSpacing: 0.8, padding: '1px 4px',
          borderRadius: 3, textTransform: 'uppercase',
          background: value < 0 ? 'rgba(16,185,129,0.15)' : value > 0 ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.08)',
          color:      value < 0 ? 'var(--accent)'          : value > 0 ? 'var(--red)'           : 'var(--text-dim)',
          border:     value < 0 ? '1px solid rgba(16,185,129,0.3)' : value > 0 ? '1px solid rgba(239,68,68,0.3)' : '1px solid rgba(255,255,255,0.1)',
        }}>{evTag}</span>
      </div>
    </div>
  )
}

// ── Build sample winners table from batch matchups ────────────────────────────────────────
// Presentation-layer filter: one row per sample, rank #1 only.
// The backend (run_batch_worker) already sends exactly one winner per sample
// in data.matchups (the pair with the most negative disparity). This function
// trusts that ordering — it does NOT re-rank or re-pick pairs.
// Rule: only the entry with rank === 1 (or the first/only entry) per sample_num
// is displayed. No 2nd, 3rd, or lower-ranked pairs are rendered.
function buildSampleWinners(matchups) {
  // Step 1 — collect exactly one row per sample_num.
  // The backend sends one winner per sample; we guard against any accidental
  // duplicates by keeping only the most-negative-disparity entry per sample.
  const bySample = new Map()
  for (const row of matchups) {
    const sid = row.sample_num ?? 0
    const existing = bySample.get(sid)
    // Keep only rank === 1 from backend, or the entry with lowest disparity
    const rowRank = row.rank ?? 1
    if (!existing || rowRank === 1 || row.disparity < existing.disparity) {
      bySample.set(sid, row)
    }
  }

  // Step 2 — build display rows from the single winner per sample.
  const winners = Array.from(bySample.entries()).map(([sid, best]) => ({
    sample_id:      sid,
    rank:           1,   // always rank 1 — this IS the #1 pair for the sample
    pair_num:       best.pair_num ?? best.rank ?? '—',
    underdog_hand:  best.underdog_hand,
    underdog_name:  best.underdog_name,
    favourite_hand: best.favourite_hand,
    favourite_name: best.favourite_name,
    und_raw:        best.und_raw,
    und_real:       best.und_real,
    disparity:      best.disparity,
    fav_raw:        best.fav_raw,
    fav_real:       best.fav_real,
  }))

  // Step 3 — sort winners globally by disparity ascending
  // (most negative = strongest BUY signal = global rank 1).
  // This is a display sort only — no data is changed.
  winners.sort((a, b) => a.disparity - b.disparity)
  winners.forEach((w, i) => { w.rank_across_batch = i + 1 })
  return winners
}

// ── Rank pattern from a hand string e.g. "AhKsQdJcTd" -> "AKQJT" ──────────────────────────
const RANK_ORDER = 'AKQJT98765432'
function rankPattern(handStr) {
  if (!handStr) return '?'
  const ranks = (handStr.match(/.{2}/g) || []).map(c => c[0])
  return [...ranks]
    .sort((a, b) => RANK_ORDER.indexOf(a) - RANK_ORDER.indexOf(b))
    .join('')
}

// ── Build frequency table from top_pairs ─────────────────────────────────────────────────
function buildFrequency(topPairs, totalSamples) {
  // Count how often each rank pattern appears as UNDERDOG in top-N pairs
  const map = {}
  for (const p of topPairs) {
    const key = rankPattern(p.underdog_hand)
    if (!map[key]) map[key] = {
      pattern: key, count: 0, samples: new Set(),
      dispSum: 0, dispBest: Infinity,
      undRawSum: 0, undRealSum: 0,
      appearances: [],
    }
    const e = map[key]
    e.count++
    e.samples.add(p.sample_num)
    e.dispSum   += p.disparity
    e.undRawSum += p.und_raw
    e.undRealSum += p.und_real
    if (p.disparity < e.dispBest) e.dispBest = p.disparity
    e.appearances.push(p)
  }
  return Object.values(map)
    .map(e => ({
      pattern:      e.pattern,
      count:        e.count,
      uniqueSamples: e.samples.size,
      pctSamples:   (e.samples.size / totalSamples * 100),
      avgDisparity: e.dispSum   / e.count,
      bestDisparity: e.dispBest,
      avgUndRaw:    e.undRawSum / e.count,
      avgUndReal:   e.undRealSum / e.count,
      appearances:  e.appearances,
    }))
    .sort((a, b) => b.count - a.count || a.avgDisparity - b.avgDisparity)
}

// ── Batch results section ──────────────────────────────────────────────────────────────────
function BatchResults({ data, jobId }) {
  const [view, setView] = useState('winners')   // 'winners' | 'all' | 'freq'

  const topN       = data.top_n || 5
  const topPairs   = useMemo(() => data.top_pairs ? [...data.top_pairs].sort((a, b) => a.disparity - b.disparity) : [], [data.top_pairs])
  const allPairs   = useMemo(() => [...data.matchups].sort((a, b) => a.disparity - b.disparity), [data.matchups])
  const winners    = useMemo(() => buildSampleWinners(data.matchups), [data.matchups])
  const freqRows   = useMemo(() => buildFrequency(topPairs, data.total_samples), [topPairs, data.total_samples])
  const maxAbsWin  = useMemo(() => Math.max(...winners.map(r => Math.abs(r.disparity)), 0), [winners])
  const maxAbsAll  = useMemo(() => Math.max(...allPairs.map(r => Math.abs(r.disparity)), 0), [allPairs])

  const best  = winners[0]
  const worst = winners[winners.length - 1]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 10, overflowY: 'auto' }}>

      {/* ── Header ── */}
      <div className="results-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontFamily: 'var(--display)', fontWeight: 700, fontSize: 13, color: '#3b82f6', letterSpacing: 1 }}>
            BATCH
          </span>
          <div className="results-meta">
            <span><b>{data.total_samples}</b> samples</span>
            <span><b>{data.valid_samples}</b> valid</span>
            {data.street && <span>{data.street}</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 5, alignItems: 'center', fontSize: 10, color: 'var(--text-muted)' }}>
            <span style={{ color: 'var(--accent)' }}>▼ NEG</span> = BUY gains
            <span style={{ color: 'var(--red)', marginLeft: 8 }}>▲ POS</span> = BUY loses
          </div>
          {jobId && (
            <button className="btn btn-ghost btn-sm" onClick={() => downloadResults(jobId)}>
              ↓ Download
            </button>
          )}
        </div>
      </div>

      {/* ── Best overall card ── */}
      {best && (
        <div style={{
          background: '#061310',
          border: '1px solid rgba(16,185,129,0.35)',
          borderRadius: 'var(--radius)',
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          flexWrap: 'wrap',
        }}>
          <span style={{ fontFamily: 'var(--display)', fontSize: 9, fontWeight: 700, letterSpacing: 2, color: '#065f46', textTransform: 'uppercase' }}>
            ★ Best Overall
          </span>
          <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>Sample {best.sample_id}</span>
          <HandChips hand={best.underdog_hand} name={best.underdog_name} />
          <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>vs</span>
          <HandChips hand={best.favourite_hand} name={best.favourite_name} />
          <span style={{ marginLeft: 'auto', fontWeight: 700, color: 'var(--accent)', fontFamily: 'var(--mono)', fontSize: 12 }}>
            {best.disparity.toFixed(4)}%
          </span>
        </div>
      )}

      {/* ── View toggle ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
        <div className="view-toggle">
          <button className={view === 'winners' ? 'active' : ''} onClick={() => setView('winners')}>
            Best BUY per Sample
          </button>
          <button className={view === 'all' ? 'active' : ''} onClick={() => setView('all')}>
            All Pairs ({allPairs.length})
          </button>
          {topPairs.length > 0 && (
            <button className={view === 'freq' ? 'active' : ''} onClick={() => setView('freq')}>
              ⟳ Hand Frequency
            </button>
          )}
        </div>
        <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>
          {view === 'winners' && `${winners.length} sample winners · ranked globally`}
          {view === 'all'     && `${allPairs.length} total pairs across all samples`}
          {view === 'freq'    && `Top-${topN} per sample · ${topPairs.length} appearances · ${freqRows.length} unique patterns`}
        </span>
      </div>

            {/* ── Winners table ── */}
      {/* Displays exactly ONE row per sample: the #1-ranked pair only.      */}
      {/* No 2nd, 3rd, or lower-ranked pairs are rendered here.              */}
      {/* Source data (data.matchups) is untouched — presentation filter only. */}
      {view === 'winners' && (
        <div className="results-wrap">
          {winners.length === 0 ? (
            <div className="panel" style={{ color: 'var(--text-dim)', fontSize: 12, textAlign: 'center', padding: '40px 20px' }}>
              NO_RESULT — no ranked pairs found in this batch
            </div>
          ) : (
          <table className="results-table">
            <thead>
              <tr>
                <th className="c" title="Global rank across all sample winners">Global Rank</th>
                <th className="c" title="Sample number">Sample</th>
                <th className="c" title="Always 1 — only the #1-ranked pair per sample is shown">Pair Rank</th>
                <th className="c" title="Pair number within the sample">Pair #</th>
                <th className="left">BUY (Underdog)</th>
                <th className="left">SELL (Favourite)</th>
                <th title="Underdog raw equity — PRICE">PRICE</th>
                <th title="Underdog realized equity — Rev Buy Hit %">Rev Buy Hit %</th>
                <th title="Realized minus Raw — Disparity / EV">Disparity (EV)</th>
                <th title="Favourite raw equity">RvsPrice</th>
                <th title="Favourite realized equity">HitRate %</th>
              </tr>
            </thead>
            <tbody>
              {winners.map((row, idx) => {
                const isBest  = idx === 0
                const isWorst = idx === winners.length - 1
                const rowCls  = isBest ? 'row-best' : isWorst ? 'row-worst' : idx % 2 === 0 ? 'row-even' : 'row-odd'
                // Safety check: if a sample returned no result, show NO_RESULT
                const hasData = row.underdog_hand && row.favourite_hand &&
                                row.und_raw != null && row.disparity != null
                return (
                  <tr key={row.sample_id} className={rowCls}>
                    <td className="c" style={{ fontWeight: 700, color: isBest ? 'var(--accent)' : isWorst ? 'var(--red)' : 'var(--text-muted)' }}>
                      {isBest ? '★' : isWorst ? '▲' : ''} {row.rank_across_batch}
                    </td>
                    <td className="c" style={{ fontWeight: 600, color: '#3b82f6' }}>{row.sample_id}</td>
                    <td className="c" style={{ color: 'var(--accent)', fontWeight: 700, fontSize: 10 }}>1</td>
                    <td className="c muted">{hasData ? row.pair_num : '—'}</td>
                    {hasData ? (
                      <>
                        <td className="left"><HandChips hand={row.underdog_hand} name={row.underdog_name} /></td>
                        <td className="left"><HandChips hand={row.favourite_hand} name={row.favourite_name} /></td>
                        <td className="pct-raw">{row.und_raw.toFixed(4)}%</td>
                        <td className="pct-real">{row.und_real.toFixed(4)}%</td>
                        <td><DisparityCell value={row.disparity} maxAbs={maxAbsWin} /></td>
                        <td className="pct-raw">{row.fav_raw.toFixed(4)}%</td>
                        <td className="pct-real">{row.fav_real.toFixed(4)}%</td>
                      </>
                    ) : (
                      <td colSpan={7} style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)', fontSize: 11 }}>
                        NO_RESULT
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
          )}
        </div>
      )}

      {/* ── Hand Frequency table ── */}
      {view === 'freq' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Explainer */}
          <div style={{
            padding: '8px 12px', borderRadius: 4, fontSize: 10, lineHeight: 1.6,
            background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)',
            color: 'var(--text-muted)',
          }}>
            Each sample keeps its <b style={{ color: 'var(--blue, #3b82f6)' }}>top-{topN} pairs</b> by disparity.
            This table shows which <b>underdog rank patterns</b> (suits removed) appeared most often
            in those top-{topN} slots across all {data.total_samples} samples —
            revealing hand structures that <em>consistently</em> over-realize equity.
          </div>

          <div className="results-wrap">
            <table className="results-table">
              <thead>
                <tr>
                  <th className="c">#</th>
                  <th className="left">Rank Pattern</th>
                  <th className="c" title="Times appeared in top-N across all samples">Appearances</th>
                  <th className="c" title="Number of distinct samples this appeared in">Samples</th>
                  <th className="c" title="% of total samples">% Samples</th>
                  <th title="Average disparity when this pattern appears as underdog">Avg Disparity</th>
                  <th title="Best (most negative) disparity recorded">Best Disparity</th>
                  <th title="Average underdog raw equity">Avg Und Raw</th>
                  <th title="Average underdog realized equity">Avg Und Real</th>
                </tr>
              </thead>
              <tbody>
                {freqRows.map((row, idx) => {
                  const isTop = idx === 0
                  const rowCls = isTop ? 'row-best' : idx % 2 === 0 ? 'row-even' : 'row-odd'
                  const dispSign = row.avgDisparity > 0 ? '+' : ''
                  const bestSign = row.bestDisparity > 0 ? '+' : ''
                  return (
                    <tr key={row.pattern} className={rowCls}>
                      <td className="c muted">{isTop ? '★' : idx + 1}</td>
                      <td className="left">
                        <span style={{
                          fontFamily: 'var(--mono)', fontWeight: 700, letterSpacing: 2,
                          fontSize: 12,
                          color: isTop ? 'var(--accent)' : 'var(--text)',
                        }}>
                          {row.pattern}
                        </span>
                        <span style={{ fontSize: 9, color: 'var(--text-dim)', marginLeft: 8 }}>
                          {row.pattern.length} cards
                        </span>
                      </td>
                      <td className="c" style={{ fontWeight: 700, color: isTop ? 'var(--accent)' : 'var(--text)' }}>
                        {row.count}
                      </td>
                      <td className="c muted">{row.uniqueSamples}</td>
                      <td className="c">
                        <span style={{
                          fontFamily: 'var(--mono)', fontSize: 11,
                          color: row.pctSamples >= 10 ? 'var(--accent)' : 'var(--text-muted)',
                        }}>
                          {row.pctSamples.toFixed(1)}%
                        </span>
                      </td>
                      <td>
                        <span style={{
                          fontFamily: 'var(--mono)', fontSize: 11,
                          color: row.avgDisparity < 0 ? 'var(--accent)' : 'var(--red)',
                        }}>
                          {dispSign}{row.avgDisparity.toFixed(4)}%
                        </span>
                      </td>
                      <td>
                        <span style={{
                          fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700,
                          color: row.bestDisparity < 0 ? 'var(--accent)' : 'var(--red)',
                        }}>
                          {bestSign}{row.bestDisparity.toFixed(4)}%
                        </span>
                      </td>
                      <td className="pct-raw">{row.avgUndRaw.toFixed(2)}%</td>
                      <td className="pct-real">{row.avgUndReal.toFixed(2)}%</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── All pairs table ── */}
      {view === 'all' && (
        <div className="results-wrap">
          <table className="results-table">
            <thead>
              <tr>
                <th className="c">#</th>
                <th className="c">Sample</th>
                <th className="c">Pair #</th>
                <th className="left">BUY (Underdog)</th>
                <th className="left">SELL (Favourite)</th>
                <th>PRICE</th>
                <th>Rev Buy Hit %</th>
                <th>Disparity</th>
                <th>RvsPrice</th>
                <th>HitRate %</th>
              </tr>
            </thead>
            <tbody>
              {allPairs.map((row, idx) => {
                const isBest  = idx === 0
                const isWorst = idx === allPairs.length - 1
                const rowCls  = isBest ? 'row-best' : isWorst ? 'row-worst' : idx % 2 === 0 ? 'row-even' : 'row-odd'
                return (
                  <tr key={idx} className={rowCls}>
                    <td className="c muted">{idx + 1}{isBest ? ' ★' : isWorst ? ' ▲' : ''}</td>
                    <td className="c" style={{ fontWeight: 600, color: '#3b82f6' }}>{row.sample_num}</td>
                    <td className="c muted">{row.pair_num ?? row.rank ?? '—'}</td>
                    <td className="left"><HandChips hand={row.underdog_hand} name={row.underdog_name} /></td>
                    <td className="left"><HandChips hand={row.favourite_hand} name={row.favourite_name} /></td>
                    <td className="pct-raw">{row.und_raw.toFixed(4)}%</td>
                    <td className="pct-real">{row.und_real.toFixed(4)}%</td>
                    <td><DisparityCell value={row.disparity} maxAbs={maxAbsAll} /></td>
                    <td className="pct-raw">{row.fav_raw.toFixed(4)}%</td>
                    <td className="pct-real">{row.fav_real.toFixed(4)}%</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Footer: best vs worst winner ── */}
      {best && worst && winners.length > 1 && (
        <div className="results-footer">
          <div className="foot-card neg">
            <div className="foot-label">★ Best BUY — Sample {best.sample_id} · Rank 1</div>
            <div className="foot-hands">
              <HandChips hand={best.underdog_hand} name={best.underdog_name} />
              <span className="foot-vs">vs</span>
              <HandChips hand={best.favourite_hand} name={best.favourite_name} />
            </div>
            <div className="foot-stats">
              <div className="foot-stat"><div className="stat-lbl">PRICE</div><div className="stat-val">{best.und_raw.toFixed(4)}%</div></div>
              <div className="foot-stat"><div className="stat-lbl">Rev Buy Hit %</div><div className="stat-val">{best.und_real.toFixed(4)}%</div></div>
              <div className="foot-stat"><div className="stat-lbl">EV</div><div className="stat-val">{best.disparity.toFixed(4)}%</div></div>
            </div>
          </div>
          <div className="foot-card pos">
            <div className="foot-label">▲ Worst BUY — Sample {worst.sample_id} · Rank {worst.rank_across_batch}</div>
            <div className="foot-hands">
              <HandChips hand={worst.underdog_hand} name={worst.underdog_name} />
              <span className="foot-vs">vs</span>
              <HandChips hand={worst.favourite_hand} name={worst.favourite_name} />
            </div>
            <div className="foot-stats">
              <div className="foot-stat"><div className="stat-lbl">PRICE</div><div className="stat-val">{worst.und_raw.toFixed(4)}%</div></div>
              <div className="foot-stat"><div className="stat-lbl">Rev Buy Hit %</div><div className="stat-val">{worst.und_real.toFixed(4)}%</div></div>
              <div className="foot-stat"><div className="stat-lbl">EV</div><div className="stat-val">+{worst.disparity.toFixed(4)}%</div></div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ResultsTable({ data, jobId }) {
  if (!data || !data.matchups) return null
  if (data.batch_results) return <BatchResults data={data} jobId={jobId} />

  // ── Single-run mode ───────────────────────────────────────────────────────────────
  const { street, runtime, cores, pairs_evaluated } = data
  // Sort ASC: most negative disparity = most +EV = rank 1
  const sorted = [...data.matchups].sort((a, b) => a.disparity - b.disparity)
  const maxAbs = Math.max(...sorted.map(r => Math.abs(r.disparity)), 0)
  const best   = sorted[0]
  const worst  = sorted[sorted.length - 1]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 10, overflowY: 'auto' }}>
      {/* Header */}
      <div className="results-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontFamily: 'var(--display)', fontWeight: 700, fontSize: 13, color: 'var(--accent)', letterSpacing: 1 }}>
            {street}
          </span>
          <div className="results-meta">
            <span><b>{pairs_evaluated}</b> pairs</span>
            <span><b>{cores}</b> cores</span>
            <span><b>{runtime}</b></span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ display: 'flex', gap: 5, alignItems: 'center', fontSize: 10, color: 'var(--text-muted)' }}>
            <span style={{ color: 'var(--accent)' }}>▼ NEG</span> = BUY gains
            <span style={{ color: 'var(--red)', marginLeft: 8 }}>▲ POS</span> = BUY loses
          </div>
          {jobId && (
            <button className="btn btn-ghost btn-sm" onClick={() => downloadResults(jobId)}>
              ↓ Download
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="results-wrap">
        <table className="results-table">
          <thead>
            <tr>
              <th className="c">#</th>
              <th className="c">Pair</th>
              <th className="left">BUY</th>
              <th className="left">REVERSE BUYER</th>
              <th>PRICE</th>
              <th>Rev Buy Hit %</th>
              <th title="Sorted ASC: most negative = most +EV">Disparity ASC (+EV)</th>
              <th>RvsPrice</th>
              <th>HitRate %</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, idx) => {
              const isBest  = idx === 0
              const isWorst = idx === sorted.length - 1
              const rowCls  = isBest
                ? 'row-best'
                : isWorst
                  ? 'row-worst'
                  : idx % 2 === 0 ? 'row-even' : 'row-odd'
              return (
                <tr key={idx} className={rowCls}>
                  <td className="c muted">{idx + 1}{isBest ? ' ★' : isWorst ? ' ▲' : ''}</td>
                  <td className="c muted">{row.pair_num}</td>
                  <td className="left">
                    <HandChips hand={row.underdog_hand} name={row.underdog_name} />
                  </td>
                  <td className="left">
                    <HandChips hand={row.favourite_hand} name={row.favourite_name} />
                  </td>
                  <td className="pct-raw">{row.und_raw.toFixed(4)}%</td>
                  <td className="pct-real">{row.und_real.toFixed(4)}%</td>
                  <td>
                    <DisparityCell value={row.disparity} maxAbs={maxAbs} />
                  </td>
                  <td className="pct-raw">{row.fav_raw.toFixed(4)}%</td>
                  <td className="pct-real">{row.fav_real.toFixed(4)}%</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Footer summary */}
      {best && worst && (
        <div className="results-footer">
          <div className="foot-card neg">
            <div className="foot-label">★ Most Negative — Best BUY</div>
            <div className="foot-hands">
              <HandChips hand={best.underdog_hand} name={best.underdog_name} />
              <span className="foot-vs">vs</span>
              <HandChips hand={best.favourite_hand} name={best.favourite_name} />
            </div>
            <div className="foot-stats">
              <div className="foot-stat">
                <div className="stat-lbl">PRICE</div>
                <div className="stat-val">{best.und_raw.toFixed(4)}%</div>
              </div>
              <div className="foot-stat">
                <div className="stat-lbl">Rev Buy Hit %</div>
                <div className="stat-val">{best.und_real.toFixed(4)}%</div>
              </div>
              <div className="foot-stat">
                <div className="stat-lbl">EV</div>
                <div className="stat-val">{best.disparity.toFixed(4)}%</div>
              </div>
            </div>
          </div>

          <div className="foot-card pos">
            <div className="foot-label">▲ Most Positive — Worst BUY</div>
            <div className="foot-hands">
              <HandChips hand={worst.underdog_hand} name={worst.underdog_name} />
              <span className="foot-vs">vs</span>
              <HandChips hand={worst.favourite_hand} name={worst.favourite_name} />
            </div>
            <div className="foot-stats">
              <div className="foot-stat">
                <div className="stat-lbl">PRICE</div>
                <div className="stat-val">{worst.und_raw.toFixed(4)}%</div>
              </div>
              <div className="foot-stat">
                <div className="stat-lbl">Rev Buy Hit %</div>
                <div className="stat-val">{worst.und_real.toFixed(4)}%</div>
              </div>
              <div className="foot-stat">
                <div className="stat-lbl">EV</div>
                <div className="stat-val">+{worst.disparity.toFixed(4)}%</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
