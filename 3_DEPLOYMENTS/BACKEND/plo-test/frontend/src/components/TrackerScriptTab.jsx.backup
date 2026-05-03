import { useState } from 'react'

const TM_SCRIPT = `$(cat /opt/plo-equity/static/plosnapshot_tampermonkey.user.js)`

function CopyBlock({ label, code }) {
  const [copied, setCopied] = useState(false)
  const copy = () => navigator.clipboard.writeText(code).then(() => {
    setCopied(true); setTimeout(() => setCopied(false), 2000)
  })
  return (
    <div style={{ background: '#07090f', border: '1px solid #333', borderRadius: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: 12, background: '#0d1117' }}>
        <span style={{ color: '#3b82f6', fontWeight: 'bold' }}>{label}</span>
        <button onClick={copy}>{copied ? 'Copied!' : 'Copy'}</button>
      </div>
      <pre style={{ margin: 0, padding: 12, color: '#8ea3c3', fontSize: 11, overflow: 'auto', maxHeight: 300 }}>
        {code}
      </pre>
    </div>
  )
}

export default function TrackerScriptTab() {
  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 20 }}>
      <CopyBlock label="PLO Hand Tracker v2.5.0 - Full Version" code={TM_SCRIPT} />
    </div>
  )
}
