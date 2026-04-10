import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
import { useAgGridTheme } from '../lib/agGridTheme'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import api from '../api'
import { uploadApi, settingsApi } from '../api'
import { t } from '../i18n'
import { getFontSizeWidthMultiplier, subscribeFontSize } from '../lib/fontSizeStore'

ModuleRegistry.registerModules([AllCommunityModule])

interface UploadJob {
  job_id: number
  status: string
  source?: string
  target?: string
  license_plate?: string | null
  error_message?: string | null
  ticket_id?: number | null
  created_at?: string | null
}

interface Settings {
  blur_kernel_size: number
  use_violation_pipeline?: boolean
}

const STATUS_COLOR: Record<string, { color: string; bg: string }> = {
  queued:     { color: '#92400e', bg: '#fef3c7' },
  processing: { color: '#1e40af', bg: '#dbeafe' },
  completed:  { color: '#065f46', bg: '#d1fae5' },
  failed:     { color: '#991b1b', bg: '#fee2e2' },
}

function StatusCell({ value }: { value: string }) {
  const s = STATUS_COLOR[value] ?? { color: '#374151', bg: '#f3f4f6' }
  const labels: Record<string, string> = {
    queued: t('statusQueued'),
    processing: t('statusProcessing'),
    completed: t('statusCompleted'),
    failed: t('statusFailed'),
  }
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
      {labels[value] ?? value}
    </span>
  )
}

function ErrorCell({ value }: { value: string | null }) {
  if (!value) return <span style={{ color: 'var(--app-text-muted)' }}>—</span>
  const short = value.length > 70 ? `${value.slice(0, 70)}…` : value
  return (
    <span title={value} style={{ color: 'var(--app-danger)', fontSize: '0.82rem' }}>
      {short}
    </span>
  )
}

