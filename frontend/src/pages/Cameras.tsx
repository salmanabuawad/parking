import { useState, useEffect } from 'react'
import { camerasApi } from '../api'

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
}

export default function Cameras() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Camera | null>(null)
  const [form, setForm] = useState<CameraForm>({
    name: '', location: '', connection_type: 'ip',
    connection_config: {}, param_source: 'manual', params: {},
    manufacturer: '', model: '', is_active: true,
  })

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await camerasApi.list()
      setCameras(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const parseJson = (v: unknown): Record<string, unknown> => {
    if (typeof v === 'object' && v !== null) return v as Record<string, unknown>
    try { return (v ? JSON.parse(String(v)) : {}) as Record<string, unknown> } catch { return {} }
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const cfg = parseJson(form.connection_config)
      const params = parseJson(form.params)
      const payload = { ...form, connection_config: cfg, params }
      if (editing) {
        await camerasApi.update(editing.id, payload)
      } else {
        await camerasApi.create(payload)
      }
      setEditing(null)
      setForm({ name: '', location: '', connection_type: 'ip', connection_config: {}, param_source: 'manual', params: {}, manufacturer: '', model: '', is_active: true })
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
    })
  }

  const remove = async (id: number) => {
    if (!confirm('Remove this camera?')) return
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
      <h1>Cameras</h1>
      <p style={{ color: '#666', marginBottom: '1.5rem' }}>
        Define cameras manually or from manufacturer specs. Connect via IP, Bluetooth, WiFi, RTSP, USB, or other.
      </p>

      <form onSubmit={save} style={{ background: '#f5f5f5', padding: '1.25rem', borderRadius: 8, marginBottom: '1.5rem' }}>
        <h3>{editing ? 'Edit Camera' : 'Add Camera'}</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div>
            <label>Name *</label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required style={{ width: '100%', padding: 6 }} />
          </div>
          <div>
            <label>Location</label>
            <input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} style={{ width: '100%', padding: 6 }} placeholder="e.g. Main St & 5th" />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div>
            <label>Connection type</label>
            <select value={form.connection_type} onChange={e => setForm({ ...form, connection_type: e.target.value })} style={{ width: '100%', padding: 6 }}>
              {CONNECTION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label>Param source</label>
            <select value={form.param_source} onChange={e => setForm({ ...form, param_source: e.target.value })} style={{ width: '100%', padding: 6 }}>
              {PARAM_SOURCES.map(p => <option key={p} value={p}>{p.replace('_', ' ')}</option>)}
            </select>
          </div>
        </div>
        <div style={{ marginBottom: '0.75rem' }}>
          <label>Connection config (JSON)</label>
          <textarea value={typeof form.connection_config === 'string' ? form.connection_config : JSON.stringify(form.connection_config || {}, null, 2)} onChange={e => setForm({ ...form, connection_config: e.target.value })} rows={2} style={{ width: '100%', padding: 6, fontFamily: 'monospace' }} placeholder='{"ip":"192.168.1.100","port":554} or {"ssid":"MyWiFi","password":"..."} or {"address":"AA:BB:CC:DD:EE:FF"}' />
        </div>
        <div style={{ marginBottom: '0.75rem' }}>
          <label>Params (JSON) — e.g. moving, night_light, resolution, fps</label>
          <textarea value={typeof form.params === 'string' ? form.params : JSON.stringify(form.params || {}, null, 2)} onChange={e => setForm({ ...form, params: e.target.value })} rows={2} style={{ width: '100%', padding: 6, fontFamily: 'monospace' }} placeholder='{"moving":true,"night_light":true,"resolution":"1080p","fps":30}' />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div>
            <label>Manufacturer</label>
            <input value={form.manufacturer} onChange={e => setForm({ ...form, manufacturer: e.target.value })} style={{ width: '100%', padding: 6 }} />
          </div>
          <div>
            <label>Model</label>
            <input value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} style={{ width: '100%', padding: 6 }} />
          </div>
        </div>
        <div style={{ marginBottom: '1rem' }}>
          <label><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} /> Active</label>
        </div>
        <div>
          <button type="submit" style={{ marginRight: 8 }}>{editing ? 'Update' : 'Add'}</button>
          {editing && <button type="button" onClick={() => { setEditing(null); setForm({ name: '', location: '', connection_type: 'ip', connection_config: {}, param_source: 'manual', params: {}, manufacturer: '', model: '', is_active: true }) }}>Cancel</button>}
        </div>
      </form>

      <h2>Configured cameras</h2>
      {loading ? <p>Loading...</p> : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {cameras.map(c => {
            const hasVideoDb = (c.connection_config as Record<string, unknown>)?.video_id
            const hasVideoFile = (c.connection_config as Record<string, unknown>)?.sample_video
            const hasSample = c.name === 'Sample Camera' || hasVideoDb || hasVideoFile
            const videoUrl = hasVideoDb ? `/api/cameras/${c.id}/video` : `/api/sample/video?t=${Date.now()}`
            return (
              <li key={c.id} style={{ background: '#fff', border: '1px solid #ddd', borderRadius: 8, padding: '1rem', marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                  <div>
                    <strong>{c.name}</strong> — {c.connection_type} {c.location && `@ ${c.location}`}
                    {c.manufacturer && <span style={{ color: '#666', marginLeft: 8 }}>{c.manufacturer} {c.model}</span>}
                  </div>
                  <div>
                    {hasSample && (
                      <a href={videoUrl} target="_blank" rel="noreferrer" style={{ marginRight: 8 }}>Watch sample</a>
                    )}
                    <button onClick={() => startEdit(c)} style={{ marginRight: 8 }}>Edit</button>
                    <button onClick={() => remove(c.id)} style={{ background: '#dc3545', color: 'white' }}>Delete</button>
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
      {!loading && cameras.length === 0 && <p style={{ color: '#666' }}>No cameras configured. Add one above.</p>}
    </div>
  )
}
