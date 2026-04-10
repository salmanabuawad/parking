import { Component, type ReactNode, useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, FileText, ListOrdered, Camera, Settings, ShieldAlert,
} from 'lucide-react'

const routerFutureFlags = { v7_startTransition: true, v7_relativeSplatPath: true }

import { useAuth } from './context/AuthContext'
import { Header }  from './components/Header'
import { Sidebar, type NavItem } from './components/Sidebar'

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

import Cameras          from './pages/Cameras'
import SettingsPage     from './pages/Settings'
import Home             from './pages/Home'
import Upload           from './pages/Upload'
import Tickets          from './pages/Tickets'
import TicketReview     from './pages/TicketReview'
import QueueMaintenance from './pages/QueueMaintenance'
import ViolationRules   from './pages/ViolationRules'
import Login            from './pages/Login'
import { he }           from './i18n/he'

/* ── Error boundary ── */
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

/* ── Navigation items ── */
const NAV_ITEMS: NavItem[] = [
  {
    id: 'home',
    label: he.app.home,
    icon: <LayoutDashboard className="w-4 h-4" />,
  },
  {
    id: 'tickets-group',
    label: 'דוחות חניה',
    icon: <FileText className="w-4 h-4" />,
    children: [
      { id: 'tickets', label: he.app.tickets,    icon: <FileText className="w-3.5 h-3.5" /> },
      { id: 'queue',   label: he.app.queue,      icon: <ListOrdered className="w-3.5 h-3.5" /> },
    ],
  },
  {
    id: 'cameras-group',
    label: 'מצלמות',
    icon: <Camera className="w-4 h-4" />,
    children: [
      { id: 'cameras',         label: he.app.cameras,  icon: <Camera className="w-3.5 h-3.5" /> },
      { id: 'violation-rules', label: 'כללי עבירה',    icon: <ShieldAlert className="w-3.5 h-3.5" /> },
    ],
  },
  {
    id: 'settings',
    label: he.app.settings,
    icon: <Settings className="w-4 h-4" />,
  },
]

/* Map nav id → route path */
const ID_TO_PATH: Record<string, string> = {
  home:             '/',
  tickets:          '/tickets',
  queue:            '/queue',
  cameras:          '/cameras',
  'violation-rules':'/violation-rules',
  settings:         '/settings',
}

/* Map pathname → active nav id */
function pathnameToActiveId(pathname: string): string {
  if (pathname === '/')                         return 'home'
  if (pathname.startsWith('/tickets'))          return 'tickets'
  if (pathname.startsWith('/queue'))            return 'queue'
  if (pathname.startsWith('/cameras'))          return 'cameras'
  if (pathname.startsWith('/violation-rules'))  return 'violation-rules'
  if (pathname.startsWith('/settings'))         return 'settings'
  return 'home'
}

/* ── App shell (requires BrowserRouter context) ── */
function AppShell() {
  const { isLoggedIn, loading } = useAuth()
  const navigate  = useNavigate()
  const location  = useLocation()
  const activeId  = pathnameToActiveId(location.pathname)
  const isMobile  = useIsMobile()

  if (loading) return <div dir="rtl" style={{ padding: 24 }}>{he.app.loading}</div>

  if (!isLoggedIn) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*"      element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  /* ── Mobile: upload/report only ── */
  if (isMobile) {
    return (
      <div className="app-shell" dir="rtl">
        <Header
          title={he.app.title}
          logo={
            <div className="w-7 h-7 rounded-lg bg-white/20 flex items-center justify-center">
              <Camera className="w-4 h-4 text-white" />
            </div>
          }
        />
        <main className="app-content bg-theme-content" style={{ overflowY: 'auto' }}>
          <Routes>
            <Route path="/upload" element={<Upload />} />
            <Route path="*"       element={<Navigate to="/upload" replace />} />
          </Routes>
        </main>
      </div>
    )
  }

  /* ── Desktop: full layout ── */
  return (
    <div className="app-shell" dir="rtl">

      {/* ── Header ── */}
      <Header
        title={he.app.title}
        logo={
          <div className="w-7 h-7 rounded-lg bg-white/20 flex items-center justify-center">
            <Camera className="w-4 h-4 text-white" />
          </div>
        }
      />

      {/* ── Body ── */}
      <div className="app-body">

        <Sidebar
          items={NAV_ITEMS}
          activeId={activeId}
          onSelect={id => {
            const path = ID_TO_PATH[id]
            if (path) navigate(path)
          }}
        />

        <main className="app-content bg-theme-content">
          <Routes>
            <Route path="/"                element={<Home />} />
            <Route path="/upload"          element={<Upload />} />
            <Route path="/tickets"         element={<Tickets />} />
            <Route path="/tickets/:id"     element={<TicketReview />} />
            <Route path="/cameras"         element={<Cameras />} />
            <Route path="/violation-rules" element={<ViolationRules />} />
            <Route path="/queue"           element={<QueueMaintenance />} />
            <Route path="/settings"        element={<SettingsPage />} />
            <Route path="*"               element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
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
