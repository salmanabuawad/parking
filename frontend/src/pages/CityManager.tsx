import { useEffect, useState, useCallback } from 'react'
import { Plus, Pencil, Trash2, ArrowUp, ArrowDown, MapPin, X } from 'lucide-react'
import { citiesApi, mapConfigApi, type City, type CityInput } from '../api'
import CityMapEditor, { type CityView } from './CityMapEditor'
import { useConfirm } from '../components/ConfirmDialog'

/** Admin manager for cities + their map areas. The row order is the order cities appear in every
 *  city dropdown (fleet dashboard, camera settings). Lives in the "ערים ומפות" settings tab. */
export default function CityManager() {
  const [cities, setCities] = useState<City[]>([])
  const [styleUrl, setStyleUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<City | 'new' | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const confirm = useConfirm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [cs, cfg] = await Promise.all([
        citiesApi.list(true),
        mapConfigApi.get().catch(() => ({ style_url: null as string | null })),
      ])
      setCities(cs)
      setStyleUrl((cfg as { style_url: string | null }).style_url || null)
    } finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])

  const move = async (idx: number, dir: -1 | 1) => {
    const j = idx + dir
    if (j < 0 || j >= cities.length) return
    const next = [...cities]
    ;[next[idx], next[j]] = [next[j], next[idx]]
    setCities(next)
    try { await citiesApi.reorder(next.map((c) => c.id)) } catch { load() }
  }

  const remove = async (c: City) => {
    if (!(await confirm({ message: `למחוק את העיר "${c.label}"? מצלמות המשויכות לעיר יישארו אך ללא שיוך.`, confirmText: 'מחק', danger: true }))) return
    setErr(null)
    try { await citiesApi.remove(c.id); load() }
    catch (e) { setErr((e as { message?: string })?.message || 'שגיאה במחיקת העיר') }
  }

  return (
    <div className="app-card p-5 space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <label className="label-base text-theme-text-primary font-semibold">ערים ומפות</label>
          <p className="text-theme-text-muted text-theme-sm">
            הוסף וערוך ערים. הסדר כאן קובע את סדר הערים בכל הרשימות (לוח המצלמות, הגדרת מצלמה).
          </p>
        </div>
        <button type="button" className="btn-primary" onClick={() => setEditing('new')}>
          <Plus className="w-4 h-4" /> הוסף עיר
        </button>
      </div>

      {err && (
        <div className="flex items-start gap-2 rounded-lg px-3 py-2 text-theme-sm border bg-red-50 text-red-700 border-red-200">
          <span className="flex-1">{err}</span>
          <button onClick={() => setErr(null)} className="shrink-0 opacity-60 hover:opacity-100 leading-none" title="סגור">✕</button>
        </div>
      )}

      {loading ? (
        <p className="text-theme-text-muted py-4">טוען…</p>
      ) : cities.length === 0 ? (
        <p className="text-theme-text-muted py-4">אין ערים עדיין. לחץ "הוסף עיר" כדי להתחיל.</p>
      ) : (
        <ul className="flex flex-col gap-2 max-w-2xl">
          {cities.map((c, i) => (
            <li key={c.id} className="flex items-center gap-2 rounded-lg border border-theme-card-border px-3 py-2">
              <span className="w-6 text-theme-text-muted text-theme-sm">{i + 1}.</span>
              <MapPin className="w-4 h-4 text-theme-accent shrink-0" />
              <span className="flex-1 text-theme-text-primary truncate">{c.label}</span>
              {!c.is_active && <span className="badge badge-neutral">מוסתרת</span>}
              <button type="button" className="btn-icon disabled:opacity-30" disabled={i === 0} onClick={() => move(i, -1)} title="העבר למעלה"><ArrowUp className="w-4 h-4" /></button>
              <button type="button" className="btn-icon disabled:opacity-30" disabled={i === cities.length - 1} onClick={() => move(i, 1)} title="העבר למטה"><ArrowDown className="w-4 h-4" /></button>
              <button type="button" className="btn-icon" onClick={() => setEditing(c)} title="ערוך"><Pencil className="w-4 h-4" /></button>
              <button type="button" className="btn-icon text-red-600" onClick={() => remove(c)} title="מחק"><Trash2 className="w-4 h-4" /></button>
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <CityEditorModal
          city={editing === 'new' ? null : editing}
          styleUrl={styleUrl}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load() }}
        />
      )}
    </div>
  )
}

function CityEditorModal({ city, styleUrl, onClose, onSaved }: {
  city: City | null
  styleUrl: string | null
  onClose: () => void
  onSaved: () => void
}) {
  const [label, setLabel] = useState(city?.label ?? '')
  const [isActive, setIsActive] = useState(city?.is_active ?? true)
  const [view, setView] = useState<CityView | null>(
    city ? { center_lat: city.center_lat, center_lng: city.center_lng, zoom: city.zoom, bounds: city.bounds ?? [[city.center_lng - 0.05, city.center_lat - 0.05], [city.center_lng + 0.05, city.center_lat + 0.05]] } : null
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const save = async () => {
    if (!label.trim()) { setError('יש להזין שם עיר'); return }
    if (!view) { setError('קבע מיקום על המפה'); return }
    setError(null)
    setSaving(true)
    try {
      const body: CityInput = {
        label: label.trim(),
        center_lat: view.center_lat,
        center_lng: view.center_lng,
        zoom: view.zoom,
        bounds: view.bounds,
        is_active: isActive,
      }
      if (city) await citiesApi.update(city.id, body)
      else await citiesApi.create(body)
      onSaved()
    } catch (e) {
      setError((e as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail || (e as { message?: string })?.message || 'שגיאה בשמירת העיר')
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 overflow-y-auto" onClick={onClose}>
      <div className="app-card w-full max-w-2xl my-6 flex flex-col overflow-hidden" dir="rtl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-theme-card-border">
          <h3 className="font-semibold text-theme-text-primary">{city ? 'עריכת עיר' : 'עיר חדשה'}</h3>
          <button type="button" className="btn-icon" onClick={onClose}><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          <div>
            <label className="label-base text-theme-text-primary">שם העיר</label>
            <input className="input-base" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="לדוגמה: נתניה" />
          </div>
          <div>
            <label className="label-base text-theme-text-primary">מיקום ואזור על המפה</label>
            <CityMapEditor
              initial={city ? { center_lat: city.center_lat, center_lng: city.center_lng, zoom: city.zoom } : null}
              styleUrl={styleUrl}
              onChange={setView}
            />
            <p className="text-theme-text-muted text-theme-xs mt-1">לחץ או גרור את הסמן לקביעת מרכז העיר. הזז והגדל את המפה — התצוגה הנוכחית נשמרת כאזור העיר.</p>
          </div>
          <label className="flex items-center gap-2 text-theme-text-primary">
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
            פעילה (מוצגת ברשימות)
          </label>
        </div>
        <div className="flex items-center gap-2 px-4 py-3 border-t border-theme-card-border">
          {error && <span className="flex-1 text-red-600 text-theme-sm">{error}</span>}
          <div className="flex justify-end gap-2 ms-auto">
            <button type="button" className="btn-cancel" onClick={onClose}>ביטול</button>
            <button type="button" className="btn-primary" onClick={save} disabled={saving}>{saving ? 'שומר…' : 'שמור'}</button>
          </div>
        </div>
      </div>
    </div>
  )
}
