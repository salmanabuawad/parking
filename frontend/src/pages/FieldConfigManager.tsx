import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
import type { ColDef } from 'ag-grid-community'
import { Sliders, RefreshCw, Save, X } from 'lucide-react'
import { useAgGridTheme } from '../lib/agGridTheme'
import { fieldConfigApi, FieldConfiguration } from '../api'
import { useFieldConfigInvalidate } from '../context/FieldConfigContext'
import { useConfirm } from '../components/ConfirmDialog'
import { t } from '../i18n'

ModuleRegistry.registerModules([AllCommunityModule])

export default function FieldConfigManager() {
  const agTheme = useAgGridTheme()
  const invalidate = useFieldConfigInvalidate()
  const gridRef = useRef<AgGridReact<FieldConfiguration>>(null)

  const [configs, setConfigs] = useState<FieldConfiguration[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [filterGrid, setFilterGrid] = useState('all')
  const [quickFilter, setQuickFilter] = useState('')
  const [dirtyMap, setDirtyMap] = useState<Map<string, FieldConfiguration>>(new Map())
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)
  const confirm = useConfirm()

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3500)
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fieldConfigApi.getAll()
      setConfigs(data)
    } catch {
      showToast('שגיאה בטעינת הגדרות', false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const uniqueGrids = useMemo(() => {
    const s = new Set(configs.map((c) => c.grid_name))
    return Array.from(s).sort()
  }, [configs])

  const filtered = useMemo(() =>
    filterGrid === 'all' ? configs : configs.filter((c) => c.grid_name === filterGrid),
    [configs, filterGrid]
  )

  const isDirty = useCallback((c: FieldConfiguration) =>
    dirtyMap.has(`${c.grid_name}:${c.field_name}`), [dirtyMap])

  const markDirty = useCallback((c: FieldConfiguration, patch: Partial<FieldConfiguration>) => {
    const key = `${c.grid_name}:${c.field_name}`
    setDirtyMap((prev) => {
      const next = new Map(prev)
      next.set(key, { ...(prev.get(key) ?? c), ...patch } as FieldConfiguration)
      return next
    })
  }, [])

  const handleCellChanged = useCallback((ev: any) => {
    markDirty(ev.data, { [ev.colDef.field]: ev.newValue })
    ev.data[ev.colDef.field] = ev.newValue
  }, [markDirty])

  const saveAll = useCallback(async () => {
    if (dirtyMap.size === 0) { showToast('אין שינויים לשמירה', true); return }
    setSaving(true)
    try {
      const items = Array.from(dirtyMap.values()).map(({ id: _id, ...rest }) => rest)
      const { count } = await fieldConfigApi.upsertBulk(items)
      await load()
      invalidate()
      setDirtyMap(new Map())
      showToast(`נשמרו ${count} הגדרות`)
    } catch {
      showToast('שגיאה בשמירה', false)
    } finally {
      setSaving(false)
    }
  }, [dirtyMap, load, invalidate])

  const cancelAll = useCallback(async () => {
    if (dirtyMap.size === 0) return
    if (await confirm({ message: `לבטל ${dirtyMap.size} שינויים?`, confirmText: 'בטל שינויים', danger: true })) {
      setDirtyMap(new Map())
      load()
    }
  }, [dirtyMap, load, confirm])

  const handleDelete = useCallback(async (c: FieldConfiguration) => {
    if (!(await confirm({ message: `למחוק את השדה "${c.field_name}" מגריד "${c.grid_name}"?`, confirmText: 'מחק', danger: true }))) return
    try {
      await fieldConfigApi.delete(c.grid_name, c.field_name)
      await load()
      invalidate()
      showToast('נמחק בהצלחה')
    } catch {
      showToast('שגיאה במחיקה', false)
    }
  }, [load, invalidate, confirm])

  const COL_W = 124

  const colDefs = useMemo<ColDef<FieldConfiguration>[]>(() => [
    {
      field: 'field_name',
      headerName: 'שם שדה',
      width: COL_W, minWidth: COL_W, maxWidth: COL_W,
      pinned: 'right',
      lockPinned: true,
      suppressMovable: true,
      editable: false,
      cellStyle: (p: any) => {
        const style: Record<string, string | number> = {
          textAlign: 'right',
          fontWeight: 600,
        }
        if (p.data && p.data ? isDirty(p.data) : false) style.background = '#fef3c7'
        return style
      },
    },
    {
      field: 'grid_name',
      headerName: 'שם גריד',
      width: COL_W, minWidth: COL_W, maxWidth: COL_W,
      editable: false,
      cellStyle: { textAlign: 'right' },
    },
    {
      field: 'hebrew_name',
      headerName: 'שם בעברית',
      width: COL_W, minWidth: COL_W, maxWidth: COL_W,
      editable: true,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (p) => p.value || '—',
    },
    {
      field: 'width_chars',
      headerName: 'רוחב (תווים)',
      width: COL_W, minWidth: COL_W, maxWidth: COL_W,
      editable: true,
      type: 'numericColumn',
      cellStyle: { textAlign: 'right' },
      valueFormatter: (p) => (p.value ? p.value : 'אוטו'),   // 0 = auto/flex width
      valueParser: (p) => { const n = parseInt(p.newValue, 10); return isNaN(n) ? p.oldValue : Math.max(0, n) },
    },
    {
      field: 'padding',
      headerName: 'ריפוד (פיקסלים)',
      width: COL_W, minWidth: COL_W, maxWidth: COL_W,
      editable: true,
      type: 'numericColumn',
      cellStyle: { textAlign: 'right' },
      valueParser: (p) => { const n = parseInt(p.newValue, 10); return isNaN(n) ? p.oldValue : Math.max(0, n) },
    },
    {
      field: 'column_order',
      headerName: 'סדר',
      width: COL_W, minWidth: COL_W, maxWidth: COL_W,
      editable: true,
      type: 'numericColumn',
      cellStyle: { textAlign: 'right' },
      sort: 'asc',
      valueFormatter: (p) => p.value ?? '—',
      valueParser: (p) => { if (!p.newValue || p.newValue === '') return null; const n = parseInt(p.newValue, 10); return isNaN(n) ? null : n },
    },
    {
      field: 'visible',
      headerName: 'נראה',
      width: COL_W, minWidth: COL_W, maxWidth: COL_W,
      editable: true,
      cellEditor: 'agCheckboxCellEditor',
      cellRenderer: 'agCheckboxCellRenderer',
      cellStyle: { textAlign: 'right' },
      valueGetter: (p) => p.data?.visible !== false,
      valueSetter: (p) => { if (!p.data) return false; p.data.visible = p.newValue ?? true; return true },
    },
    {
      field: 'pinned',
      headerName: 'נעוץ',
      width: COL_W, minWidth: COL_W, maxWidth: COL_W,
      editable: true,
      cellEditor: 'agCheckboxCellEditor',
      cellRenderer: 'agCheckboxCellRenderer',
      cellStyle: { textAlign: 'right' },
      valueGetter: (p) => p.data?.pinned ?? false,
      valueSetter: (p) => { if (!p.data) return false; p.data.pinned = p.newValue ?? false; return true },
    },
    {
      field: 'pin_side',
      headerName: 'צד נעיצה',
      width: COL_W, minWidth: COL_W, maxWidth: COL_W,
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: [null, 'left', 'right'] },
      cellStyle: { textAlign: 'right' },
      valueFormatter: (p) => p.value === 'left' ? 'שמאל' : p.value === 'right' ? 'ימין' : '—',
    },
    {
      headerName: 'מחק',
      width: 80, minWidth: 80, maxWidth: 80,
      sortable: false, filter: false,
      cellRenderer: (p: any) => (
        <button
          onClick={() => handleDelete(p.data)}
          className="inline-flex items-center justify-center px-2.5 py-0.5 rounded-md text-xs font-semibold bg-red-600 text-white hover:bg-red-700 transition-colors"
        >✕</button>
      ),
    },
  ], [isDirty, handleDelete])

  return (
    <div className="page-container" dir="rtl">
      {toast && (
        <div
          className={`fixed top-5 left-1/2 -translate-x-1/2 z-[9999] px-6 py-2.5 rounded-lg font-semibold text-white text-theme-sm ${
            toast.ok ? 'bg-green-700' : 'bg-red-700'
          }`}
        >
          {toast.msg}
        </div>
      )}

      {/* Page header */}
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon">
          <Sliders className="w-5 h-5" strokeWidth={1.5} />
        </span>
        <div className="flex-1 min-w-0">
          <h1 className="page-header-title">הגדרות שדות גריד</h1>
          <p className="page-header-label opacity-90">שליטה על רוחב, סדר ונראות עמודות בכל גריד · רוחב "אוטו" (0) = עמודה גמישה</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {dirtyMap.size > 0 && (
            <>
              <button onClick={cancelAll} disabled={saving} className="btn-cancel">
                <X className="w-4 h-4" />
                <span>ביטול ({dirtyMap.size})</span>
              </button>
              <button onClick={saveAll} disabled={saving} className="btn-primary">
                <Save className="w-4 h-4" />
                <span>{saving ? 'שומר...' : `שמור הכל (${dirtyMap.size})`}</span>
              </button>
            </>
          )}
          <button onClick={load} className="btn-cancel">
            <RefreshCw className="w-4 h-4" />
            <span>רענן</span>
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="w-48">
          <select
            value={filterGrid}
            onChange={(e) => setFilterGrid(e.target.value)}
            className="input-base"
            dir="rtl"
          >
            <option value="all">כל הגרידים</option>
            {uniqueGrids.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
        <div className="w-52">
          <input
            type="search"
            placeholder="חיפוש..."
            value={quickFilter}
            onChange={(e) => setQuickFilter(e.target.value)}
            className="input-base"
            dir="rtl"
          />
        </div>
        <span className="text-theme-text-muted text-theme-sm">{filtered.length} רשומות</span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12 text-theme-text-muted">{t('loading')}</div>
      ) : (
        <div className="grid-card">
          <AgGridReact<FieldConfiguration>
            ref={gridRef}
            theme={agTheme}
            rowData={filtered}
            columnDefs={colDefs}
            quickFilterText={quickFilter}
            enableRtl={true}
            rowHeight={44}
            defaultColDef={{ sortable: true, filter: true, resizable: false }}
            onCellValueChanged={handleCellChanged}
            stopEditingWhenCellsLoseFocus={true}
            animateRows={false}
            overlayNoRowsTemplate={'<span style="color:#64748b">אין שדות להצגה</span>'}
          />
        </div>
      )}
    </div>
  )
}
