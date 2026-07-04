import { useState, useEffect, useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import { Camera as CameraIcon, Plus, Pencil, Trash2, X, Clapperboard, Eye, Map as MapIcon, List } from 'lucide-react'
import { camerasApi, violationRulesApi, parkingZonesApi, inspectorsApi, simulationApi, mapConfigApi } from '../api'
import type { SimulationSource } from '../api'
import CameraZoneConfigurator from './CameraZoneConfigurator'
import CameraZoneView from './CameraZoneView'
import CameraMap, { STATUS_META } from './CameraMap'
import CameraLocationPicker from './CameraLocationPicker'
import { useAgGridTheme } from '../lib/agGridTheme'
import { DEFAULT_COL_DEF } from '../lib/gridConfig'
import { t } from '../i18n'

ModuleRegistry.registerModules([AllCommunityModule])

const CONNECTION_TYPES = ['ip', 'bluetooth', 'wifi', 'rtsp', 'usb', 'other'] as const
const PARAM_SOURCES = ['manual', 'manufacturer_manual'] as const
const MODAL_TABS = [
  { key: 'general', label: 'כללי' },
  { key: 'zones', label: 'אזורים וכללים' },
  { key: 'zonemap', label: 'מפת אכיפה' },
  { key: 'advanced', label: 'מתקדם' },
] as const
type ModalTab = typeof MODAL_TABS[number]['key']

interface Camera {
  id: number
  name: string
  location?: string
  connection_type: string
  connection_config?: Record<string, unknown>
  param_source?: string
  params?: Record<string, unknown>
  manufacturer?: string
  model?: string
  is_active: boolean
  violation_rules?: string[] | null
  violation_zone?: string | null
  assigned_inspector_id?: number | null
  zone_ids?: number[]
  source_type?: string
  rtsp_url?: string
  latitude?: number | null
  longitude?: number | null
  status?: string | null
  city?: string | null
}

interface CameraForm {
  name: string
  location: string
  connection_type: string
  connection_config: Record<string, unknown> | string
  param_source: string
  params: Record<string, unknown> | string
  manufacturer: string
  model: string
  is_active: boolean
  violation_rules: string[]
  selected_zone_ids: number[]
  assigned_inspector_id: number | null
  source_type: string
  rtsp_url: string
  simulation_source: string
  latitude: string
  longitude: string
}

interface ParkingZone {
  id: number
  zone_code: string
  name_he: string
  name_en: string
  description_he?: string
  is_active: boolean
}

interface ViolationRuleOption {
  id: string
  label: string
  title: string
}

const EMPTY_FORM: CameraForm = {
  name: '', location: '', connection_type: 'ip',
  connection_config: {}, param_source: 'manual', params: {},
  manufacturer: '', model: '', is_active: true,
  violation_rules: [], selected_zone_ids: [], assigned_inspector_id: null,
  source_type: 'uploaded_image', rtsp_url: '', simulation_source: '',
  latitude: '', longitude: '',
}

export default function Cameras() {
  const agTheme = useAgGridTheme()
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [availableRules, setAvailableRules] = useState<ViolationRuleOption[]>([])
  const [availableZones, setAvailableZones] = useState<ParkingZone[]>([])
  const [inspectors, setInspectors] = useState<{ id: number; full_name: string }[]>([])
  const [cameraZoneMap, setCameraZoneMap] = useState<Record<number, number[]>>({})
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Camera | null>(null)
  const [viewing, setViewing] = useState<Camera | null>(null)
  const [tab, setTab] = useState<ModalTab>('general')
  const [form, setForm] = useState<CameraForm>(EMPTY_FORM)
  const [simSources, setSimSources] = useState<SimulationSource[]>([])
  const [seeding, setSeeding] = useState(false)
  const [view, setView] = useState<'list' | 'map'>('list')
  const [mapStyleUrl, setMapStyleUrl] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [camsResult, rulesResult, zonesResult, inspectorsResult, simsResult, mapCfg] = await Promise.all([
        camerasApi.list(),
        violationRulesApi.list(),
        parkingZonesApi.list(),
        inspectorsApi.list(true).catch(() => []),
        simulationApi.sources().catch(() => []),
        mapConfigApi.get().catch(() => ({ maptiler_key: '', style_url: null as string | null })),
      ])
      const cams: Camera[] = camsResult.data
      setCameras(cams)
      setInspectors(inspectorsResult as { id: number; full_name: string }[])
      setSimSources(simsResult as SimulationSource[])
      setMapStyleUrl(mapCfg.style_url || null)
      setAvailableRules(
        rulesResult.data
          .filter((r: any) => r.is_active)
          .map((r: any) => ({ id: r.rule_id, label: `${r.rule_id} — ${r.title_he}`, title: r.title_he || r.rule_id }))
      )
      setAvailableZones(zonesResult.data.filter((z: any) => z.is_active))
      const zoneEntries = await Promise.all(
        cams.map(async (cam) => {
          try {
            const res = await parkingZonesApi.getCameraZones(cam.id)
            return [cam.id, (res.data as ParkingZone[]).map(z => z.id)] as [number, number[]]
          } catch {
            return [cam.id, []] as [number, number[]]
          }
        })
      )
      setCameraZoneMap(Object.fromEntries(zoneEntries))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const parseJson = (v: unknown): Record<string, unknown> => {
    if (typeof v === 'object' && v !== null) return v as Record<string, unknown>
    try { return (v ? JSON.parse(String(v)) : {}) as Record<string, unknown> } catch { return {} }
  }

  const toggleZone = (id: number) => {
    setForm(f => ({
      ...f,
      selected_zone_ids: f.selected_zone_ids.includes(id)
        ? f.selected_zone_ids.filter(z => z !== id)
        : [...f.selected_zone_ids, id],
    }))
  }

  const openAdd = () => { setEditing(null); setForm(EMPTY_FORM); setTab('general'); setModalOpen(true) }
  const openEdit = (c: Camera) => {
    setEditing(c)
    setForm({
      name: c.name, location: c.location || '', connection_type: c.connection_type,
      connection_config: c.connection_config || {}, param_source: c.param_source || 'manual',
      params: c.params || {}, manufacturer: c.manufacturer || '', model: c.model || '',
      is_active: c.is_active ?? true,
      violation_rules: c.violation_rules || [],
      selected_zone_ids: cameraZoneMap[c.id] || [],
      assigned_inspector_id: c.assigned_inspector_id ?? null,
      source_type: c.source_type || 'uploaded_image',
      rtsp_url: c.rtsp_url || '',
      simulation_source: (c.connection_config?.simulation_source as string) || '',
      latitude: c.latitude != null ? String(c.latitude) : '',
      longitude: c.longitude != null ? String(c.longitude) : '',
    })
    setTab('general')
    setModalOpen(true)
  }
  const closeModal = () => { setModalOpen(false); setEditing(null); setForm(EMPTY_FORM) }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) { setTab('general'); return }
    try {
      const cfg = parseJson(form.connection_config)
      if (form.source_type === 'simulation' && form.simulation_source) cfg.simulation_source = form.simulation_source
      const lat = form.latitude.trim() === '' ? null : Number(form.latitude)
      const lng = form.longitude.trim() === '' ? null : Number(form.longitude)
      if ((lat !== null && Number.isNaN(lat)) || (lng !== null && Number.isNaN(lng))) {
        setTab('general'); alert('קו רוחב / קו אורך לא תקינים'); return
      }
      const payload = {
        ...form,
        connection_config: cfg,
        params: parseJson(form.params),
        violation_rules: form.violation_rules.length > 0 ? form.violation_rules : null,
        violation_zone: null,
        latitude: lat,
        longitude: lng,
      }
      let camId: number
      if (editing) { await camerasApi.update(editing.id, payload); camId = editing.id }
      else { const res = await camerasApi.create(payload); camId = res.data.id }
      await parkingZonesApi.setCameraZones(camId, form.selected_zone_ids)
      closeModal(); load()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      alert(ax.response?.data?.detail || ax.message)
    }
  }

  const seedSimulation = async () => {
    setSeeding(true)
    try {
      const res = await simulationApi.seedCameras()
      await load()
      alert(`נוצרו/עודכנו ${res.count} מצלמות סימולציה — פתח מצלמה לעריכה כדי לצייר מקטעים`)
    } catch (err: unknown) {
      const ax = err as { message?: string }
      alert(ax.message || 'שגיאה ביצירת מצלמות סימולציה')
    } finally { setSeeding(false) }
  }

  const selectFromMap = (id: number) => { const c = cameras.find(x => x.id === id); if (c) setViewing(c) }
  const editFromMap = (id: number) => { const c = cameras.find(x => x.id === id); if (c) openEdit(c) }

  const remove = async (id: number) => {
    if (!confirm(t('removeCameraConfirm'))) return
    try { await camerasApi.delete(id); load() }
    catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      alert(ax.response?.data?.detail || ax.message)
    }
  }

  const inspectorName = (id?: number | null) => (id ? inspectors.find(i => i.id === id)?.full_name ?? `#${id}` : '—')
  const zoneNames = (id: number) => availableZones.filter(z => (cameraZoneMap[id] || []).includes(z.id)).map(z => z.name_he).join(', ')

  const colDefs = useMemo<ColDef<Camera>[]>(() => [
    { field: 'name', headerName: 'שם', flex: 1, minWidth: 130 },
    { field: 'location', headerName: 'מיקום', flex: 1, valueFormatter: p => p.value || '—' },
    { field: 'connection_type', headerName: 'סוג חיבור', width: 120 },
    { headerName: 'יצרן/דגם', flex: 1, valueGetter: p => [p.data?.manufacturer, p.data?.model].filter(Boolean).join(' ') || '—' },
    { headerName: 'אזורים', flex: 1, valueGetter: p => zoneNames(p.data!.id) || '—' },
    { headerName: 'פקח מטפל', width: 150, valueGetter: p => inspectorName(p.data?.assigned_inspector_id) },
    {
      field: 'status', headerName: 'מצב', width: 130,
      valueGetter: p => p.data?.status || (p.data?.is_active ? 'online' : 'offline'),
      cellRenderer: (p: ICellRendererParams<Camera>) => {
        const meta = STATUS_META.find(s => s.key === p.value)
        return <span className="inline-flex items-center gap-1.5 text-theme-sm"><span className="w-2.5 h-2.5 rounded-full" style={{ background: meta?.color || '#64748b' }} />{meta?.label || p.value}</span>
      },
    },
    {
      field: 'is_active', headerName: 'מופעל', width: 100,
      cellRenderer: (p: ICellRendererParams<Camera>) =>
        <span className={`badge ${p.value ? 'badge-success' : 'badge-neutral'}`}>{p.value ? 'כן' : 'לא'}</span>,
    },
    {
      headerName: '', width: 130, sortable: false, filter: false,
      cellRenderer: (p: ICellRendererParams<Camera>) => p.data ? (
        <div className="flex items-center gap-1 h-full">
          <button onClick={() => setViewing(p.data!)} className="btn-icon" title="תצוגת אזורים"><Eye className="w-4 h-4" /></button>
          <button onClick={() => openEdit(p.data!)} className="btn-icon" title={t('edit')}><Pencil className="w-4 h-4" /></button>
          <button onClick={() => remove(p.data!.id)} className="btn-icon text-red-600" title={t('delete')}><Trash2 className="w-4 h-4" /></button>
        </div>
      ) : null,
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [inspectors, availableZones, cameraZoneMap])

  return (
    <div className="page-container">
      {/* Page header */}
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon"><CameraIcon className="w-5 h-5" strokeWidth={1.5} /></span>
        <div className="flex-1 min-w-0">
          <h1 className="page-header-title">{t('cameras')}</h1>
          <p className="page-header-label opacity-90">{t('camerasIntro')}</p>
        </div>
        <div className="flex items-center rounded-lg border border-theme-card-border overflow-hidden">
          <button onClick={() => setView('list')} className={`px-2.5 py-1.5 text-theme-sm flex items-center gap-1 ${view === 'list' ? 'bg-theme-accent text-white' : 'text-theme-text-muted'}`}><List className="w-4 h-4" /> רשימה</button>
          <button onClick={() => setView('map')} className={`px-2.5 py-1.5 text-theme-sm flex items-center gap-1 ${view === 'map' ? 'bg-theme-accent text-white' : 'text-theme-text-muted'}`}><MapIcon className="w-4 h-4" /> מפה</button>
        </div>
        {simSources.length > 0 && (
          <button onClick={seedSimulation} disabled={seeding} className="btn-secondary" title="יוצר מצלמת סימולציה לכל קליפ לדוגמה בשרת">
            <Clapperboard className="w-4 h-4" /> {seeding ? 'יוצר...' : 'מצלמות סימולציה'}
          </button>
        )}
        <button onClick={openAdd} className="btn-primary"><Plus className="w-4 h-4" /> {t('addCamera')}</button>
      </div>

      {/* Camera list / map */}
      <div className="flex flex-col flex-1 min-h-0">
        {loading ? (
          <p className="text-theme-text-muted py-6 text-center">{t('loading')}</p>
        ) : view === 'map' ? (
          <div className="grid-card overflow-hidden relative">
            <CameraMap
              cameras={cameras}
              styleUrl={mapStyleUrl}
              onSelect={(c) => selectFromMap(c.id)}
              onEdit={(c) => editFromMap(c.id)}
            />
          </div>
        ) : (
          <div className="grid-card">
            <AgGridReact<Camera>
              theme={agTheme}
              rowData={cameras}
              columnDefs={colDefs}
              enableRtl={true}
              rowHeight={46}
              defaultColDef={DEFAULT_COL_DEF}
              overlayNoRowsTemplate={`<span style="color:#94a3b8">${t('noCameras')}</span>`}
              style={{ width: '100%', height: '100%' }}
            />
          </div>
        )}
      </div>

      {/* Add / edit modal — tabbed: sticky header + tabs, scrollable body, sticky footer */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 overflow-y-auto" onClick={closeModal}>
          <div className="app-card w-full max-w-4xl my-6 flex flex-col max-h-[90vh] overflow-hidden" dir="rtl" onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-theme-card-border">
              <h3 className="text-base font-semibold text-theme-text-primary">{editing ? t('editCamera') : t('addCamera')}</h3>
              <button type="button" onClick={closeModal} className="btn-icon" title={t('cancel')}><X className="w-5 h-5" /></button>
            </div>

            {/* Tabs */}
            <div className="flex items-center gap-1 px-3 sm:px-5 border-b border-theme-card-border flex-wrap">
              {MODAL_TABS.filter(tb => tb.key !== 'zonemap' || editing).map(tb => (
                <button key={tb.key} type="button" onClick={() => setTab(tb.key)}
                  className={`px-3 py-2 text-theme-sm border-b-2 -mb-px transition-colors ${tab === tb.key ? 'border-theme-accent text-theme-accent font-semibold' : 'border-transparent text-theme-text-muted hover:text-theme-text-primary'}`}>
                  {tb.label}
                </button>
              ))}
            </div>

            {/* Body (scrollable) */}
            <div className="flex-1 min-h-0 overflow-y-auto px-5 py-4">
              <form id="camera-form" onSubmit={save}>
                {/* ── General ── */}
                {tab === 'general' && (
                  <div className="flex flex-col gap-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="label-base">{t('nameRequired')}</label>
                        <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required className="input-base" />
                      </div>
                      <div>
                        <label className="label-base">{t('location')}</label>
                        <input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} className="input-base" placeholder={t('locationPlaceholder')} />
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="label-base">מקור תמונה לכיול</label>
                        <select className="input-base" value={form.source_type} onChange={e => setForm({ ...form, source_type: e.target.value })}>
                          <option value="uploaded_image">תמונה שהועלתה</option>
                          <option value="uploaded_video">וידאו שהועלה</option>
                          <option value="rtsp">RTSP (מצלמה חיה)</option>
                          <option value="simulation">סימולציה (קליפ לדוגמה)</option>
                        </select>
                      </div>
                      {form.source_type === 'rtsp' && (
                        <div>
                          <label className="label-base">RTSP URL</label>
                          <input value={form.rtsp_url} onChange={e => setForm({ ...form, rtsp_url: e.target.value })} className="input-base font-mono" placeholder="rtsp://user:pass@host:554/stream" />
                        </div>
                      )}
                      {form.source_type === 'simulation' && (
                        <div>
                          <label className="label-base">קליפ סימולציה</label>
                          <select value={form.simulation_source} onChange={e => setForm({ ...form, simulation_source: e.target.value })} className="input-base">
                            <option value="">— בחר קליפ —</option>
                            {simSources.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
                          </select>
                        </div>
                      )}
                    </div>
                    <div>
                      <label className="label-base">פקח מטפל</label>
                      <select
                        className="input-base sm:w-64"
                        value={form.assigned_inspector_id ?? ''}
                        onChange={e => setForm({ ...form, assigned_inspector_id: e.target.value ? parseInt(e.target.value, 10) : null })}
                      >
                        <option value="">— ללא —</option>
                        {inspectors.map(i => <option key={i.id} value={i.id}>{i.full_name}</option>)}
                      </select>
                      <p className="text-theme-xs text-theme-text-muted mt-1">דוחות מהמצלמה יוקצו אוטומטית לפקח זה</p>
                    </div>
                    <div>
                      <label className="label-base">מיקום על המפה</label>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-2">
                        <input type="number" step="any" value={form.latitude} onChange={e => setForm({ ...form, latitude: e.target.value })} className="input-base" placeholder="קו רוחב (lat) — 32.3215" />
                        <input type="number" step="any" value={form.longitude} onChange={e => setForm({ ...form, longitude: e.target.value })} className="input-base" placeholder="קו אורך (lng) — 34.8532" />
                      </div>
                      <CameraLocationPicker
                        lat={form.latitude.trim() !== '' && !Number.isNaN(Number(form.latitude)) ? Number(form.latitude) : null}
                        lng={form.longitude.trim() !== '' && !Number.isNaN(Number(form.longitude)) ? Number(form.longitude) : null}
                        styleUrl={mapStyleUrl}
                        onChange={(la, ln) => setForm(f => ({ ...f, latitude: String(la), longitude: String(ln) }))}
                      />
                      <p className="text-theme-xs text-theme-text-muted mt-1">לחץ על המפה לקביעת מיקום, או גרור את הסמן. השאר ריק אם אין מיקום.</p>
                    </div>
                    <label className="flex items-center gap-2 text-theme-sm"><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} /> {t('active')}</label>
                  </div>
                )}

                {/* ── Zones & rules ── */}
                {tab === 'zones' && (
                  <div className="flex flex-col gap-5">
                    <div>
                      <label className="label-base">אזורי חניה באזור המצלמה</label>
                      <div className="flex flex-wrap gap-2">
                        {availableZones.length === 0 && <span className="text-theme-text-muted text-theme-sm">אין אזורים מוגדרים</span>}
                        {availableZones.map(zone => (
                          <label
                            key={zone.id}
                            title={zone.description_he || zone.name_he}
                            className={`flex items-center gap-1.5 text-theme-sm rounded border px-2 py-1 cursor-pointer ${form.selected_zone_ids.includes(zone.id) ? 'bg-green-100 border-green-300' : 'border-theme-card-border'}`}
                          >
                            <input type="checkbox" checked={form.selected_zone_ids.includes(zone.id)} onChange={() => toggleZone(zone.id)} />
                            {zone.name_he}
                          </label>
                        ))}
                      </div>
                      <p className="text-theme-xs text-theme-text-muted mt-1">אם לא נבחר אזור — כל הכללים ייבדקו (ברירת מחדל)</p>
                    </div>
                    <div>
                      <label className="label-base">כללי הפרה לבדיקה</label>
                      <div className="border border-theme-card-border rounded-lg max-h-72 overflow-y-auto p-1 grid grid-cols-1 sm:grid-cols-2 gap-0.5">
                        {availableRules.map(rule => {
                          const on = form.violation_rules.includes(rule.id)
                          return (
                            <label key={rule.id} title={rule.label} className={`flex items-center gap-1.5 text-theme-xs rounded px-2 py-1.5 cursor-pointer ${on ? 'bg-green-50' : 'hover:bg-black/5'}`}>
                              <input type="checkbox" className="shrink-0" checked={on} onChange={e => {
                                const next = e.target.checked ? [...form.violation_rules, rule.id] : form.violation_rules.filter(r => r !== rule.id)
                                setForm({ ...form, violation_rules: next })
                              }} />
                              <span className="truncate">{rule.title}</span>
                            </label>
                          )
                        })}
                      </div>
                      <p className="text-theme-xs text-theme-text-muted mt-1">אם לא נבחר כלום — כל הכללים ייבדקו (ברירת מחדל)</p>
                    </div>
                  </div>
                )}

                {/* ── Advanced ── */}
                {tab === 'advanced' && (
                  <div className="flex flex-col gap-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="label-base">{t('connectionType')}</label>
                        <select value={form.connection_type} onChange={e => setForm({ ...form, connection_type: e.target.value })} className="input-base">
                          {CONNECTION_TYPES.map(ct => <option key={ct} value={ct}>{ct}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="label-base">{t('paramSource')}</label>
                        <select value={form.param_source} onChange={e => setForm({ ...form, param_source: e.target.value })} className="input-base">
                          {PARAM_SOURCES.map(p => <option key={p} value={p}>{p.replace('_', ' ')}</option>)}
                        </select>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="label-base">{t('manufacturer')}</label>
                        <input value={form.manufacturer} onChange={e => setForm({ ...form, manufacturer: e.target.value })} className="input-base" />
                      </div>
                      <div>
                        <label className="label-base">{t('model')}</label>
                        <input value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} className="input-base" />
                      </div>
                    </div>
                    <div className="text-theme-xs text-theme-text-muted -mb-1">הגדרות טכניות (JSON) — לרוב אין צורך לשנות</div>
                    <div>
                      <label className="label-base">{t('connectionConfigJson')}</label>
                      <textarea value={typeof form.connection_config === 'string' ? form.connection_config : JSON.stringify(form.connection_config || {}, null, 2)} onChange={e => setForm({ ...form, connection_config: e.target.value })} rows={3} className="input-base font-mono text-theme-xs" placeholder='{"ip":"192.168.1.100","port":554}' />
                    </div>
                    <div>
                      <label className="label-base">{t('paramsJson')}</label>
                      <textarea value={typeof form.params === 'string' ? form.params : JSON.stringify(form.params || {}, null, 2)} onChange={e => setForm({ ...form, params: e.target.value })} rows={3} className="input-base font-mono text-theme-xs" placeholder='{"moving":true,"night_light":true,"resolution":"1080p","fps":30}' />
                    </div>
                  </div>
                )}
              </form>

              {/* ── Zone map (edit-only; auto-saves independently) ── */}
              {tab === 'zonemap' && editing && (
                <CameraZoneConfigurator cameraId={editing.id} rules={availableRules} />
              )}
            </div>

            {/* Footer (sticky) */}
            <div className="flex items-center gap-2 px-5 py-3 border-t border-theme-card-border">
              {tab === 'zonemap' ? (
                <>
                  <span className="text-theme-sm text-theme-text-muted">שינויים במפת האכיפה נשמרים אוטומטית</span>
                  <button type="button" onClick={closeModal} className="btn-primary ms-auto">סגור</button>
                </>
              ) : (
                <>
                  <button type="submit" form="camera-form" className="btn-primary">{editing ? t('update') : t('add')}</button>
                  <button type="button" onClick={closeModal} className="btn-cancel">{t('cancel')}</button>
                  {!editing && <span className="text-theme-xs text-theme-text-muted ms-auto">שמור כדי להגדיר מפת אכיפה</span>}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Read-only zone view — snapshot with configured grid + polygon zones overlaid */}
      {viewing && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 overflow-y-auto" onClick={() => setViewing(null)}>
          <div className="app-card w-full max-w-3xl my-6 p-5" dir="rtl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-semibold text-theme-text-primary">תצוגת אזורי אכיפה — {viewing.name}</h3>
              <button type="button" onClick={() => setViewing(null)} className="btn-icon" title={t('cancel')}><X className="w-5 h-5" /></button>
            </div>
            <CameraZoneView cameraId={viewing.id} rules={availableRules} />
          </div>
        </div>
      )}
    </div>
  )
}
