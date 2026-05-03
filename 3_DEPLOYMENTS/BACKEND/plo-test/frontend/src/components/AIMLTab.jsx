// AIMLTab.jsx — AI / ML analysis hub with poker table centrepiece
import { useState } from 'react'

/* ── CSS-drawn poker table — matches the reference image exactly ─────────── */
function PokerTable({ children }) {
  return (
    <div style={{
      /* wooden floor tiles */
      background: `
        repeating-linear-gradient(
          90deg,
          transparent,
          transparent 79px,
          rgba(0,0,0,0.18) 79px,
          rgba(0,0,0,0.18) 82px
        ),
        repeating-linear-gradient(
          0deg,
          transparent,
          transparent 79px,
          rgba(0,0,0,0.18) 79px,
          rgba(0,0,0,0.18) 82px
        ),
        linear-gradient(135deg, #a0622a 0%, #c8832e 25%, #b06e22 50%, #c8832e 75%, #a0622a 100%)
      `,
      borderRadius: 12,
      padding: '40px 32px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 420,
    }}>
      {/* wood rail */}
      <div style={{
        position: 'relative',
        width: '100%',
        maxWidth: 740,
        aspectRatio: '1.85 / 1',
        borderRadius: '50%',
        background: 'linear-gradient(145deg, #c8832e 0%, #e09a40 30%, #b06e22 60%, #8a5218 100%)',
        boxShadow: '0 8px 40px rgba(0,0,0,0.6), inset 0 2px 6px rgba(255,200,80,0.25), inset 0 -4px 12px rgba(0,0,0,0.4)',
        padding: 22,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        {/* felt surface */}
        <div style={{
          width: '100%',
          height: '100%',
          borderRadius: '50%',
          background: 'radial-gradient(ellipse at 40% 35%, #2d8a4e 0%, #1e6b38 50%, #164f2a 100%)',
          boxShadow: 'inset 0 4px 20px rgba(0,0,0,0.35), inset 0 -2px 10px rgba(0,0,0,0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          overflow: 'hidden',
        }}>
          {/* betting line oval */}
          <div style={{
            position: 'absolute',
            inset: '12% 10%',
            borderRadius: '50%',
            border: '2px solid rgba(144,238,144,0.55)',
            boxShadow: '0 0 6px rgba(144,238,144,0.2)',
            pointerEvents: 'none',
          }} />
          {/* felt texture grain */}
          <div style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            background: `repeating-linear-gradient(
              45deg,
              transparent,
              transparent 2px,
              rgba(0,0,0,0.04) 2px,
              rgba(0,0,0,0.04) 4px
            )`,
            pointerEvents: 'none',
          }} />
          {/* content sits on the felt */}
          <div style={{ position: 'relative', zIndex: 1, width: '75%', textAlign: 'center' }}>
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── placeholder stat chip ───────────────────────────────────────────────── */
function Chip({ label, value, sub, color = '#22c55e' }) {
  return (
    <div style={{
      display: 'inline-flex', flexDirection: 'column', alignItems: 'center',
      background: 'rgba(0,0,0,0.55)', border: `1px solid ${color}44`,
      borderRadius: 10, padding: '10px 18px', minWidth: 90,
      backdropFilter: 'blur(4px)',
    }}>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 20, fontWeight: 700, color, lineHeight: 1 }}>{value}</span>
      <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.55)', marginTop: 4, textTransform: 'uppercase', letterSpacing: 1 }}>{label}</span>
      {sub && <span style={{ fontSize: 8, color: 'rgba(255,255,255,0.35)', marginTop: 2 }}>{sub}</span>}
    </div>
  )
}

