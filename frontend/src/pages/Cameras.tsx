import { useState, useEffect } from 'react'
import { camerasApi, violationRulesApi, parkingZonesApi, getApiBase } from '../api'
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
  violation_rules: [], selected_zone_ids: [],
}

export default function Cameras() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Camera | null>(null)
  const [form, setForm] = useState<CameraForm>(EMPTY_FORM)
  const [availableRules, setAvailableRules] = useState<ViolationRuleOption[]>([])
  const [availableZones, setAvailableZones] = useState<ParkingZone[]>([])
  // camera zone map: cameraId → zoneId[]
  const [cameraZoneMap, setCameraZoneMap] = useState<Record<number, number[]>>({})

  const load = async () => {
    setLoading(true)
    try {
      const [camsResult, rulesResult, zonesResult] = await Promise.all([
        camerasApi.list(),
        violationRulesApi.list(),
        parkingZonesApi.list(),
      ])
      const cams: Camera[] = camsResult.data
      setCameras(cams)
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
    <div style={{ padding: '1.5rem', fontFamily: 'system-ui', maxWidth: 900 }}>
      <h1>{t('cameras')}</h1>
      <p style={{ color: '#666', marginBottom: '1.5rem' }}>
        {t('camerasIntro')}
      </p>

      <form onSubmit={save} style={{ background: '#f5f5f5', padding: '1.25rem', borderRadius: 8, marginBottom: '1.5rem' }}>
        <h3>{editing ? t('editCamera') : t('addCamera')}</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div>
            <label>{t('nameRequired')}</label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required style={{ width: '100%', padding: 6 }} />
          </div>
          <div>
            <label>{t('location')}</label>
            <input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} style={{ width: '100%', padding: 6 }} placeholder={t('locationPlaceholder')} />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div>
            <label>{t('connectionType')}</label>
            <select value={form.connection_type} onChange={e => setForm({ ...form, connection_type: e.target.value })} style={{ width: '100%', padding: 6 }}>
              {CONNECTION_TYPES.map(ct => <option key={ct} value={ct}>{ct}</option>)}
            </select>
          </div>
          <div>
            <label>{t('paramSource')}</label>
            <select value={form.param_source} onChange={e => setForm({ ...form, param_source: e.target.value })} style={{ width: '100%', padding: 6 }}>
              {PARAM_SOURCES.map(p => <option key={p} value={p}>{p.replace('_', ' ')}</option>)}
            </select>
          </div>
        </div>
        <div style={{ marginBottom: '0.75rem' }}>
          <label>{t('connectionConfigJson')}</label>
          <textarea value={typeof form.connection_config === 'string' ? form.connection_config : JSON.stringify(form.connection_config || {}, null, 2)} onChange={e => setForm({ ...form, connection_config: e.target.value })} rows={2} style={{ width: '100%', padding: 6, fontFamily: 'monospace' }} placeholder='{"ip":"192.168.1.100","port":554}' />
        </div>
        <div style={{ marginBottom: '0.75rem' }}>
          <label>{t('paramsJson')}</label>
          <textarea value={typeof form.params === 'string' ? form.params : JSON.stringify(form.params || {}, null, 2)} onChange={e => setForm({ ...form, params: e.target.value })} rows={2} style={{ width: '100%', padding: 6, fontFamily: 'monospace' }} placeholder='{"moving":true,"night_light":true,"resolution":"1080p","fps":30}' />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div>
            <label>{t('manufacturer')}</label>
            <input value={form.manufacturer} onChange={e => setForm({ ...form, manufacturer: e.target.value })} style={{ width: '100%', padding: 6 }} />
          </div>
          <div>
            <label>{t('model')}</label>
            <input value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} style={{ width: '100%', padding: 6 }} />
          </div>
        </div>

        {/* Parking zones (multi-select) */}
        <div style={{ marginBottom: '0.75rem' }}>
          <label style={{ display: 'block', marginBottom: 4 }}>אזורי חניה באזור המצלמה (ניתן לבחור מספר)</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {availableZones.length === 0 && <span style={{ color: '#888', fontSize: '0.85rem' }}>טוען אזורים...</span>}
            {availableZones.map(zone => (
              <label key={zone.id} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', background: form.selected_zone_ids.includes(zone.id) ? '#d4edda' : '#fff', border: '1px solid #ccc', borderRadius: 4, padding: '3px 8px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={form.selected_zone_ids.includes(zone.id)}
                  onChange={() => toggleZone(zone.id)}
                />
                {zone.name_he}
                {zone.description_he && <span style={{ color: '#888', fontSize: '0.78rem' }}> — {zone.description_he}</span>}
              </label>
            ))}
          </div>
          <p style={{ fontSize: '0.78rem', color: '#888', margin: '4px 0 0' }}>אם לא נבחר אזור — כל הכללים יבדקו (ברירת מחדל)</p>
        </div>

        {/* Violation rules (multi-select) */}
        <div style={{ marginBottom: '0.75rem' }}>
          <label style={{ display: 'block', marginBottom: 4 }}>כללי הפרה לבדיקה</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {availableRules.map(rule => (
              <label key={rule.id} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
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
          <p style={{ fontSize: '0.78rem', color: '#888', margin: '4px 0 0' }}>אם לא נבחר כלום — כל הכללים יבדקו (ברירת מחדל)</p>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} /> {t('active')}</label>
        </div>
        <div>
          <button type="submit" style={{ marginRight: 8 }}>{editing ? t('update') : t('add')}</button>
          {editing && <button type="button" onClick={() => { setEditing(null); setForm(EMPTY_FORM) }}>{t('cancel')}</button>}
        </div>
      </form>

      <h2>{t('configuredCameras')}</h2>
      {loading ? <p>{t('loading')}</p> : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {cameras.map(c => {
            const hasVideoDb = (c.connection_config as Record<string, unknown>)?.video_id
            const hasVideoFile = (c.connection_config as Record<string, unknown>)?.sample_video
            const hasSample = c.name === 'Sample Camera' || hasVideoDb || hasVideoFile
            const base = getApiBase().replace(/\/$/, '')
            const videoUrl = hasVideoDb ? `${base}/cameras/${c.id}/video` : `${base}/sample/video?t=${Date.now()}`
            const zoneIds = cameraZoneMap[c.id] || []
            const zoneNames = availableZones.filter(z => zoneIds.includes(z.id)).map(z => z.name_he)
            return (
              <li key={c.id} style={{ background: '#fff', border: '1px solid #ddd', borderRadius: 8, padding: '1rem', marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                  <div>
                    <strong>{c.name}</strong> — {c.connection_type} {c.location && `@ ${c.location}`}
                    {c.manufacturer && <span style={{ color: '#666', marginLeft: 8 }}>{c.manufacturer} {c.model}</span>}
                    {zoneNames.length > 0 && (
                      <div style={{ fontSize: '0.8rem', color: '#1a6b3a', marginTop: 2 }}>
                        אזורים: {zoneNames.join(', ')}
                      </div>
                    )}
                    {c.violation_rules && c.violation_rules.length > 0 && (
                      <div style={{ fontSize: '0.8rem', color: '#555', marginTop: 2 }}>
                        כללים: {c.violation_rules.join(', ')}
                      </div>
                    )}
                  </div>
                  <div>
                    {hasSample && (
                      <a href={videoUrl} target="_blank" rel="noreferrer" style={{ marginRight: 8 }}>{t('watchSample')}</a>
                    )}
                    <button onClick={() => startEdit(c)} style={{ marginRight: 8 }}>{t('edit')}</button>
                    <button onClick={() => remove(c.id)} style={{ background: '#dc3545', color: 'white' }}>{t('delete')}</button>
                  </div>
                </div>
                {hasSample && (
                  <video src={videoUrl} controls style={{ width: '100%', maxWidth: 400, marginTop: 8, borderRadius: 4 }} />
                )}
              </li>
            )
          })}
        </ul>
      )}
      {!loading && cameras.length === 0 && <p style={{ color: '#666' }}>{t('noCameras')}</p>}
    </div>
  )
}
