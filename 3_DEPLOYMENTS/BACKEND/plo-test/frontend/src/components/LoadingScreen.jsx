// LoadingScreen.jsx — animated splash while auth check runs
import { useEffect, useState } from 'react'

const SUITS = ['\u2660', '\u2665', '\u2666', '\u2663']

export default function LoadingScreen() {
  const [activeSuit, setActiveSuit] = useState(0)
  const [progress,   setProgress]   = useState(0)

  // Cycle suit highlight
  useEffect(() => {
    const id = setInterval(() => {
      setActiveSuit(i => (i + 1) % 4)
    }, 350)
    return () => clearInterval(id)
  }, [])

  // Sweep progress bar
  useEffect(() => {
    let raf
    let start = null
    const duration = 1800
    const step = (ts) => {
      if (!start) start = ts
      const pct = Math.min(((ts - start) / duration) * 90, 90)
      setProgress(pct)
      if (pct < 90) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [])

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 0,
      userSelect: 'none',
    }}>

      {/* Suits */}
      <div style={{
        display: 'flex',
        gap: 18,
        marginBottom: 28,
      }}>
        {SUITS.map((s, i) => (
          <span key={s} style={{
            fontSize: 28,
            transition: 'color 0.25s, transform 0.25s',
            color: activeSuit === i
              ? (i === 1 || i === 2 ? 'var(--red, #ef4444)' : 'var(--accent, #3b82f6)')
              : 'var(--border, #334155)',
            transform: activeSuit === i ? 'scale(1.35)' : 'scale(1)',
            display: 'inline-block',
          }}>
            {s}
          </span>
        ))}
      </div>

      {/* Logo */}
      <div style={{
        fontFamily: 'var(--display, monospace)',
        fontWeight: 700,
        fontSize: 22,
        color: 'var(--accent, #3b82f6)',
        letterSpacing: 3,
        textTransform: 'uppercase',
        marginBottom: 6,
      }}>
        PLO Equity Engine
      </div>

      {/* Domain */}
      <div style={{
        fontFamily: 'var(--mono, monospace)',
        fontSize: 11,
        color: 'var(--text-muted, #64748b)',
        letterSpacing: 4,
        textTransform: 'uppercase',
        marginBottom: 36,
      }}>
        nuts4poker.com
      </div>

      {/* Progress bar */}
      <div style={{
        width: 220,
        height: 3,
        borderRadius: 2,
        background: 'var(--border, #1e293b)',
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${progress}%`,
          borderRadius: 2,
          background: 'var(--accent, #3b82f6)',
          transition: 'width 0.1s linear',
          boxShadow: '0 0 8px var(--accent, #3b82f6)',
        }} />
      </div>

      {/* Label */}
      <div style={{
        marginTop: 14,
        fontFamily: 'var(--mono, monospace)',
        fontSize: 10,
        color: 'var(--text-dim, #475569)',
        letterSpacing: 2,
        textTransform: 'uppercase',
      }}>
        Loading...
      </div>

    </div>
  )
}
