import { useState, useEffect } from 'react'
import { Camera as CameraIcon } from 'lucide-react'
import { camerasApi, violationRulesApi, parkingZonesApi, inspectorsApi, getApiBase } from '../api'
import CameraSegmentsEditor from '../components/CameraSegmentsEditor'
import { t } from '../i18n'

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
  zone_ids?: number[]      // active parking zone IDs for this camera
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
  selected_zone_ids: number[]   // multi-select parking zones
  assigned_inspector_id: number | null
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
}

export default function Cameras() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Camera | null>(null)
  const [form, setForm] = useState<CameraForm>(EMPTY_FORM)
  const [availableRules, setAvailableRules] = useState<ViolationRuleOption[]>([])
  const [availableZones, setAvailableZones] = useState<ParkingZone[]>([])
  const [inspectors, setInspectors] = useState<{ id: number; full_name: string }[]>([])
  const [expandedSegments, setExpandedSegments] = useState<number | null>(null)
  // camera zone map: cameraId → zoneId[]
  const [cameraZoneMap, setCameraZoneMap] = useState<Record<number, number[]>>({})

  const load = async () => {
    setLoading(true)
    try {
      const [camsResult, rulesResult, zonesResult, inspectorsResult] = await Promise.all([
        camerasApi.list(),
        violationRulesApi.list(),
        parkingZonesApi.list(),
        inspectorsApi.list(true).catch(() => []),
      ])
      const cams: Camera[] = camsResult.data
      setCameras(cams)
      setInspectors(inspectorsResult as { id: number; full_name: string }[])
      setAvailableRules(
        rulesResult.data
          .filter((r: any) => r.is_active)
          .map((r: any) => ({ id: r.rule_id, label: `${r.rule_id} — ${r.title_he}` }))
      )
      setAvailableZones(zonesResult.data.filter((z: any) => z.is_active))

      // Load zones for each camera in parallel
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

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const cfg = parseJson(form.connection_config)
      const params = parseJson(form.params)
      const payload = {
        ...form,
        connection_config: cfg,
        params,
        violation_rules: form.violation_rules.length > 0 ? form.violation_rules : null,
        violation_zone: null,
      }
      let camId: number
      if (editing) {
        const res = await camerasApi.update(editing.id, payload)
        camId = editing.id
        // ignore unused res warning
        void res
      } else {
        const res = await camerasApi.create(payload)
        camId = res.data.id
      }
      // Save zone assignments
      await parkingZonesApi.setCameraZones(camId, form.selected_zone_ids)

      setEditing(null)
      setForm(EMPTY_FORM)
      load()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      alert(ax.response?.data?.detail || ax.message)
    }
  }

  const startEdit = (c: Camera) => {
    setEditing(c)
    setForm({
      name: c.name, location: c.location || '', connection_type: c.connection_type,
      connection_config: c.connection_config || {}, param_source: c.param_source || 'manual',
      params: c.params || {}, manufacturer: c.manufacturer || '', model: c.model || '',
      is_active: c.is_active ?? true,
      violation_rules: c.violation_rules || [],
      selected_zone_ids: cameraZoneMap[c.id] || [],
      assigned_inspector_id: c.assigned_inspector_id ?? null,
    })
  }

  const remove = async (id: number) => {
    if (!confirm(t('removeCameraConfirm'))) return
    try {
      await camerasApi.delete(id)
      load()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      alert(ax.response?.data?.detail || ax.message)
    }
  }

  return (
    <div className="page-container">
      {/* Page header */}
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon">
          <CameraIcon className="w-5 h-5" strokeWidth={1.5} />
        </span>
        <div className="flex-1 min-w-0">
          <h1 className="page-header-title">{t('cameras')}</h1>
          <p className="page-header-label opacity-90">{t('camerasIntro')}</p>
        </div>
      </div>

      <form onSubmit={save} className="app-card p-5">
        <h3 className="text-base font-semibold text-theme-text-primary mb-3">{editing ? t('editCamera') : t('addCamera')}</h3>
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
                className={`flex items-center gap-1 text-theme-sm rounded border px-2 py-1 cursor-pointer ${
                  form.selected_zone_ids.includes(zone.id)
                    ? 'bg-green-100 border-green-300'
                    : 'border-theme-card-border'
                }`}
              >
                <input
                  type="checkbox"
                  checked={form.selected_zone_ids.includes(zone.id)}
                  onChange={() => toggleZone(zone.id)}
                />
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
          {editing && <button type="button" onClick={() => { setEditing(null); setForm(EMPTY_FORM) }} className="btn-cancel">{t('cancel')}</button>}
        </div>
      </form>

      <h2 className="text-base font-semibold text-theme-text-primary">{t('configuredCameras')}</h2>
      {loading ? <p className="text-theme-text-muted">{t('loading')}</p> : (
        <ul className="list-none p-0 flex flex-col gap-2">
          {cameras.map(c => {
            const hasVideoDb = Boolean((c.connection_config as Record<string, unknown>)?.video_id)
            const hasVideoFile = Boolean((c.connection_config as Record<string, unknown>)?.sample_video)
            const hasSample = c.name === 'Sample Camera' || hasVideoDb || hasVideoFile
            const base = getApiBase().replace(/\/$/, '')
            const videoUrl: string = hasVideoDb ? `${base}/cameras/${c.id}/video` : `${base}/sample/video?t=${Date.now()}`
            const zoneIds = cameraZoneMap[c.id] || []
            const zoneNames = availableZones.filter(z => zoneIds.includes(z.id)).map(z => z.name_he)
            return (
              <li key={c.id} className="app-card p-4">
                <div className="flex justify-between items-center flex-wrap gap-2">
                  <div>
                    <strong>{c.name}</strong> — {c.connection_type} {c.location && `@ ${c.location}`}
                    {c.manufacturer && <span className="text-theme-text-muted ms-2">{c.manufacturer} {c.model}</span>}
                    {zoneNames.length > 0 && (
                      <div className="text-theme-xs text-green-700 mt-0.5">
                        אזורים: {zoneNames.join(', ')}
                      </div>
                    )}
                    {c.violation_rules && c.violation_rules.length > 0 && (
                      <div className="text-theme-xs text-theme-text-muted mt-0.5">
                        כללים: {c.violation_rules.join(', ')}
                      </div>
                    )}
                  </div>
                  <div className="action-bar flex flex-wrap items-center gap-2">
                    {hasSample && (
                      <a href={videoUrl} target="_blank" rel="noreferrer" className="btn-ghost">{t('watchSample')}</a>
                    )}
                    <button onClick={() => setExpandedSegments(expandedSegments === c.id ? null : c.id)} className="btn-ghost">מקטעים</button>
                    <button onClick={() => startEdit(c)} className="btn-secondary">{t('edit')}</button>
                    <button onClick={() => remove(c.id)} className="btn-danger">{t('delete')}</button>
                  </div>
                </div>
                {hasSample && (
                  <video src={videoUrl} controls className="w-full max-w-[400px] mt-2 rounded" />
                )}
                {expandedSegments === c.id && (
                  <CameraSegmentsEditor cameraId={c.id} rules={availableRules} />
                )}
              </li>
            )
          })}
        </ul>
      )}
      {!loading && cameras.length === 0 && <p className="text-theme-text-muted">{t('noCameras')}</p>}
    </div>
  )
}
