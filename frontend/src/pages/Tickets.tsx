import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry, themeQuartz } from 'ag-grid-community'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import { ticketsApi } from '../api'
import { he } from '../i18n/he'
import { useRtl } from '../hooks/useRtl'

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

const STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  pending_review: { bg: '#fff2d1', color: '#a16b00', label: 'ממתין לבדיקה' },
  approved:       { bg: '#daf5e6', color: '#0f8b4c', label: 'אושר' },
  final:          { bg: '#daf5e6', color: '#0f8b4c', label: 'סופי' },
  rejected:       { bg: '#fde8e8', color: '#c83737', label: 'נדחה' },
}

function StatusBadge({ value }: { value: string }) {
  const s = STATUS_STYLE[value] ?? { bg: '#f1f5f9', color: '#475569', label: value }
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

function ActionCell({ data }: ICellRendererParams<Ticket>) {
  const navigate = useNavigate()
  if (!data) return null
  return (
    <button
      onClick={() => navigate(`/tickets/${data.id}`)}
      style={{
        padding: '4px 12px',
        background: '#1e40af',
        color: '#fff',
        border: 'none',
        borderRadius: 6,
        cursor: 'pointer',
        fontSize: '0.82rem',
        fontFamily: 'inherit',
      }}
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

  const colDefs: ColDef<Ticket>[] = [
    { field: 'id', headerName: 'מזהה', width: 80, sort: 'desc' },
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
      width: 150,
      cellRenderer: (p: ICellRendererParams<Ticket>) => <StatusBadge value={p.value} />,
    },
    {
      field: 'violation_rule_id',
      headerName: 'כלל הפרה',
      width: 130,
      valueFormatter: (p) => p.value || '—',
    },
    {
      field: 'violation_confidence',
      headerName: 'ביטחון',
      width: 100,
      valueFormatter: (p) => (p.value != null ? `${Math.round(p.value * 100)}%` : '—'),
    },
    {
      field: 'created_at',
      headerName: 'תאריך',
      width: 120,
      valueFormatter: (p) =>
        p.value ? new Date(p.value).toLocaleDateString('he-IL') : '—',
    },
    {
      headerName: 'פעולה',
      width: 100,
      sortable: false,
      filter: false,
      cellRenderer: ActionCell,
    },
  ]

  const onFilterChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setQuickFilter(e.target.value)
  }, [])

  return (
    <div style={{ padding: '1.5rem', maxWidth: 1100, margin: '0 auto' }}>
      <h1 style={{ margin: '0 0 1rem', fontSize: '1.4rem', color: '#0f172a' }}>
        {he.tickets.title}
      </h1>

      {/* Status filter buttons */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '0.75rem' }}>
        {FILTER_BUTTONS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            style={{
              padding: '6px 16px',
              borderRadius: 20,
              border: '1.5px solid',
              borderColor: filter === key ? '#1e40af' : '#d7dfeb',
              background: filter === key ? '#1e40af' : '#fff',
              color: filter === key ? '#fff' : '#334155',
              cursor: 'pointer',
              fontWeight: filter === key ? 700 : 400,
              fontSize: '0.88rem',
              transition: 'all 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Quick filter search */}
      <div style={{ marginBottom: '0.75rem' }}>
        <input
          type="search"
          placeholder="חיפוש חופשי..."
          value={quickFilter}
          onChange={onFilterChange}
          style={{
            padding: '8px 14px',
            borderRadius: 8,
            border: '1.5px solid #d7dfeb',
            fontSize: '0.95rem',
            width: 260,
            outline: 'none',
            direction: 'rtl',
          }}
        />
      </div>

      {loading ? (
        <div style={{ color: '#64748b', padding: '2rem 0' }}>{he.tickets.loading}</div>
      ) : error ? (
        <div style={{ color: '#dc2626', padding: '1rem 0' }}>{error}</div>
      ) : (
        <div style={{ height: 520, borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
          <AgGridReact<Ticket>
            ref={gridRef}
            theme={themeQuartz}
            rowData={tickets}
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
