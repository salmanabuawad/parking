
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
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

const STATUS_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  queued:     { color: '#92400e', bg: '#fef3c7', label: 'ממתין בתור' },
  processing: { color: '#1e40af', bg: '#dbeafe', label: 'מעובד' },
  completed:  { color: '#065f46', bg: '#d1fae5', label: 'הושלם' },
  failed:     { color: '#991b1b', bg: '#fee2e2', label: 'נכשל' },
}

function StatusCell({ value }: { value: string }) {
  const s = STATUS_STYLE[value] ?? { color: '#374151', bg: '#f3f4f6', label: value }
  return (
    <span style={{
      display: 'inline-block',
      padding: '3px 10px',
      borderRadius: 999,
      background: s.bg,
      color: s.color,
      fontWeight: 600,
      fontSize: '0.82rem',
    }}>
      {s.label}
    </span>
  )
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{
      background: 'var(--app-surface)',
      border: '1px solid var(--app-border)',
      borderRadius: 12,
      padding: '1rem 1.25rem',
      minWidth: 110,
      flex: 1,
      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
    }}>
      <div style={{ fontSize: '1.75rem', fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: '0.85rem', color: 'var(--app-text-muted)', marginTop: 2 }}>{label}</div>
    </div>
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
            ? <span title={p.value} style={{ color: 'var(--app-danger)', fontSize: '0.82rem' }}>
                {p.value.length > 70 ? `${p.value.slice(0, 70)}…` : p.value}
              </span>
            : <span style={{ color: 'var(--app-text-muted)' }}>—</span>,
      },
      {
        headerName: he.home.openTicket,
        width: Math.round(120 * w),
        cellRenderer: (p: ICellRendererParams<UploadJob>) =>
          p.data?.ticket_id ? (
            <button
              onClick={() => navigate(`/tickets/${p.data!.ticket_id}`)}
              style={{
                padding: '4px 12px',
                borderRadius: 6,
                border: '1px solid var(--app-border)',
                background: 'var(--app-surface-muted)',
                color: 'var(--app-accent)',
                cursor: 'pointer',
                fontSize: '0.82rem',
                fontWeight: 600,
                fontFamily: 'inherit',
              }}
            >
              {he.home.openTicket}
            </button>
          ) : null,
      },
    ]
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fsVer, navigate])

  return (
    <div
      style={{
        padding: '1.5rem 2rem',
        width: '100%',
        boxSizing: 'border-box',
        color: 'var(--app-text)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        flex: 1,
      }}
    >
      <div style={{ marginBottom: '1.25rem' }}>
        <h1 style={{ margin: '0 0 4px', fontSize: '1.5rem', color: 'var(--app-text)' }}>{he.home.title}</h1>
        <p style={{ margin: 0, color: 'var(--app-text-muted)', fontSize: '0.95rem' }}>{he.home.subtitle}</p>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: '1.5rem' }}>
        <StatCard label="סה״כ" value={counts.total} color="#1e40af" />
        <StatCard label="ממתינים" value={counts.pending} color="#d97706" />
        <StatCard label="הושלמו" value={counts.completed} color="#065f46" />
        <StatCard label="נכשלו" value={counts.failed} color="#dc2626" />
      </div>

      {/* Queue grid */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem', flexWrap: 'wrap', gap: 8 }}>
          <h2 style={{ margin: 0, fontSize: '1rem', color: 'var(--app-text)' }}>{he.home.queueTitle}</h2>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="search"
              placeholder="חיפוש..."
              value={quickFilter}
              onChange={(e) => setQuickFilter(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 8, border: '1.5px solid var(--app-border)', background: 'var(--app-surface)', color: 'var(--app-text)', fontSize: '0.88rem', width: 180, direction: 'rtl' }}
            />
            <button
              onClick={() => { setRefreshing(true); fetchJobs() }}
              style={{
                padding: '6px 14px',
                borderRadius: 8,
                border: 'none',
                background: 'var(--app-accent)',
                color: '#fff',
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontFamily: 'inherit',
              }}
            >
              {refreshing ? he.home.refreshing : he.home.refresh}
            </button>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: '2rem', color: 'var(--app-text-muted)', textAlign: 'center' }}>{he.home.loading}</div>
        ) : (
          <div style={{ flex: 1, minHeight: 0, borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.08)', marginTop: '0.25rem' }}>
            <AgGridReact<UploadJob>
              theme={agTheme}
              rowData={jobs}
              columnDefs={colDefs}
              quickFilterText={quickFilter}
              enableRtl={true}
              pagination={true}
              paginationPageSize={15}
              rowHeight={46}
              defaultColDef={{ sortable: true, filter: true, resizable: true }}
              overlayNoRowsTemplate={`<span style="color:#94a3b8">${he.home.empty}</span>`}
              style={{ width: '100%', height: '100%' }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
