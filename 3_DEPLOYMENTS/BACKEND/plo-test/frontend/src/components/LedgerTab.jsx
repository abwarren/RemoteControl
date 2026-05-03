// LedgerTab.jsx -- Per-hand ZAR Value & P/L tracker
import { useState, useMemo } from 'react'

const STORAGE_KEY = 'plo_ledger'
const MAX_HANDS   = 500

const load = () => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') } catch { return [] } }
const save = (d) => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(d)) } catch {} }

const fmtR    = (v) => 'R ' + Math.abs(v).toFixed(2)
const plColor = (v) => v > 0 ? 'var(--green, #22c55e)' : v < 0 ? 'var(--red, #ef4444)' : 'var(--text-dim)'
const plSign  = (v) => v > 0 ? '+' : v < 0 ? '-' : ''

export default function LedgerTab() {
  const [entries, setEntries] = useState(load)
  const [form,    setForm]    = useState({ hand: '', name: '', zarValue: '', pl: '' })
  const [last50,   setLast50]  = useState(false)

  const persist = (updated) => { setEntries(updated); save(updated) }

  const nextHand = useMemo(() =>
    entries.length ? Math.max(...entries.map(e => e.hand)) + 1 : 1
  , [entries])

  const displayEntries = useMemo(() =>
    last50 ? [...entries].slice(-50) : entries
  , [entries, last50])

  const addEntry = () => {
    if (!form.name.trim() || form.zarValue === '') return
    const entry = {
      id:       Date.now(),
      hand:     parseInt(form.hand)       || nextHand,
      name:     form.name.trim(),
      zarValue: parseFloat(form.zarValue) || 0,
      pl:       parseFloat(form.pl)       || 0,
    }
    const updated = [...entries, entry]
      .sort((a, b) => a.hand - b.hand || a.name.localeCompare(b.name))
      .slice(0, MAX_HANDS)
    persist(updated)
    setForm(p => ({ hand: '', name: p.name, zarValue: '', pl: '' }))
  }

  const deleteEntry = (id) => persist(entries.filter(e => e.id !== id))
  const clearAll    = ()  => { if (window.confirm('Clear all ledger entries?')) persist([]) }

  const printLedger = () => {
    const rows = displayEntries.map(e =>
      '<tr><td>#'+e.hand+'</td><td>'+e.name+'</td><td>R '+e.zarValue.toFixed(2)+'</td><td>'+(e.pl>=0?'+':'')+e.pl.toFixed(2)+'</td></tr>'
    ).join('')
    const sumRows = summary.map(r =>
      '<tr><td><b>'+r.name+'</b></td><td>'+r.hands+'</td><td>R '+r.totalZar.toFixed(2)+'</td><td>'+(r.totalPl>=0?'+':'')+r.totalPl.toFixed(2)+'</td></tr>'
    ).join('')
    const w = window.open('','_blank')
    w.document.write('<html><head><title>PLO Ledger</title><style>body{font-family:monospace;padding:20px}table{border-collapse:collapse;width:100%;margin-bottom:20px}th,td{border:1px solid #ccc;padding:6px 10px}th{background:#f0f0f0}</style></head><body><h2>PLO Ledger -- nuts4poker.com</h2><p>'+new Date().toLocaleString()+' | '+displayEntries.length+' entries'+(last50?' (last 50)':'')+' </p><table><thead><tr><th>Hand</th><th>Player</th><th>ZAR Value</th><th>P/L</th></tr></thead><tbody>'+rows+'</tbody></table><h2>Player Totals</h2><table><thead><tr><th>Name</th><th>Hands</th><th>ZAR</th><th>P/L</th></tr></thead><tbody>'+sumRows+'</tbody></table></body></html>')
    w.document.close(); w.print()
  }

  const summary = useMemo(() => {
    const map = {}
    entries.forEach(e => {
      if (!map[e.name]) map[e.name] = { name: e.name, totalZar: 0, totalPl: 0, hands: 0 }
      map[e.name].totalZar += e.zarValue
      map[e.name].totalPl  += e.pl
      map[e.name].hands    += 1
    })
    return Object.values(map).sort((a, b) => b.totalPl - a.totalPl)
  }, [entries])

  const grandZar = summary.reduce((s, r) => s + r.totalZar, 0)
  const grandPl  = summary.reduce((s, r) => s + r.totalPl,  0)

  const TH = ({ right, children }) => (
    <th style={{ textAlign: right ? 'right' : 'left', padding: '5px 8px',
      color: 'var(--text-dim)', fontWeight: 600, fontSize: 10,
      letterSpacing: 1, textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>
      {children}
    </th>
  )

  return (
    <div className="engine-layout">

      {/* LEFT -- form + summary */}
      <div className="engine-left">
        <div className="panel">
          <div className="panel-title">Add Hand Entry</div>

          {[
            { label: 'Hand #',     key: 'hand',     type: 'number', ph: String(nextHand) },
            { label: 'Player Name',key: 'name',     type: 'text',   ph: 'e.g. Hero' },
            { label: 'ZAR Value',  key: 'zarValue', type: 'number', ph: '0.00' },
            { label: 'P/L (R)',    key: 'pl',       type: 'number', ph: '0.00 (loss = negative)' },
          ].map(({ label, key, type, ph }) => (
            <div className="field-group" key={key}>
              <label>{label}</label>
              <input type={type} placeholder={ph} value={form[key]}
                onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))}
                onKeyDown={e => e.key === 'Enter' && addEntry()}
                style={{ fontFamily: 'var(--mono)', fontSize: 12 }} />
            </div>
          ))}

          <button className="btn btn-primary btn-sm"
            style={{ width: '100%', marginBottom: 6 }}
            onClick={addEntry}
            disabled={!form.name.trim() || form.zarValue === ''}>
            + Add Entry
          </button>
          <button className="btn btn-secondary btn-sm"
            style={{ width: '100%' }}
            onClick={clearAll} disabled={!entries.length}>
            Clear All
          </button>
        </div>

        {summary.length > 0 && (
          <div className="panel" style={{ flex: 1 }}>
            <div className="panel-title">Player Totals</div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, fontFamily: 'var(--mono)' }}>
              <thead>
                <tr><TH>Name</TH><TH right>Hands</TH><TH right>ZAR</TH><TH right>P/L</TH></tr>
              </thead>
              <tbody>
                {summary.map(r => (
                  <tr key={r.name} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '5px 8px', color: 'var(--text)' }}>{r.name}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', color: 'var(--text-dim)' }}>{r.hands}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', color: 'var(--text)' }}>{fmtR(r.totalZar)}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', fontWeight: 700, color: plColor(r.totalPl) }}>
                      {plSign(r.totalPl)}{fmtR(r.totalPl)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr style={{ borderTop: '2px solid var(--border)' }}>
                  <td style={{ padding: '6px 8px', fontWeight: 700, color: 'var(--text)' }}>TOTAL</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', color: 'var(--text-dim)' }}>{entries.length}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, color: 'var(--text)' }}>{fmtR(grandZar)}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, color: plColor(grandPl) }}>
                    {plSign(grandPl)}{fmtR(grandPl)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

      {/* RIGHT -- hand log */}
      <div className="engine-right">
        <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>
            {displayEntries.length}{last50 ? ' (last 50)' : ''} of {entries.length} {entries.length === 1 ? 'entry' : 'entries'}
          </span>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className={'btn btn-sm ' + (last50 ? 'btn-primary' : 'btn-secondary')} style={{ fontSize: 10, padding: '3px 8px' }} onClick={() => setLast50(v => !v)}>
              {last50 ? 'All Hands' : 'Last 50'}
            </button>
            <button className="btn btn-secondary btn-sm" style={{ fontSize: 10, padding: '3px 8px' }} onClick={printLedger} disabled={!entries.length}>
              Print / Export
            </button>
          </div>
        </div>

        {!entries.length ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 200, color: 'var(--text-dim)', fontFamily: 'var(--mono)', fontSize: 12 }}>
            No entries yet &mdash; add your first hand on the left
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: 'var(--mono)' }}>
              <thead>
                <tr style={{ color: 'var(--text-dim)', fontSize: 10, letterSpacing: 1,
                  textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ textAlign: 'left',  padding: '6px 10px' }}>Hand #</th>
                  <th style={{ textAlign: 'left',  padding: '6px 10px' }}>Name</th>
                  <th style={{ textAlign: 'right', padding: '6px 10px' }}>ZAR Value</th>
                  <th style={{ textAlign: 'right', padding: '6px 10px' }}>P/L</th>
                  <th style={{ width: 30 }}></th>
                </tr>
              </thead>
              <tbody>
                {displayEntries.map((e, i) => (
                  <tr key={e.id} style={{ borderBottom: '1px solid var(--border)',
                    background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                    <td style={{ padding: '7px 10px', color: 'var(--text-dim)' }}>#{e.hand}</td>
                    <td style={{ padding: '7px 10px', color: 'var(--text)', fontWeight: 500 }}>{e.name}</td>
                    <td style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text)' }}>R {e.zarValue.toFixed(2)}</td>
                    <td style={{ padding: '7px 10px', textAlign: 'right', fontWeight: 600, color: plColor(e.pl) }}>
                      {plSign(e.pl)}R {Math.abs(e.pl).toFixed(2)}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button onClick={() => deleteEntry(e.id)} title="Delete"
                        style={{ background: 'none', border: 'none', cursor: 'pointer',
                          color: 'var(--text-dim)', fontSize: 13, padding: '0 6px' }}>
                        &#x2715;
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
