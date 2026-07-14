import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
import { DEFAULT_COL_DEF, emptyOverlay } from '../lib/gridConfig'
import { jobStatusBadge } from '../lib/jobStatus'
import { ListOrdered } from 'lucide-react'
import { useAgGridTheme } from '../lib/agGridTheme'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import api from '../api'
import { uploadApi, settingsApi } from '../api'
import { t } from '../i18n'
import { getFontSizeWidthMultiplier, subscribeFontSize } from '../lib/fontSizeStore'
import { useFieldConfig } from '../lib/useFieldConfig'
import { useFieldConfigVersion } from '../context/FieldConfigContext'

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

function StatusCell({ value }: { value: string }) {
  const s = jobStatusBadge(value)
  return <span className={`badge ${s.cls}`}>{s.label}</span>
}

function ErrorCell({ value }: { value: string | null }) {
  if (!value) return <span className="text-theme-text-muted">—</span>
  const short = value.length > 70 ? `${value.slice(0, 70)}…` : value
  return (
    <span title={value} className="text-red-600 text-theme-xs">
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
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)
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
    setMsg(null)
    try {
      const { data } = await uploadApi.resetStuckJobs()
      await fetchJobs()
      setMsg({ kind: 'ok', text: data.message || `אופסו ${data.reset_count} עבודות תקועות` })
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      setMsg({ kind: 'err', text: ax.response?.data?.detail || ax.message || 'שגיאה באיפוס עבודות' })
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
      setMsg({ kind: 'ok', text: 'הסרטון הועלה ונכנס לתור העיבוד' })
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      setMsg({ kind: 'err', text: ax.response?.data?.detail || ax.message || 'שגיאה בהעלאת הסרטון' })
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
          p.value ? <code className="text-theme-xs break-all">{p.value}</code> : <span className="text-theme-text-muted">—</span>,
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
              className="text-theme-link font-semibold no-underline text-theme-sm"
            >
              #{p.value}
            </Link>
          ) : (
            <span className="text-theme-text-muted">—</span>
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

  const cfgVer = useFieldConfigVersion()
  const [gridColDefs] = useFieldConfig(colDefs, 'queue-maintenance')

  return (
    <div className="page-container">
      {/* Page header */}
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon">
          <ListOrdered className="w-5 h-5" strokeWidth={1.5} />
        </span>
        <div className="flex-1 min-w-0">
          <h1 className="page-header-title">{t('queueMaintenance')}</h1>
          <p className="page-header-label opacity-90">
            {t('queueSubtitle')}{' '}
            <Link to="/settings" className="text-theme-link">{t('editBlurSettings')}</Link>
          </p>
        </div>
        <div className="flex-1" />
        <div className="action-bar flex flex-wrap items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            onChange={handleFileChange}
            disabled={uploading}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="btn-primary"
          >
            {uploading ? t('uploading') : t('uploadVideo')}
          </button>
          <button
            onClick={handleResetStuck}
            disabled={resettingStuck}
            className="btn-danger"
          >
            {resettingStuck ? '...' : 'איפוס תקועים'}
          </button>
        </div>
      </div>

      {msg && (
        <div className={`flex items-start gap-2 rounded-lg px-3 py-2 text-theme-sm border ${msg.kind === 'ok' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
          <span className="flex-1">{msg.text}</span>
          <button onClick={() => setMsg(null)} className="shrink-0 opacity-60 hover:opacity-100 leading-none" title="סגור">✕</button>
        </div>
      )}

      {settings && (
        <div className="app-card inline-flex items-center gap-2 px-3.5 py-1.5 self-start">
          <strong className="text-theme-sm">{t('blurKernelSize')}:</strong>
          <span className="badge badge-info">{settings.blur_kernel_size}</span>
        </div>
      )}

      <div className="w-56">
        <input
          type="search"
          placeholder="חיפוש..."
          value={quickFilter}
          onChange={(e) => setQuickFilter(e.target.value)}
          className="input-base"
        />
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12 text-theme-text-muted">{t('loading')}</div>
      ) : (
        <div className="grid-card">
          <AgGridReact<UploadJob>
            key={`queue-maintenance-${cfgVer}`}
            theme={agTheme}
            rowData={jobs}
            columnDefs={gridColDefs}
            quickFilterText={quickFilter}
            enableRtl={true}
            rowHeight={48}
            defaultColDef={DEFAULT_COL_DEF}
            overlayNoRowsTemplate={emptyOverlay('אין עבודות בתור')}
          />
        </div>
      )}
    </div>
  )
}
