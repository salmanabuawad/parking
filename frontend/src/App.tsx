import { Component, type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Cameras from './pages/Cameras'
import Settings from './pages/Settings'
import Home from './pages/Home'
import Upload from './pages/Upload'
import Tickets from './pages/Tickets'
import TicketReview from './pages/TicketReview'
import QueueMaintenance from './pages/QueueMaintenance'
import Login from './pages/Login'

export class AppErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error?: Error }> {
  state = { hasError: false as boolean, error: undefined as Error | undefined }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }
  render() {
    if (this.state.hasError)
      return (
        <div style={{ padding: '2rem', fontFamily: 'system-ui', maxWidth: 600 }}>
          <h2 style={{ color: '#b91c1c' }}>Something went wrong</h2>
          <p>Check the browser console (F12) for details. Ensure the backend is running at <code>http://localhost:8000</code>.</p>
          <pre style={{ background: '#f3f4f6', padding: 12, overflow: 'auto' }}>{this.state.error?.message}</pre>
        </div>
      )
    return this.props.children
  }
}

function App() {
  const { isLoggedIn, loading, logout, user } = useAuth()

  if (loading)
    return (
      <div style={{ padding: '2rem', textAlign: 'center', fontFamily: 'system-ui' }}>
        Loading...
      </div>
    )

  if (!isLoggedIn) {
    return (
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<Login />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    )
  }

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <nav
        style={{
          padding: '0.75rem 2rem',
          background: '#1a1a2e',
          color: 'white',
          fontFamily: 'system-ui',
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <span style={{ fontWeight: 'bold', color: '#4ade80', marginRight: '1rem' }}>PARKING</span>
        <Link to="/" style={{ color: 'white' }}>
          Home
        </Link>
        <Link to="/upload" style={{ color: 'white' }}>
          Upload
        </Link>
        <Link to="/tickets" style={{ color: 'white' }}>
          Tickets
        </Link>
        <Link to="/cameras" style={{ color: 'white' }}>
          Cameras
        </Link>
        <Link to="/queue" style={{ color: 'white' }}>
          Queue
        </Link>
        <Link to="/settings" style={{ color: 'white' }}>
          Settings
        </Link>
        <span style={{ marginLeft: 'auto', fontSize: '0.9rem' }}>{user?.username}</span>
        <button
          onClick={logout}
          style={{
            background: 'transparent',
            color: '#aaa',
            border: '1px solid #555',
            padding: '0.25rem 0.5rem',
            borderRadius: 4,
            cursor: 'pointer',
          }}
        >
          Logout
        </button>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/tickets" element={<Tickets />} />
        <Route path="/tickets/:id" element={<TicketReview />} />
        <Route path="/cameras" element={<Cameras />} />
        <Route path="/queue" element={<QueueMaintenance />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
