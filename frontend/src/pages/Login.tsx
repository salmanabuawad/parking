import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(username, password)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const styles: Record<string, React.CSSProperties> = {
    page: { padding: '1.5rem', maxWidth: 400, margin: '0 auto', fontFamily: 'system-ui' },
    title: { fontSize: '1.5rem', marginBottom: '1rem' },
    input: { width: '100%', padding: '0.75rem', fontSize: '1rem', marginTop: 4 },
    btn: { width: '100%', padding: '1rem', marginTop: '1.5rem', fontSize: '1.1rem', background: '#1a1a2e', color: 'white', border: 'none', borderRadius: 8 },
  }

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>Parking Enforcement</h1>
      <p style={{ color: '#666', marginBottom: '1.5rem' }}>Sign in to upload violation videos</p>

      <form onSubmit={submit}>
        <label style={{ display: 'block', fontWeight: 600 }}>Username</label>
        <input
          type="text"
          value={username}
          onChange={e => setUsername(e.target.value)}
          required
          autoComplete="username"
          style={styles.input}
        />
        <label style={{ display: 'block', fontWeight: 600, marginTop: '1rem' }}>Password</label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
          autoComplete="current-password"
          style={styles.input}
        />
        {error && <p style={{ color: 'red', marginTop: 8 }}>{error}</p>}
        <button type="submit" style={styles.btn} disabled={loading}>
          {loading ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
