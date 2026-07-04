import { useEffect, useState } from 'react'
import { Plus, Trash2, Pencil, X } from 'lucide-react'
import { cameraSegmentsApi } from '../api'

interface Segment {
  id: number
  label: string
  violation_rule_ids?: string[] | null
  display_order: number
  is_active: boolean
  coordinate_type?: string | null
  x1?: number | null; y1?: number | null; x2?: number | null; y2?: number | null
  min_stay_seconds?: number | null
  evidence_video_seconds?: number | null
  active_days?: string[] | null
  active_from_time?: string | null
  active_to_time?: string | null
  holiday_policy?: string | null
}
interface RuleOpt { id: string; label: string }

const DAYS = [
  { key: 'SUN', label: 'א' }, { key: 'MON', label: 'ב' }, { key: 'TUE', label: 'ג' },
  { key: 'WED', label: 'ד' }, { key: 'THU', label: 'ה' }, { key: 'FRI', label: 'ו' }, { key: 'SAT', label: 'ש' },
]
const HOLIDAY = [
  { value: '', label: '— ברירת מחדל —' },
  { value: 'enforce', label: 'אכיפה בחגים' },
  { value: 'skip', label: 'ללא אכיפה בחגים' },
]

const num = (v: string): number | null => { const n = Number(v); return v.trim() === '' || isNaN(n) ? null : n }
const str = (v?: number | null): string => (v == null ? '' : String(v))

