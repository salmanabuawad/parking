import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
import ExcelLikeFilter from '../components/grid/ExcelLikeFilter'
import { LayoutDashboard, RefreshCw } from 'lucide-react'
import { useAgGridTheme } from '../lib/agGridTheme'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import { uploadApi } from '../api'
import { getFontSizeWidthMultiplier, subscribeFontSize } from '../lib/fontSizeStore'
import { he } from '../i18n/he'
import { useRtl } from '../hooks/useRtl'

ModuleRegistry.registerModules([AllCommunityModule])

interface UploadJob {
  job_id: number
  status: string
  ticket_id?: number
  license_plate?: string
  created_at?: string
  error_message?: string
}

const STATUS_BADGE: Record<string, { cls: string; label: string }> = {
  queued:     { cls: 'badge-warning', label: 'ממתין בתור' },
  processing: { cls: 'badge-info',    label: 'מעובד' },
  completed:  { cls: 'badge-success', label: 'הושלם' },
  failed:     { cls: 'badge-danger',  label: 'נכשל' },
}

function StatusCell({ value }: { value: string }) {
  const s = STATUS_BADGE[value] ?? { cls: 'badge-neutral', label: value }
  return <span className={`badge ${s.cls}`}>{s.label}</span>
}

function StatCard({ label, value, accent, active, onClick }: { label: string; value: number; accent: string; active?: boolean; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`app-card flex-1 min-w-[110px] px-5 py-4 text-right cursor-pointer transition-shadow ${active ? 'ring-2 ring-theme-accent' : 'hover:shadow-md'}`}
    >
      <div className={`text-3xl font-bold ${accent}`}>{value}</div>
      <div className="text-sm text-theme-text-muted mt-0.5">{label}</div>
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

  const fetchJobs = useCallback(async () => {
    try {
      const { data } = await uploadApi.listJobs()
      setJobs(data)
    } catch (err) {
      console.error('Failed to fetch jobs', err)
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
    pending: jobs.filter((j) => j.status === 'queued').length,
    completed: jobs.filter((j) => j.status === 'completed').length,
    failed: jobs.filter((j) => j.status === 'failed').length,
  }
  const visibleJobs = statusFilter ? jobs.filter((j) => j.status === statusFilter) : jobs

  const colDefs = useMemo<ColDef<UploadJob>[]>(() => {
    const w = getFontSizeWidthMultiplier()
    return [
      { field: 'job_id', headerName: he.home.job, width: Math.round(90 * w), sort: 'desc' },
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
        valueFormatter: (p) => (p.value && p.value !== '11111' ? p.value : he.home.plateNotIdentified),
      },
      {
        field: 'created_at',
        headerName: he.home.created,
        flex: 1,
        valueFormatter: (p) => p.value ? new Date(p.value).toLocaleString('he-IL') : '—',
      },
      {
        field: 'error_message',
        headerName: he.home.error,
        flex: 1.5,
        cellRenderer: (p: ICellRendererParams<UploadJob>) =>
          p.value
            ? <span title={p.value} className="text-red-600 text-theme-xs">
                {p.value.length > 70 ? `${p.value.slice(0, 70)}…` : p.value}
              </span>
            : <span className="text-theme-text-muted">—</span>,
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

      {/* Stat cards */}
      <div className="flex flex-wrap gap-3">
        <StatCard label="סה״כ"   value={counts.total}     accent="text-blue-700"  active={statusFilter === null}        onClick={() => setStatusFilter(null)} />
        <StatCard label="ממתינים" value={counts.pending}   accent="text-amber-600" active={statusFilter === 'queued'}    onClick={() => setStatusFilter((s) => (s === 'queued' ? null : 'queued'))} />
        <StatCard label="הושלמו"  value={counts.completed} accent="text-green-700" active={statusFilter === 'completed'} onClick={() => setStatusFilter((s) => (s === 'completed' ? null : 'completed'))} />
        <StatCard label="נכשלו"   value={counts.failed}    accent="text-red-600"   active={statusFilter === 'failed'}    onClick={() => setStatusFilter((s) => (s === 'failed' ? null : 'failed'))} />
      </div>

      {/* Queue grid */}
      <div className="flex flex-col flex-1 min-h-0 gap-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-base font-semibold text-theme-text-primary">{he.home.queueTitle}</h2>
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
              theme={agTheme}
              rowData={visibleJobs}
              columnDefs={colDefs}
              quickFilterText={quickFilter}
              enableRtl={true}
              rowHeight={46}
              defaultColDef={{ sortable: true, filter: ExcelLikeFilter, resizable: true }}
              overlayNoRowsTemplate={`<span style="color:#94a3b8">${he.home.empty}</span>`}
              style={{ width: '100%', height: '100%' }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
