import { Component, type ReactNode, useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom'

const routerFutureFlags = { v7_startTransition: true, v7_relativeSplatPath: true }
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

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= 768)
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])
  return isMobile
}

export class AppErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error?: Error }> {
  state = { hasError: false as boolean, error: undefined as Error | undefined }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24 }} dir="rtl">
          <h2>{he.app.unknownError}</h2>
          <p>בדקו את קונסולת הדפדפן (F12) וודאו שהשרת פעיל.</p>
          <pre>{this.state.error?.message}</pre>
        </div>
      )
    }
    return this.props.children
  }
}

function MobileShell() {
  return (
    <div dir="rtl" style={{ minHeight: '100vh', background: '#f9fafb' }}>
      <header style={{ padding: '12px 16px', background: '#1e3a8a', color: '#fff', textAlign: 'center' }}>
        <strong style={{ fontSize: '1.1rem' }}>דיווח חנייה אסורה</strong>
      </header>
      <Upload />
    </div>
  )
}

function AppShell() {
  const { isLoggedIn, loading, logout, user } = useAuth()
  const isMobile = useIsMobile()

  if (loading) return <div dir="rtl" style={{ padding: 24 }}>{he.app.loading}</div>

  // Mobile: only show the upload page, no login required
  if (isMobile) {
    return <MobileShell />
  }

  if (!isLoggedIn) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return (
    <div dir="rtl">
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid #e5e7eb', background: '#fff' }}>
        <nav style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <strong>{he.app.title}</strong>
          <Link to="/">{he.app.home}</Link>
          <Link to="/upload">{he.app.upload}</Link>
          <Link to="/tickets">{he.app.tickets}</Link>
          <Link to="/cameras">{he.app.cameras}</Link>
          <Link to="/queue">{he.app.queue}</Link>
          <Link to="/settings">{he.app.settings}</Link>
        </nav>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
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
    <BrowserRouter future={routerFutureFlags}>
      <AppErrorBoundary>
        <AppShell />
      </AppErrorBoundary>
    </BrowserRouter>
  )
}
