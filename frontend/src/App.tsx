import { Component, type ReactNode, useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Link, Navigate, useLocation } from 'react-router-dom'

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
      <header style={{
        padding: '14px 16px',
        background: 'linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%)',
        color: '#fff',
        textAlign: 'center',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
      }}>
        <strong style={{ fontSize: '1.1rem', letterSpacing: '0.02em' }}>דיווח חנייה אסורה</strong>
      </header>
      <Upload />
    </div>
  )
}

const NAV_LINKS = [
  { to: '/', label: he.app.home },
  { to: '/upload', label: he.app.upload },
  { to: '/tickets', label: he.app.tickets },
  { to: '/cameras', label: he.app.cameras },
  { to: '/queue', label: he.app.queue },
  { to: '/settings', label: he.app.settings },
]

function NavLink({ to, label }: { to: string; label: string }) {
  const loc = useLocation()
  const active = to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(to)
  return (
    <Link
      to={to}
      style={{
        padding: '6px 14px',
        borderRadius: 8,
        textDecoration: 'none',
        fontWeight: active ? 700 : 400,
        color: active ? '#fff' : '#cbd5e1',
        background: active ? 'rgba(255,255,255,0.18)' : 'transparent',
        fontSize: '0.92rem',
        transition: 'all 0.15s',
      }}
    >
      {label}
    </Link>
  )
}

function AppShell() {
  const { isLoggedIn, loading, logout, user } = useAuth()
  const isMobile = useIsMobile()

  if (loading) return <div dir="rtl" style={{ padding: 24 }}>{he.app.loading}</div>

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
    <div dir="rtl" style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0 20px',
        height: 56,
        background: 'linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%)',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <nav style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ color: '#fff', fontWeight: 800, fontSize: '1rem', marginLeft: 12, letterSpacing: '0.03em' }}>
            {he.app.title}
          </span>
          {NAV_LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} label={l.label} />
          ))}
        </nav>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ color: '#bfdbfe', fontSize: '0.88rem' }}>{user?.username}</span>
          <button
            onClick={logout}
            style={{
              padding: '5px 14px',
              background: 'rgba(255,255,255,0.15)',
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.3)',
              borderRadius: 8,
              cursor: 'pointer',
              fontSize: '0.88rem',
              fontFamily: 'inherit',
            }}
          >
            {he.app.logout}
          </button>
        </div>
      </header>

      <main style={{ padding: '0' }}>
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
      </main>
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