export default function CameraSegmentsEditor({ cameraId, rules }: { cameraId: number; rules: RuleOpt[] }) {
  const [segments, setSegments] = useState<Segment[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  // form
  const [label, setLabel] = useState('')
  const [selRules, setSelRules] = useState<string[]>([])
  const [coordType, setCoordType] = useState('pixels')
  const [x1, setX1] = useState(''); const [y1, setY1] = useState(''); const [x2, setX2] = useState(''); const [y2, setY2] = useState('')
  const [minStay, setMinStay] = useState(''); const [evVideo, setEvVideo] = useState('')
  const [days, setDays] = useState<string[]>([])
  const [fromTime, setFromTime] = useState(''); const [toTime, setToTime] = useState('')
  const [holiday, setHoliday] = useState('')

  const load = () => {
    setLoading(true)
    cameraSegmentsApi.list(cameraId).then(setSegments).catch(() => setSegments([])).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [cameraId])

  const reset = () => {
    setEditingId(null); setLabel(''); setSelRules([]); setCoordType('pixels')
    setX1(''); setY1(''); setX2(''); setY2(''); setMinStay(''); setEvVideo('')
    setDays([]); setFromTime(''); setToTime(''); setHoliday('')
  }
  const startEdit = (s: Segment) => {
    setEditingId(s.id); setLabel(s.label); setSelRules(s.violation_rule_ids || [])
    setCoordType(s.coordinate_type || 'pixels')
    setX1(str(s.x1)); setY1(str(s.y1)); setX2(str(s.x2)); setY2(str(s.y2))
    setMinStay(str(s.min_stay_seconds)); setEvVideo(str(s.evidence_video_seconds))
    setDays(s.active_days || []); setFromTime(s.active_from_time || ''); setToTime(s.active_to_time || '')
    setHoliday(s.holiday_policy || '')
  }

  const payload = () => ({
    label: label.trim(),
    violation_rule_ids: selRules,
    coordinate_type: coordType,
    x1: num(x1), y1: num(y1), x2: num(x2), y2: num(y2),
    min_stay_seconds: num(minStay), evidence_video_seconds: num(evVideo),
    active_days: days.length ? days : null,
    active_from_time: fromTime || null, active_to_time: toTime || null,
    holiday_policy: holiday || null,
  })

  const save = async () => {
    if (!label.trim()) return
    setSaving(true)
    try {
      if (editingId) await cameraSegmentsApi.update(cameraId, editingId, payload())
      else await cameraSegmentsApi.create(cameraId, { ...payload(), display_order: segments.length })
      reset(); load()
    } finally { setSaving(false) }
  }
  const del = async (id: number) => { await cameraSegmentsApi.delete(cameraId, id); if (editingId === id) reset(); load() }
  const toggleRule = (rid: string) => setSelRules(s => (s.includes(rid) ? s.filter(x => x !== rid) : [...s, rid]))
  const toggleDay = (d: string) => setDays(s => (s.includes(d) ? s.filter(x => x !== d) : [...s, d]))

  const summary = (s: Segment): string => {
    const parts: string[] = []
    if (s.active_from_time || s.active_to_time) parts.push(`${s.active_from_time || '00:00'}–${s.active_to_time || '24:00'}`)
    if (s.active_days && s.active_days.length) parts.push(s.active_days.map(d => DAYS.find(x => x.key === d)?.label || d).join(''))
    if (s.min_stay_seconds != null) parts.push(`שהייה ${s.min_stay_seconds}ש׳`)
    return parts.join(' · ')
  }

  return (
    <div className="mt-3 border-t border-theme-card-border pt-3">
      <div className="text-theme-sm font-semibold mb-2">מקטעים ({segments.length})</div>

      {loading ? (
        <div className="text-theme-text-muted text-theme-sm">טוען...</div>
      ) : (
        <div className="flex flex-col gap-1.5 mb-2">
          {segments.map(s => (
            <div key={s.id} className="flex items-center justify-between gap-2 bg-black/5 rounded px-2 py-1">
              <div className="text-theme-sm min-w-0">
                <strong>{s.label}</strong>
                {s.violation_rule_ids && s.violation_rule_ids.length > 0 && (
                  <span className="text-theme-xs text-theme-text-muted"> — {s.violation_rule_ids.join(', ')}</span>
                )}
                {summary(s) && <span className="text-theme-xs text-theme-text-muted block">{summary(s)}</span>}
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button onClick={() => startEdit(s)} className="btn-icon" title="ערוך מקטע"><Pencil className="w-4 h-4" /></button>
                <button onClick={() => del(s.id)} className="btn-icon text-red-600" title="מחק מקטע"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
          {segments.length === 0 && <div className="text-theme-text-muted text-theme-sm">אין מקטעים</div>}
        </div>
      )}

      {/* Add / edit a segment */}
      <div className="flex flex-col gap-2 bg-black/5 rounded p-2">
        <div className="flex items-center justify-between">
          <span className="text-theme-xs font-semibold text-theme-text-muted">{editingId ? 'עריכת מקטע' : 'מקטע חדש'}</span>
          {editingId && <button onClick={reset} className="btn-icon" title="בטל עריכה"><X className="w-4 h-4" /></button>}
        </div>
        <input className="input-base" placeholder="מלל ליד המקטע" value={label} onChange={e => setLabel(e.target.value)} />

        {/* Violation types */}
        <div className="flex flex-wrap gap-1.5">
          {rules.map(r => (
            <label key={r.id} className={`text-theme-xs rounded border px-2 py-0.5 cursor-pointer ${selRules.includes(r.id) ? 'bg-green-100 border-green-300' : 'border-theme-card-border'}`}>
              <input type="checkbox" className="me-1" checked={selRules.includes(r.id)} onChange={() => toggleRule(r.id)} />
              {r.label || r.id}
            </label>
          ))}
        </div>

        {/* Geometry */}
        <label className="text-theme-xs text-theme-text-muted">סוג קואורדינטות
          <select className="input-base" value={coordType} onChange={e => setCoordType(e.target.value)}>
            <option value="pixels">פיקסלים</option>
            <option value="normalized">מנורמל (0–1)</option>
            <option value="polygon">מצולע</option>
          </select>
        </label>
        {coordType !== 'polygon' && (
          <div className="grid grid-cols-4 gap-2">
            {(['x1', 'y1', 'x2', 'y2'] as const).map((k) => {
              const val = { x1, y1, x2, y2 }[k]
              const set = { x1: setX1, y1: setY1, x2: setX2, y2: setY2 }[k]
              return (
                <label key={k} className="text-theme-xs text-theme-text-muted">{k.toUpperCase()}
                  <input type="number" step="any" className="input-base" value={val} onChange={e => set(e.target.value)} />
                </label>
              )
            })}
          </div>
        )}

        {/* Per-segment overrides + schedule */}
        <div className="grid grid-cols-2 gap-2">
          <label className="text-theme-xs text-theme-text-muted">זמן שהייה לעבירה (ש׳)
            <input type="number" className="input-base" value={minStay} onChange={e => setMinStay(e.target.value)} />
          </label>
          <label className="text-theme-xs text-theme-text-muted">אורך סרטון ראיה (ש׳)
            <input type="number" className="input-base" value={evVideo} onChange={e => setEvVideo(e.target.value)} />
          </label>
          <label className="text-theme-xs text-theme-text-muted">שעת התחלה
            <input type="time" className="input-base" value={fromTime} onChange={e => setFromTime(e.target.value)} />
          </label>
          <label className="text-theme-xs text-theme-text-muted">שעת סיום
            <input type="time" className="input-base" value={toTime} onChange={e => setToTime(e.target.value)} />
          </label>
        </div>

        {/* Active days */}
        <div>
          <div className="text-theme-xs text-theme-text-muted mb-1">ימי פעילות</div>
          <div className="flex gap-1">
            {DAYS.map(d => (
              <button key={d.key} type="button" onClick={() => toggleDay(d.key)}
                className={`w-7 h-7 rounded-full text-theme-xs ${days.includes(d.key) ? 'bg-theme-accent text-white' : 'bg-white border border-theme-card-border'}`}>
                {d.label}
              </button>
            ))}
          </div>
        </div>

        {/* Holiday policy */}
        <label className="text-theme-xs text-theme-text-muted">מדיניות חגים
          <select className="input-base" value={holiday} onChange={e => setHoliday(e.target.value)}>
            {HOLIDAY.map(h => <option key={h.value} value={h.value}>{h.label}</option>)}
          </select>
        </label>

        <button type="button" onClick={save} disabled={!label.trim() || saving} className="btn-secondary self-start">
          {editingId ? <><Pencil className="w-4 h-4" /> עדכן מקטע</> : <><Plus className="w-4 h-4" /> הוסף מקטע</>}
        </button>
      </div>
    </div>
  )
}