export default function QueueMaintenance() {
  const agTheme = useAgGridTheme()
  const [fsVer, setFsVer] = useState(0)
  useEffect(() => subscribeFontSize(() => setFsVer(v => v + 1)), [])

  const [jobs, setJobs] = useState<UploadJob[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [resettingStuck, setResettingStuck] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [quickFilter, setQuickFilter] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchJobs = useCallback(async () => {
    try {
      const { data } = await uploadApi.listJobs(50)
      setJobs(data)
    } catch (err) {
      console.error('Failed to fetch jobs', err)
    }
  }, [])

  const load = async () => {
    setLoading(true)
    await Promise.all([
      fetchJobs(),
      settingsApi.get().then(({ data }) => setSettings(data)).catch(() => {}),
    ])
    setLoading(false)
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const id = setInterval(fetchJobs, 5000)
    return () => clearInterval(id)
  }, [fetchJobs])

  const handleResetStuck = async () => {
    setResettingStuck(true)
    try {
      const { data } = await uploadApi.resetStuckJobs()
      await fetchJobs()
      alert(data.message || `Reset ${data.reset_count} stuck job(s)`)
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      alert(ax.response?.data?.detail || ax.message)
    } finally {
      setResettingStuck(false)
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('video', file)
      fd.append('latitude', '0')
      fd.append('longitude', '0')
      fd.append('captured_at', new Date().toISOString())
      fd.append('license_plate', '')
      fd.append('violation_zone', 'red_white')
      await api.post('/upload/violation', fd)
      await fetchJobs()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      alert(ax.response?.data?.detail || ax.message)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const colDefs = useMemo<ColDef<UploadJob>[]>(() => {
    const w = getFontSizeWidthMultiplier()
    return [
      { field: 'job_id', headerName: t('jobNum'), width: Math.round(90 * w), sort: 'desc' },
      {
        field: 'created_at',
        headerName: t('uploadDate'),
        width: Math.round(160 * w),
        valueFormatter: (p) => p.value ? new Date(p.value).toLocaleString('he-IL', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—',
      },
      {
        field: 'source',
        headerName: t('source'),
        flex: 1.5,
        cellRenderer: (p: ICellRendererParams<UploadJob>) =>
          p.value ? <code style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>{p.value}</code> : <span style={{ color: 'var(--app-text-muted)' }}>—</span>,
      },
      {
        field: 'status',
        headerName: t('status'),
        width: Math.round(130 * w),
        cellRenderer: (p: ICellRendererParams<UploadJob>) => <StatusCell value={p.value} />,
      },
      {
        field: 'license_plate',
        headerName: t('plate'),
        width: Math.round(130 * w),
        valueFormatter: (p) => (p.value && p.value !== '11111' ? p.value : t('plateNotIdentified')),
      },
      {
        field: 'ticket_id',
        headerName: t('ticket'),
        width: Math.round(110 * w),
        cellRenderer: (p: ICellRendererParams<UploadJob>) =>
          p.value ? (
            <Link
              to={`/tickets/${p.value}`}
              style={{ color: 'var(--app-accent)', fontWeight: 600, textDecoration: 'none', fontSize: '0.88rem' }}
            >
              #{p.value}
            </Link>
          ) : (
            <span style={{ color: 'var(--app-text-muted)' }}>—</span>
          ),
      },
      {
        field: 'error_message',
        headerName: t('failingReason'),
        flex: 2,
        cellRenderer: (p: ICellRendererParams<UploadJob>) => <ErrorCell value={p.value} />,
      },
    ]
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fsVer])

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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', color: 'var(--app-text)' }}>{t('queueMaintenance')}</h1>
          <p style={{ margin: '4px 0 0', color: 'var(--app-text-muted)', fontSize: '0.92rem' }}>
            {t('queueSubtitle')}{' '}
            <Link to="/settings" style={{ color: 'var(--app-accent)' }}>{t('editBlurSettings')}</Link>
          </p>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            onChange={handleFileChange}
            disabled={uploading}
            style={{ display: 'none' }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            style={{ padding: '8px 16px', background: 'var(--app-accent)', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            {uploading ? t('uploading') : t('uploadVideo')}
          </button>
          <button
            onClick={handleResetStuck}
            disabled={resettingStuck}
            style={{ padding: '8px 16px', background: 'var(--app-danger)', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            {resettingStuck ? '...' : 'איפוס תקועים'}
          </button>
        </div>
      </div>

      {settings && (
        <div style={{ marginBottom: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', background: 'var(--app-surface-muted)', border: '1px solid var(--app-border)', borderRadius: 8 }}>
          <strong style={{ fontSize: '0.88rem' }}>{t('blurKernelSize')}:</strong>
          <span style={{ background: 'rgba(37,99,235,0.14)', color: 'var(--app-accent)', padding: '2px 8px', borderRadius: 4, fontSize: '0.88rem', fontWeight: 600 }}>
            {settings.blur_kernel_size}
          </span>
        </div>
      )}

      <div style={{ marginBottom: '0.75rem' }}>
        <input
          type="search"
          placeholder="חיפוש..."
          value={quickFilter}
          onChange={(e) => setQuickFilter(e.target.value)}
          style={{ padding: '7px 12px', borderRadius: 8, border: '1.5px solid var(--app-border)', background: 'var(--app-surface)', color: 'var(--app-text)', fontSize: '0.9rem', width: 220, direction: 'rtl' }}
        />
      </div>

      {loading ? (
        <p style={{ color: 'var(--app-text-muted)' }}>{t('loading')}</p>
      ) : (
        <div style={{ flex: 1, minHeight: 0, borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.08)', marginTop: '0.25rem' }}>
          <AgGridReact<UploadJob>
            theme={agTheme}
            rowData={jobs}
            columnDefs={colDefs}
            quickFilterText={quickFilter}
            enableRtl={true}
            pagination={true}
            paginationPageSize={20}
            rowHeight={48}
            defaultColDef={{ sortable: true, filter: true, resizable: true }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      )}
    </div>
  )
}
