import { useState, useEffect, useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import { Camera as CameraIcon, Plus, Pencil, Trash2, X, Clapperboard } from 'lucide-react'
import { camerasApi, violationRulesApi, parkingZonesApi, inspectorsApi, simulationApi } from '../api'
import type { SimulationSource } from '../api'
import CameraZoneConfigurator from './CameraZoneConfigurator'
import { useAgGridTheme } from '../lib/agGridTheme'
import { DEFAULT_COL_DEF } from '../lib/gridConfig'
import { t } from '../i18n'

ModuleRegistry.registerModules([AllCommunityModule])

const CONNECTION_TYPES = ['ip', 'bluetooth', 'wifi', 'rtsp', 'usb', 'other'] as const
const PARAM_SOURCES = ['manual', 'manufacturer_manual'] as const

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
}

const EMPTY_FORM: CameraForm = {
  name: '', location: '', connection_type: 'ip',
  connection_config: {}, param_source: 'manual', params: {},
  manufacturer: '', model: '', is_active: true,
  violation_rules: [], selected_zone_ids: [], assigned_inspector_id: null,
  source_type: 'uploaded_image', rtsp_url: '', simulation_source: '',
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
  const [form, setForm] = useState<CameraForm>(EMPTY_FORM)
  const [simSources, setSimSources] = useState<SimulationSource[]>([])
  const [seeding, setSeeding] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [camsResult, rulesResult, zonesResult, inspectorsResult, simsResult] = await Promise.all([
        camerasApi.list(),
        violationRulesApi.list(),
        parkingZonesApi.list(),
        inspectorsApi.list(true).catch(() => []),
        simulationApi.sources().catch(() => []),
      ])
      const cams: Camera[] = camsResult.data
      setCameras(cams)
      setInspectors(inspectorsResult as { id: number; full_name: string }[])
      setSimSources(simsResult as SimulationSource[])
      setAvailableRules(
        rulesResult.data
          .filter((r: any) => r.is_active)
          .map((r: any) => ({ id: r.rule_id, label: `${r.rule_id} — ${r.title_he}` }))
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

  const openAdd = () => { setEditing(null); setForm(EMPTY_FORM); setModalOpen(true) }
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
    })
    setModalOpen(true)
  }
  const closeModal = () => { setModalOpen(false); setEditing(null); setForm(EMPTY_FORM) }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const cfg = parseJson(form.connection_config)
      if (form.source_type === 'simulation' && form.simulation_source) cfg.simulation_source = form.simulation_source
      const payload = {
        ...form,
        connection_config: cfg,
        params: parseJson(form.params),
        violation_rules: form.violation_rules.length > 0 ? form.violation_rules : null,
        violation_zone: null,
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
      field: 'is_active', headerName: 'סטטוס', width: 110,
      cellRenderer: (p: ICellRendererParams<Camera>) =>
        <span className={`badge ${p.value ? 'badge-success' : 'badge-neutral'}`}>{p.value ? 'פעיל' : 'לא פעיל'}</span>,
    },
    {
      headerName: '', width: 100, sortable: false, filter: false,
      cellRenderer: (p: ICellRendererParams<Camera>) => p.data ? (
        <div className="flex items-center gap-1 h-full">
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
        {simSources.length > 0 && (
          <button onClick={seedSimulation} disabled={seeding} className="btn-secondary" title="יוצר מצלמת סימולציה לכל קליפ לדוגמה בשרת">
            <Clapperboard className="w-4 h-4" /> {seeding ? 'יוצר...' : 'מצלמות סימולציה'}
          </button>
        )}
        <button onClick={openAdd} className="btn-primary"><Plus className="w-4 h-4" /> {t('addCamera')}</button>
      </div>

      {/* Camera list */}
      <div className="flex flex-col flex-1 min-h-0">
        {loading ? (
          <p className="text-theme-text-muted py-6 text-center">{t('loading')}</p>
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

      {/* Add / edit modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 overflow-y-auto" onClick={closeModal}>
          <div className="app-card w-full max-w-5xl my-6 p-5" dir="rtl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-semibold text-theme-text-primary">{editing ? t('editCamera') : t('addCamera')}</h3>
              <button type="button" onClick={closeModal} className="btn-icon" title={t('cancel')}><X className="w-5 h-5" /></button>
            </div>

            <form onSubmit={save}>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <label className="label-base">{t('nameRequired')}</label>
                  <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required className="input-base" />
                </div>
                <div>
                  <label className="label-base">{t('location')}</label>
                  <input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} className="input-base" placeholder={t('locationPlaceholder')} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 mb-3">
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
              <div className="mb-3">
                <label className="label-base">{t('connectionConfigJson')}</label>
                <textarea value={typeof form.connection_config === 'string' ? form.connection_config : JSON.stringify(form.connection_config || {}, null, 2)} onChange={e => setForm({ ...form, connection_config: e.target.value })} rows={2} className="input-base font-mono" placeholder='{"ip":"192.168.1.100","port":554}' />
              </div>
              <div className="mb-3">
                <label className="label-base">{t('paramsJson')}</label>
                <textarea value={typeof form.params === 'string' ? form.params : JSON.stringify(form.params || {}, null, 2)} onChange={e => setForm({ ...form, params: e.target.value })} rows={2} className="input-base font-mono" placeholder='{"moving":true,"night_light":true,"resolution":"1080p","fps":30}' />
              </div>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <label className="label-base">{t('manufacturer')}</label>
                  <input value={form.manufacturer} onChange={e => setForm({ ...form, manufacturer: e.target.value })} className="input-base" />
                </div>
                <div>
                  <label className="label-base">{t('model')}</label>
                  <input value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} className="input-base" />
                </div>
              </div>

              {/* Snapshot source for zone configuration */}
              <div className="grid grid-cols-2 gap-3 mb-3">
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

              {/* Handling inspector (#8) */}
              <div className="mb-3">
                <label className="label-base block mb-1">פקח מטפל</label>
                <select
                  className="input-base w-64"
                  value={form.assigned_inspector_id ?? ''}
                  onChange={e => setForm({ ...form, assigned_inspector_id: e.target.value ? parseInt(e.target.value, 10) : null })}
                >
                  <option value="">— ללא —</option>
                  {inspectors.map(i => <option key={i.id} value={i.id}>{i.full_name}</option>)}
                </select>
                <p className="text-theme-xs text-theme-text-muted mt-1">דוחות מהמצלמה יוקצו אוטומטית לפקח זה</p>
              </div>

              {/* Parking zones (multi-select) */}
              <div className="mb-3">
                <label className="label-base block mb-1">אזורי חניה באזור המצלמה (ניתן לבחור מספר)</label>
                <div className="flex flex-wrap gap-2">
                  {availableZones.length === 0 && <span className="text-theme-text-muted text-theme-sm">טוען אזורים...</span>}
                  {availableZones.map(zone => (
                    <label
                      key={zone.id}
                      className={`flex items-center gap-1 text-theme-sm rounded border px-2 py-1 cursor-pointer ${form.selected_zone_ids.includes(zone.id) ? 'bg-green-100 border-green-300' : 'border-theme-card-border'}`}
                    >
                      <input type="checkbox" checked={form.selected_zone_ids.includes(zone.id)} onChange={() => toggleZone(zone.id)} />
                      {zone.name_he}
                      {zone.description_he && <span className="text-theme-text-muted text-theme-xs"> — {zone.description_he}</span>}
                    </label>
                  ))}
                </div>
                <p className="text-theme-xs text-theme-text-muted mt-1">אם לא נבחר אזור — כל הכללים יבדקו (ברירת מחדל)</p>
              </div>

              {/* Violation rules (multi-select) */}
              <div className="mb-3">
                <label className="label-base block mb-1">כללי הפרה לבדיקה</label>
                <div className="flex flex-wrap gap-2">
                  {availableRules.map(rule => (
                    <label key={rule.id} className="flex items-center gap-1 text-theme-sm whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={form.violation_rules.includes(rule.id)}
                        onChange={e => {
                          const next = e.target.checked
                            ? [...form.violation_rules, rule.id]
                            : form.violation_rules.filter(r => r !== rule.id)
                          setForm({ ...form, violation_rules: next })
                        }}
                      />
                      {rule.label}
                    </label>
                  ))}
                </div>
                <p className="text-theme-xs text-theme-text-muted mt-1">אם לא נבחר כלום — כל הכללים יבדקו (ברירת מחדל)</p>
              </div>

              <div className="mb-4">
                <label className="flex items-center gap-1 text-theme-sm"><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} /> {t('active')}</label>
              </div>
              <div className="action-bar flex flex-wrap items-center gap-2">
                <button type="submit" className="btn-primary">{editing ? t('update') : t('add')}</button>
                <button type="button" onClick={closeModal} className="btn-cancel">{t('cancel')}</button>
              </div>
            </form>

            {/* Zone configuration — draw enforcement sections on the camera image (saved camera only) */}
            {editing && (
              <div className="mt-4 border-t border-theme-card-border pt-3">
                <div className="text-base font-semibold mb-2">הגדרת מקטעי אכיפה (ציור על תמונת המצלמה)</div>
                <CameraZoneConfigurator cameraId={editing.id} rules={availableRules} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
