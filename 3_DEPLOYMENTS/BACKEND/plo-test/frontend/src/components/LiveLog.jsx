// LiveLog.jsx — renders the raw SSE log output
import { useEffect, useRef } from 'react'

export default function LiveLog({ lines, status }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines.length])

  return (
    <div className="log-box" style={{ flex: 1 }}>
      {lines.length === 0 && status === 'idle' && (
        <span style={{ color: 'var(--text-dim)' }}>
          Configure inputs on the left, then click Run Engine.
        </span>
      )}
      {lines.map((line, i) => {
        const cls = line.includes('__EXIT__')
          ? 'log-line-exit'
          : line.includes('ERR') || line.includes('__ERROR__')
            ? 'log-line-error'
            : ''
        return (
          <span key={i} className={cls}>
            {line}{'\n'}
          </span>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