/* ── coming-soon feature card ────────────────────────────────────────────── */
function FeatureCard({ icon, title, desc, badge }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: '14px 16px',
      display: 'flex', alignItems: 'flex-start', gap: 12,
    }}>
      <span style={{ fontSize: 22, lineHeight: 1, marginTop: 1 }}>{icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontFamily: 'var(--display)', fontWeight: 700, fontSize: 12, color: 'var(--text)' }}>{title}</span>
          {badge && (
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase',
              background: 'rgba(59,130,246,0.15)', color: '#60a5fa',
              border: '1px solid rgba(59,130,246,0.3)',
              borderRadius: 4, padding: '1px 6px',
            }}>{badge}</span>
          )}
        </div>
        <p style={{ margin: 0, fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.6 }}>{desc}</p>
      </div>
    </div>
  )
}

/* ── main component ──────────────────────────────────────────────────────── */
export default function AIMLTab() {
  const [hovered, setHovered] = useState(null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 960, margin: '0 auto', padding: '4px 0' }}>

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <h2 style={{ margin: 0, fontFamily: 'var(--display)', fontSize: 18, fontWeight: 700, color: 'var(--text)', letterSpacing: 1 }}>
          AI / ML
        </h2>
        <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>Analysis &amp; Machine Learning Pipeline</span>
        <span style={{
          marginLeft: 'auto', fontSize: 9, fontWeight: 700, letterSpacing: 1.5,
          textTransform: 'uppercase', color: '#f59e0b',
          background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)',
          borderRadius: 4, padding: '2px 8px',
        }}>
          In Development
        </span>
      </div>

      {/* ── poker table ── */}
      <PokerTable>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
          <div style={{ fontFamily: 'var(--display)', fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,0.85)', letterSpacing: 2, textTransform: 'uppercase', textShadow: '0 2px 8px rgba(0,0,0,0.6)' }}>
            PLO5 · 6-MAX
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
            <Chip label="Samples"  value="124"   sub="validated"  color="#22c55e" />
            <Chip label="Avg EV"   value="—"     sub="pending"    color="#60a5fa" />
            <Chip label="Model"    value="v0.1"  sub="training"   color="#f59e0b" />
          </div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', letterSpacing: 1, textTransform: 'uppercase' }}>
            nuts4poker.com
          </div>
        </div>
      </PokerTable>

      {/* ── feature roadmap ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: 12,
      }}>
        <FeatureCard
          icon="🧠"
          title="Equity Pattern Recognition"
          desc="Train a model on captured PLO5 6-max hand histories to predict real-time equity edges beyond raw simulation."
          badge="Next Up"
        />
        <FeatureCard
          icon="📊"
          title="EV Distribution Analysis"
          desc="Cluster hand samples by disparity patterns. Identify recurring BUY/REVERSE BUYER archetypes across sessions."
          badge="Planned"
        />
        <FeatureCard
          icon="🎯"
          title="Live Hand Scoring"
          desc="Score incoming tracker hands in real time — rank expected value before the engine completes a full run."
          badge="Planned"
        />
        <FeatureCard
          icon="🔁"
          title="Session Replay"
          desc="Step through validated hand history chronologically. Overlay equity curves with board runouts."
          badge="Planned"
        />
        <FeatureCard
          icon="⚖️"
          title="Range vs Range"
          desc="Build player range profiles from session data. Compare aggregate equity distributions hand-over-hand."
          badge="Planned"
        />
        <FeatureCard
          icon="💬"
          title="AI Analyst (Claude)"
          desc="Natural language equity analysis already live on the Parser tab. ML model integration coming here."
          badge="Partial"
        />
      </div>

      {/* data note */}
      <div style={{
        padding: '10px 14px',
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        fontSize: 11, lineHeight: 1.8, color: 'var(--text-dim)',
      }}>
        Training data is collected via the <b style={{ color: 'var(--text-muted)' }}>Tracker tab</b> (Tampermonkey script on pokerbet.co.za).
        Each validated hand is stored in <code style={{ background: '#0d1117', padding: '1px 5px', borderRadius: 3 }}>validated_hands/</code> on the server.
        124 hands captured so far. ML pipeline begins when a minimum dataset threshold is reached.
      </div>

    </div>
  )
}
