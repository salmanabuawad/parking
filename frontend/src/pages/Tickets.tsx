import { useEffect, useMemo, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
import { FileText } from 'lucide-react'
import { useAgGridTheme } from '../lib/agGridTheme'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import { ticketsApi } from '../api'
import { getFontSizeWidthMultiplier, subscribeFontSize } from '../lib/fontSizeStore'
import { he } from '../i18n/he'
import { useRtl } from '../hooks/useRtl'
import ExcelLikeFilter from '../components/grid/ExcelLikeFilter'

ModuleRegistry.registerModules([AllCommunityModule])

interface Ticket {
  id: number
  license_plate: string
  location?: string
  status: string
  created_at?: string
  violation_rule_id?: string
  violation_confidence?: number
}

const STATUS_BADGE: Record<string, { cls: string; label: string }> = {
  pending_review: { cls: 'badge-warning', label: 'ממתין לבדיקה' },
  approved:       { cls: 'badge-success', label: 'אושר' },
  final:          { cls: 'badge-success', label: 'סופי' },
  rejected:       { cls: 'badge-danger',  label: 'נדחה' },
}

function StatusBadge({ value }: { value: string }) {
  const s = STATUS_BADGE[value] ?? { cls: 'badge-neutral', label: value }
  return <span className={`badge ${s.cls}`}>{s.label}</span>
}

function ActionCell({ data }: ICellRendererParams<Ticket>) {
  const navigate = useNavigate()
  if (!data) return null
  return (
    <button
      onClick={() => navigate(`/tickets/${data.id}`)}
      className="inline-flex items-center gap-1 px-3 py-1 rounded-md text-xs font-semibold bg-theme-accent text-white hover:bg-theme-accent-hover transition-colors"
    >
      {he.tickets.review}
    </button>
  )
}

const FILTER_BUTTONS = [
  { key: '', label: he.tickets.all ?? 'הכל' },
  { key: 'pending_review', label: 'ממתין' },
  { key: 'approved', label: 'אושר' },
  { key: 'rejected', label: 'נדחה' },
]

export default function Tickets() {
  useRtl(`${he.tickets.title} | ${he.app.title}`)
  const agTheme = useAgGridTheme()

  const [fsVer, setFsVer] = useState(0)
  useEffect(() => subscribeFontSize(() => setFsVer(v => v + 1)), [])

  const [tickets, setTickets] = useState<Ticket[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [quickFilter, setQuickFilter] = useState('')
  const gridRef = useRef<AgGridReact<Ticket>>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    ticketsApi
      .list(filter || undefined)
      .then(({ data }) => setTickets(data))
      .catch((err) => {
        setTickets([])
        if (err?.response?.status === 401) setError(he.tickets.loginRequired)
        else setError(he.tickets.loadError)
      })
      .finally(() => setLoading(false))
  }, [filter])

  const colDefs = useMemo<ColDef<Ticket>[]>(() => {
    const w = getFontSizeWidthMultiplier()
    return [
      { field: 'id', headerName: 'מזהה', width: Math.round(80 * w), sort: 'desc' },
      {
        field: 'license_plate',
        headerName: 'לוחית רישוי',
        flex: 1,
        valueFormatter: (p) =>
          p.value && p.value !== '11111' ? p.value : he.tickets.plateNotIdentified,
      },
      { field: 'location', headerName: 'מיקום', flex: 1.5, valueFormatter: (p) => p.value || '—' },
      {
        field: 'status',
        headerName: 'סטטוס',
        width: Math.round(150 * w),
        cellRenderer: (p: ICellRendererParams<Ticket>) => <StatusBadge value={p.value} />,
      },
      {
        field: 'violation_rule_id',
        headerName: 'כלל הפרה',
        width: Math.round(130 * w),
        valueFormatter: (p) => p.value || '—',
      },
      {
        field: 'violation_confidence',
        headerName: 'ביטחון',
        width: Math.round(100 * w),
        valueFormatter: (p) => (p.value != null ? `${Math.round(p.value * 100)}%` : '—'),
      },
      {
        field: 'created_at',
        headerName: 'תאריך',
        width: Math.round(120 * w),
        valueFormatter: (p) =>
          p.value ? new Date(p.value).toLocaleDateString('he-IL') : '—',
      },
      {
        headerName: 'פעולה',
        width: Math.round(100 * w),
        sortable: false,
        filter: false,
        cellRenderer: ActionCell,
      },
    ]
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fsVer])

  const onFilterChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setQuickFilter(e.target.value)
  }, [])

  return (
    <div className="page-container">
      {/* Page header */}
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon">
          <FileText className="w-5 h-5" strokeWidth={1.5} />
        </span>
        <h1 className="page-header-title">{he.tickets.title}</h1>
      </div>

      {/* Status filter pills */}
      <div className="flex flex-wrap gap-2">
        {FILTER_BUTTONS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-4 py-1.5 rounded-full text-theme-sm font-medium border transition-colors ${
              filter === key
                ? 'bg-theme-accent text-white border-theme-accent'
                : 'bg-white text-theme-text-primary border-theme-card-border hover:bg-black/5'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Quick filter search */}
      <div className="w-64">
        <input
          type="search"
          placeholder="חיפוש חופשי..."
          value={quickFilter}
          onChange={onFilterChange}
          className="input-base"
        />
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12 text-theme-text-muted">{he.tickets.loading}</div>
      ) : error ? (
        <div className="text-red-600 py-4">{error}</div>
      ) : (
        <div className="grid-card">
          <AgGridReact<Ticket>
            ref={gridRef}
            theme={agTheme}
            rowData={tickets}
            columnDefs={colDefs}
            quickFilterText={quickFilter}
            enableRtl={true}
            pagination={true}
            paginationPageSize={20}
            rowHeight={48}
            defaultColDef={{ sortable: true, filter: ExcelLikeFilter, resizable: true }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      )}
    </div>
  )
}
