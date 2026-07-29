import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
import { DEFAULT_COL_DEF, emptyOverlay } from '../lib/gridConfig'
import { ticketStatusBadge } from '../lib/ticketStatus'
import { formatPlate } from '../lib/format'
import { LayoutDashboard, RefreshCw, Layers, Clock, CheckCircle2, AlertTriangle } from 'lucide-react'
import type { ReactNode } from 'react'
import { useAgGridTheme } from '../lib/agGridTheme'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import { ticketsApi } from '../api'
import { getFontSizeWidthMultiplier, subscribeFontSize } from '../lib/fontSizeStore'
import { he } from '../i18n/he'
import { useRtl } from '../hooks/useRtl'
import { useFieldConfig } from '../lib/useFieldConfig'
import { useFieldConfigVersion } from '../context/FieldConfigContext'

ModuleRegistry.registerModules([AllCommunityModule])

interface UploadJob {
  job_id: number
  status: string
  ticket_id?: number
  license_plate?: string
  created_at?: string
  error_message?: string
}

function StatusCell({ value }: { value: string }) {
  const s = ticketStatusBadge(value)
  return <span className={`badge ${s.cls}`}>{s.label}</span>
}

function StatCard({ label, value, accent, tint, icon, active, onClick }: { label: string; value: number; accent: string; tint: string; icon: ReactNode; active?: boolean; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`app-card flex-1 min-w-[140px] px-4 py-3.5 flex items-center gap-3 text-right cursor-pointer transition-all ${active ? 'ring-2 ring-theme-accent shadow-md' : 'hover:shadow-md hover:-translate-y-0.5'}`}
    >
      <span className={`flex items-center justify-center w-11 h-11 rounded-xl shrink-0 ${tint}`}>{icon}</span>
      <div className="min-w-0">
        <div className={`text-3xl font-bold leading-none ${accent}`}>{value}</div>
        <div className="text-sm text-theme-text-muted mt-1 truncate">{label}</div>
      </div>
    </button>
  )
}

