import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
import type { ColDef } from 'ag-grid-community'
import { useAgGridTheme } from '../lib/agGridTheme'
import { fieldConfigApi, FieldConfiguration } from '../api'
import { useFieldConfigInvalidate } from '../context/FieldConfigContext'
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

  const cancelAll = useCallback(() => {
    if (dirtyMap.size === 0) return
    if (confirm(`לבטל ${dirtyMap.size} שינויים?`)) {
      setDirtyMap(new Map())
      load()
    }
  }, [dirtyMap, load])

  const handleDelete = useCallback(async (c: FieldConfiguration) => {
    if (!confirm(`למחוק את השדה "${c.field_name}" מגריד "${c.grid_name}"?`)) return
    try {
      await fieldConfigApi.delete(c.grid_name, c.field_name)
      await load()
      invalidate()
      showToast('נמחק בהצלחה')
    } catch {
      showToast('שגיאה במחיקה', false)
    }
  }, [load, invalidate])

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
      cellStyle: (p: any) => ({
        textAlign: 'right',
        fontWeight: 600,
        background: isDirty(p.data) ? '#fef3c7' : undefined,
      }),
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
      valueParser: (p) => { const n = parseInt(p.newValue, 10); return isNaN(n) ? p.oldValue : Math.max(1, n) },
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
      valueGetter: (p) => p.data.visible !== false,
      valueSetter: (p) => { p.data.visible = p.newValue ?? true; return true },
    },
    {
      field: 'pinned',
      headerName: 'נעוץ',
      width: COL_W, minWidth: COL_W, maxWidth: COL_W,
      editable: true,
      cellEditor: 'agCheckboxCellEditor',
      cellRenderer: 'agCheckboxCellRenderer',
      cellStyle: { textAlign: 'right' },
      valueGetter: (p) => p.data.pinned ?? false,
      valueSetter: (p) => { p.data.pinned = p.newValue ?? false; return true },
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
          style={{ background: 'var(--app-danger)', color: '#fff', border: 'none', borderRadius: 5, padding: '2px 10px', cursor: 'pointer', fontSize: '0.8rem' }}
        >✕</button>
      ),
    },
  ], [isDirty, handleDelete])

  return (
    <div style={{ padding: '1.5rem 2rem', width: '100%', boxSizing: 'border-box', color: 'var(--app-text)', display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1, direction: 'rtl' }}>
      {toast && (
        <div style={{ position: 'fixed', top: 20, left: '50%', transform: 'translateX(-50%)', background: toast.ok ? '#065f46' : '#991b1b', color: '#fff', padding: '10px 24px', borderRadius: 8, fontWeight: 600, zIndex: 9999, fontSize: '0.95rem' }}>
          {toast.msg}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', color: 'var(--app-text)' }}>הגדרות שדות גריד</h1>
          <p style={{ margin: '4px 0 0', color: 'var(--app-text-muted)', fontSize: '0.9rem' }}>שליטה על רוחב, סדר ונראות עמודות בכל גריד</p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {dirtyMap.size > 0 && (
            <>
              <button onClick={cancelAll} disabled={saving} style={{ padding: '8px 16px', background: 'var(--app-surface-muted)', color: 'var(--app-text)', border: '1.5px solid var(--app-border)', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit' }}>
                ביטול ({dirtyMap.size})
              </button>
              <button onClick={saveAll} disabled={saving} style={{ padding: '8px 16px', background: 'var(--app-accent)', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit' }}>
                {saving ? 'שומר...' : `שמור הכל (${dirtyMap.size})`}
              </button>
            </>
          )}
          <button onClick={load} style={{ padding: '8px 16px', background: 'var(--app-surface-muted)', color: 'var(--app-text)', border: '1.5px solid var(--app-border)', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit' }}>
            רענן
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: '0.75rem', alignItems: 'center' }}>
        <select
          value={filterGrid}
          onChange={(e) => setFilterGrid(e.target.value)}
          style={{ padding: '7px 12px', borderRadius: 8, border: '1.5px solid var(--app-border)', background: 'var(--app-surface)', color: 'var(--app-text)', fontSize: '0.9rem', direction: 'rtl' }}
        >
          <option value="all">כל הגרידים</option>
          {uniqueGrids.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
        <input
          type="search"
          placeholder="חיפוש..."
          value={quickFilter}
          onChange={(e) => setQuickFilter(e.target.value)}
          style={{ padding: '7px 12px', borderRadius: 8, border: '1.5px solid var(--app-border)', background: 'var(--app-surface)', color: 'var(--app-text)', fontSize: '0.9rem', width: 200, direction: 'rtl' }}
        />
        <span style={{ color: 'var(--app-text-muted)', fontSize: '0.88rem' }}>{filtered.length} רשומות</span>
      </div>

      {loading ? (
        <p style={{ color: 'var(--app-text-muted)' }}>{t('loading')}</p>
      ) : (
        <div style={{ flex: 1, minHeight: 0, borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
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
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      )}
    </div>
  )
}
