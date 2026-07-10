import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
import { Inbox as InboxIcon } from 'lucide-react'
import { useAgGridTheme } from '../lib/agGridTheme'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import { ticketsApi } from '../api'
import { DEFAULT_COL_DEF, emptyOverlay } from '../lib/gridConfig'
import { formatLocation } from '../lib/format'
import { useRtl } from '../hooks/useRtl'
import { useFieldConfig } from '../lib/useFieldConfig'
import { useFieldConfigVersion } from '../context/FieldConfigContext'

ModuleRegistry.registerModules([AllCommunityModule])

interface Ticket {
  id: number
  license_plate: string
  location?: string
  status: string
  created_at?: string
}

const STATUS: Record<string, string> = {
  pending_review: 'ממתין לטיפול', approved: 'אושר', rejected: 'נדחה', final: 'סופי',
}

function ReviewCell({ data }: ICellRendererParams<Ticket>) {
  const navigate = useNavigate()
  if (!data) return null
  return (
    <button onClick={() => navigate(`/tickets/${data.id}`)} className="btn-primary px-3 py-1 text-xs">
      טיפול
    </button>
  )
}

export default function Inbox() {
  useRtl('תיבת דוחות | פקח')
  const agTheme = useAgGridTheme()
  const [rows, setRows] = useState<Ticket[]>([])
  const [loading, setLoading] = useState(true)
  const [quick, setQuick] = useState('')

  useEffect(() => {
    setLoading(true)
    ticketsApi.inbox().then(setRows).catch(() => setRows([])).finally(() => setLoading(false))
  }, [])

  const cols = useMemo<ColDef<Ticket>[]>(() => [
    { field: 'id', headerName: 'מזהה', width: 90, sort: 'desc' },
    { field: 'license_plate', headerName: 'לוחית רישוי', flex: 1, valueFormatter: p => (p.value && p.value !== '11111' ? p.value : 'לא זוהה') },
    { field: 'location', headerName: 'מיקום', flex: 1.5, valueFormatter: p => formatLocation(p.value) },
    { field: 'status', headerName: 'סטטוס', width: 140, valueFormatter: p => STATUS[p.value] || p.value },
    { field: 'created_at', headerName: 'התקבל', width: 150, valueFormatter: p => (p.value ? new Date(p.value).toLocaleString('he-IL') : '—') },
    { headerName: 'פעולה', width: 110, sortable: false, filter: false, cellRenderer: ReviewCell },
  ], [])

  const cfgVer = useFieldConfigVersion()
  const [gridColDefs] = useFieldConfig(cols, 'inbox')

  return (
    <div className="page-container">
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon"><InboxIcon className="w-5 h-5" strokeWidth={1.5} /></span>
        <h1 className="page-header-title">תיבת דוחות שלי</h1>
      </div>

      <div className="w-64">
        <input type="search" placeholder="חיפוש חופשי..." value={quick} onChange={e => setQuick(e.target.value)} className="input-base" />
      </div>

      {loading ? (
        <div className="py-12 text-center text-theme-text-muted">טוען...</div>
      ) : (
        <div className="grid-card">
          <AgGridReact<Ticket>
            key={`inbox-${cfgVer}`}
            theme={agTheme}
            rowData={rows}
            columnDefs={gridColDefs}
            quickFilterText={quick}
            enableRtl
            rowHeight={48}
            defaultColDef={DEFAULT_COL_DEF}
            overlayNoRowsTemplate={emptyOverlay('אין דוחות בתיבה')}
          />
        </div>
      )}
    </div>
  )
}