export default function Home() {
  useRtl(`${he.home.title} | ${he.app.title}`)
  const agTheme = useAgGridTheme()

  const navigate = useNavigate()
  const [fsVer, setFsVer] = useState(0)
  useEffect(() => subscribeFontSize(() => setFsVer(v => v + 1)), [])

  const [jobs, setJobs] = useState<UploadJob[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [quickFilter, setQuickFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [error, setError] = useState(false)

  const fetchJobs = useCallback(async () => {
    try {
      const { data } = await ticketsApi.list()
      // The dashboard lists TICKETS (one processed video can yield several) — map each ticket to a row,
      // using its capture time (not the upload time), so all tickets show with the correct clock.
      setJobs((data || []).map((t: any) => ({
        job_id: t.id,
        status: t.status,
        ticket_id: t.id,
        license_plate: t.license_plate,
        created_at: t.captured_at,
      })))
      setError(false)
    } catch (err) {
      console.error('Failed to fetch tickets', err); setError(true)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { fetchJobs() }, [fetchJobs])
  useEffect(() => {
    const id = setInterval(fetchJobs, 5000)
    return () => clearInterval(id)
  }, [fetchJobs])

  const counts = {
    total: jobs.length,
    pending: jobs.filter((j) => j.status === 'pending_review').length,
    completed: jobs.filter((j) => j.status === 'approved').length,
    failed: jobs.filter((j) => j.status === 'rejected').length,
  }
  const visibleJobs = statusFilter ? jobs.filter((j) => j.status === statusFilter) : jobs

  const colDefs = useMemo<ColDef<UploadJob>[]>(() => {
    const w = getFontSizeWidthMultiplier()
    return [
      { field: 'job_id', headerName: 'מס׳ דוח', width: Math.round(90 * w), sort: 'desc' },
      {
        field: 'status',
        headerName: he.home.status,
        width: Math.round(140 * w),
        cellRenderer: (p: ICellRendererParams<UploadJob>) => <StatusCell value={p.value} />,
      },
      {
        field: 'license_plate',
        headerName: he.home.plate,
        width: Math.round(140 * w),
        valueFormatter: (p) => (p.value && p.value !== '11111' ? formatPlate(p.value) : he.home.plateNotIdentified),
      },
      {
        field: 'created_at',
        headerName: 'תאריך',
        flex: 1,
        valueFormatter: (p) => p.value ? new Date(p.value).toLocaleString('he-IL') : '—',
      },
      {
        headerName: he.home.openTicket,
        width: Math.round(120 * w),
        cellRenderer: (p: ICellRendererParams<UploadJob>) =>
          p.data?.ticket_id ? (
            <button
              onClick={() => navigate(`/tickets/${p.data!.ticket_id}`)}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold text-theme-link hover:bg-black/5 transition-colors"
            >
              {he.home.openTicket}
            </button>
          ) : null,
      },
    ]
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fsVer, navigate])

  const cfgVer = useFieldConfigVersion()
  const [gridColDefs] = useFieldConfig(colDefs, 'home')

  return (
    <div className="page-container">
      {/* Page header */}
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon">
          <LayoutDashboard className="w-5 h-5" strokeWidth={1.5} />
        </span>
        <div className="flex-1 min-w-0">
          <h1 className="page-header-title">{he.home.title}</h1>
          <p className="page-header-label opacity-90">{he.home.subtitle}</p>
        </div>
      </div>

      {error && <div className="text-red-600 text-theme-sm">שגיאה בטעינת נתוני הדשבורד — נסה לרענן.</div>}

      {/* Stat cards */}
      <div className="flex flex-wrap gap-3">
        <StatCard label="סה״כ דוחות" value={counts.total}   accent="text-blue-700"  tint="bg-blue-50 text-blue-600"   icon={<Layers className="w-5 h-5" />}         active={statusFilter === null}              onClick={() => setStatusFilter(null)} />
        <StatCard label="ממתינים לאישור" value={counts.pending} accent="text-amber-600" tint="bg-amber-50 text-amber-600" icon={<Clock className="w-5 h-5" />}          active={statusFilter === 'pending_review'}  onClick={() => setStatusFilter((s) => (s === 'pending_review' ? null : 'pending_review'))} />
        <StatCard label="אושרו"   value={counts.completed} accent="text-green-700" tint="bg-green-50 text-green-600"  icon={<CheckCircle2 className="w-5 h-5" />}    active={statusFilter === 'approved'}        onClick={() => setStatusFilter((s) => (s === 'approved' ? null : 'approved'))} />
        <StatCard label="נדחו"    value={counts.failed}    accent="text-red-600"   tint="bg-red-50 text-red-600"     icon={<AlertTriangle className="w-5 h-5" />}  active={statusFilter === 'rejected'}        onClick={() => setStatusFilter((s) => (s === 'rejected' ? null : 'rejected'))} />
      </div>

      {/* Queue grid */}
      <div className="flex flex-col flex-1 min-h-0 gap-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-base font-semibold text-theme-text-primary">דוחות חניה</h2>
          <div className="flex items-center gap-2">
            <div className="w-44">
              <input
                type="search"
                placeholder="חיפוש..."
                value={quickFilter}
                onChange={(e) => setQuickFilter(e.target.value)}
                className="input-base"
              />
            </div>
            <button onClick={() => { setRefreshing(true); fetchJobs() }} className="btn-primary">
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              <span>{refreshing ? he.home.refreshing : he.home.refresh}</span>
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12 text-theme-text-muted">{he.home.loading}</div>
        ) : (
          <div className="grid-card">
            <AgGridReact<UploadJob>
              key={`home-${cfgVer}`}
              theme={agTheme}
              rowData={visibleJobs}
              columnDefs={gridColDefs}
              quickFilterText={quickFilter}
              enableRtl={true}
              rowHeight={46}
              defaultColDef={DEFAULT_COL_DEF}
              overlayNoRowsTemplate={emptyOverlay(he.home.empty)}
            />
          </div>
        )}
      </div>
    </div>
  )
}
