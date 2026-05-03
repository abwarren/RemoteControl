// LoginScreen.jsx — Full-page login gate
import { useState } from 'react'

export default function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')
  const [showPw,   setShowPw]   = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password) return
    setLoading(true)
    setError('')
    try {
      const res  = await fetch('/api/login', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ username: username.trim(), password }),
      })
      const data = await res.json()
      if (data.ok) {
        localStorage.setItem('auth_token',    data.token)
        localStorage.setItem('auth_username', data.username)
        onLogin(data.token, data.username)
      } else {
        setError(data.error || 'Invalid username or password')
      }
    } catch {
      setError('Could not reach server — check your connection')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 20,
    }}>
      {/* Logo */}
      <div style={{ marginBottom: 32, textAlign: 'center' }}>
        <div style={{
          fontFamily: 'var(--display)',
          fontWeight: 700,
          fontSize: 22,
          color: 'var(--accent)',
          letterSpacing: 2,
          textTransform: 'uppercase',
        }}>
          PLO Equity Engine
        </div>
        <div style={{
          fontFamily: 'var(--mono)',
          fontSize: 11,
          color: 'var(--text-muted)',
          letterSpacing: 3,
          marginTop: 4,
          textTransform: 'uppercase',
        }}>
          nuts4poker.com
        </div>
      </div>

      {/* Card */}
      <form onSubmit={submit} style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: '32px 28px',
        width: '100%',
        maxWidth: 360,
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}>
        <div style={{
          fontFamily: 'var(--display)',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: 2,
          textTransform: 'uppercase',
          color: 'var(--text-muted)',
          marginBottom: 4,
          textAlign: 'center',
        }}>
          Sign In
        </div>

        {/* Username */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          <label style={{ fontSize: 10, letterSpacing: 2, color: 'var(--text-muted)' }}>
            USERNAME
          </label>
          <input
            type="text"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={e => setUsername(e.target.value)}
            placeholder="Enter username"
            style={{ margin: 0 }}
            disabled={loading}
          />
        </div>

        {/* Password */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          <label style={{ fontSize: 10, letterSpacing: 2, color: 'var(--text-muted)' }}>
            PASSWORD
          </label>
          <div style={{ position: 'relative' }}>
            <input
              type={showPw ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Enter password"
              style={{ margin: 0, paddingRight: 38 }}
              disabled={loading}
            />
            <button
              type="button"
              onClick={() => setShowPw(v => !v)}
              style={{
                position: 'absolute',
                right: 8,
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--text-muted)',
                fontSize: 13,
                padding: '2px 4px',
                lineHeight: 1,
              }}
              tabIndex={-1}
            >
              {showPw ? '🙈' : '👁'}
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div style={{
            background: 'var(--red-dim)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 5,
            padding: '8px 12px',
            color: 'var(--red)',
            fontSize: 11,
            fontFamily: 'var(--mono)',
          }}>
            ✗ {error}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          className="btn btn-primary"
          style={{ width: '100%', marginTop: 4, padding: '11px 20px' }}
          disabled={loading || !username.trim() || !password}
        >
          {loading ? '⟳  Signing in...' : '→  Sign In'}
        </button>
      </form>

      <div style={{
        marginTop: 20,
        fontSize: 10,
        color: 'var(--text-dim)',
        fontFamily: 'var(--mono)',
        letterSpacing: 1,
      }}>
        Authorised users only
      </div>
    </div>
  )
}
