import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry, themeQuartz } from 'ag-grid-community'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import api from '../api'
import { uploadApi, settingsApi } from '../api'
import { t } from '../i18n'

ModuleRegistry.registerModules([AllCommunityModule])

interface UploadJob {
  job_id: number
  status: string
  source?: string
  target?: string
  license_plate?: string | null
  error_message?: string | null
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
  if (!value) return <span style={{ color: '#94a3b8' }}>—</span>
  const short = value.length > 70 ? `${value.slice(0, 70)}…` : value
  return (
    <span title={value} style={{ color: '#dc2626', fontSize: '0.82rem' }}>
      {short}
    </span>
  )
}

export default function QueueMaintenance() {
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

  const colDefs: ColDef<UploadJob>[] = [
    { field: 'job_id', headerName: t('jobNum'), width: 90, sort: 'desc' },
    {
      field: 'source',
      headerName: t('source'),
      flex: 1.5,
      cellRenderer: (p: ICellRendererParams<UploadJob>) =>
        p.value ? <code style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>{p.value}</code> : <span style={{ color: '#94a3b8' }}>—</span>,
    },
    {
      field: 'status',
      headerName: t('status'),
      width: 130,
      cellRenderer: (p: ICellRendererParams<UploadJob>) => <StatusCell value={p.value} />,
    },
    {
      field: 'license_plate',
      headerName: t('plate'),
      width: 130,
      valueFormatter: (p) => (p.value && p.value !== '11111' ? p.value : t('plateNotIdentified')),
    },
    {
      field: 'error_message',
      headerName: t('failingReason'),
      flex: 2,
      cellRenderer: (p: ICellRendererParams<UploadJob>) => <ErrorCell value={p.value} />,
    },
  ]

  return (
    <div style={{ padding: '1.5rem 2rem', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', color: '#0f172a' }}>{t('queueMaintenance')}</h1>
          <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '0.92rem' }}>
            {t('queueSubtitle')}{' '}
            <Link to="/settings" style={{ color: '#2563eb' }}>{t('editBlurSettings')}</Link>
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
            style={{ padding: '8px 16px', background: '#1e40af', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            {uploading ? t('uploading') : t('uploadVideo')}
          </button>
          <button
            onClick={handleResetStuck}
            disabled={resettingStuck}
            style={{ padding: '8px 16px', background: '#dc2626', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            {resettingStuck ? '...' : 'איפוס תקועים'}
          </button>
        </div>
      </div>

      {settings && (
        <div style={{ marginBottom: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', background: '#f1f5f9', borderRadius: 8 }}>
          <strong style={{ fontSize: '0.88rem' }}>{t('blurKernelSize')}:</strong>
          <span style={{ background: '#e0e7ff', color: '#4338ca', padding: '2px 8px', borderRadius: 4, fontSize: '0.88rem', fontWeight: 600 }}>
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
          style={{ padding: '7px 12px', borderRadius: 8, border: '1.5px solid #d7dfeb', fontSize: '0.9rem', width: 220, direction: 'rtl' }}
        />
      </div>

      {loading ? (
        <p style={{ color: '#64748b' }}>{t('loading')}</p>
      ) : (
        <div style={{ height: 520, borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
          <AgGridReact<UploadJob>
            theme={themeQuartz}
            rowData={jobs}
            columnDefs={colDefs}
            quickFilterText={quickFilter}
            enableRtl={true}
            pagination={true}
            paginationPageSize={20}
            rowHeight={48}
            defaultColDef={{ sortable: true, filter: true, resizable: true }}
          />
        </div>
      )}
    </div>
  )
}
