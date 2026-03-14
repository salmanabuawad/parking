
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
import { he } from './i18n/he'

export class AppErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error?: Error }> {
  state = { hasError: false as boolean, error: undefined as Error | undefined }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, fontFamily: 'system-ui' }}>
          <h2>אירעה שגיאה</h2>
          <p>בדוק את הקונסול בדפדפן וודא שהשרת פועל ב־http://localhost:8000.</p>
          <pre>{this.state.error?.message}</pre>
        </div>
      )
    }
    return this.props.children
  }
}

function Shell() {
  const { isLoggedIn, loading, logout, user } = useAuth()

  if (loading) return <div style={{ padding: 24 }}>{he.app.loading}</div>

  if (!isLoggedIn) {
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    )
  }

  return (
    <div dir="rtl">
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
          padding: '16px 24px',
          borderBottom: '1px solid #e5e7eb',
          background: '#fff',
        }}
      >
        <div style={{ fontWeight: 800 }}>{he.app.title}</div>
        <nav style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
          <Link to="/">{he.app.home}</Link>
          <Link to="/upload">{he.app.upload}</Link>
          <Link to="/tickets">{he.app.tickets}</Link>
          <Link to="/cameras">{he.app.cameras}</Link>
          <Link to="/queue">{he.app.queue}</Link>
          <Link to="/settings">{he.app.settings}</Link>
        </nav>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span>{user?.username}</span>
          <button onClick={logout}>{he.app.logout}</button>
        </div>
      </header>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/tickets" element={<Tickets />} />
        <Route path="/tickets/:id" element={<TicketReview />} />
        <Route path="/cameras" element={<Cameras />} />
        <Route path="/queue" element={<QueueMaintenance />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  )
}
