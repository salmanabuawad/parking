import { useEffect, useState, type FormEvent } from 'react'
import { ShieldCheck, Pencil, Trash2 } from 'lucide-react'
import { exemptionsApi } from '../api'
import { useRtl } from '../hooks/useRtl'

interface Exemption {
  id: number
  plate_number: string
  exemption_type: string
  valid_from?: string | null
  valid_until?: string | null
  notes?: string | null
  is_active: boolean
}

const TYPES: { value: string; label: string }[] = [
  { value: 'diplomat', label: 'דיפלומט' },
  { value: 'police', label: 'משטרה' },
  { value: 'resident', label: 'תושב' },
  { value: 'disabled', label: 'נכה' },
  { value: 'emergency', label: 'חירום' },
  { value: 'other', label: 'אחר' },
]
const typeLabel = (v: string) => TYPES.find(t => t.value === v)?.label ?? v
const toDateInput = (iso?: string | null): string => (iso ? iso.slice(0, 10) : '')

const EMPTY = { plate_number: '', exemption_type: 'resident', valid_from: '', valid_until: '', notes: '', is_active: true }

export default function Exemptions() {
  useRtl('פטורים | ניהול')
  const [list, setList] = useState<Exemption[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Exemption | null>(null)
  const [form, setForm] = useState<any>(EMPTY)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    exemptionsApi.list().then(setList).catch(() => setList([])).finally(() => setLoading(false))
  }
  useEffect(load, [])

  const startAdd = () => { setEditing(null); setForm(EMPTY); setError(null) }
  const startEdit = (x: Exemption) => {
    setEditing(x)
    setForm({ ...x, valid_from: toDateInput(x.valid_from), valid_until: toDateInput(x.valid_until), notes: x.notes || '' })
    setError(null)
  }

  const save = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true); setError(null)
    try {
      const payload: any = {
        plate_number: form.plate_number,
        exemption_type: form.exemption_type,
        valid_from: form.valid_from || null,
        valid_until: form.valid_until || null,
        notes: form.notes || null,
        is_active: form.is_active,
      }
      if (editing) await exemptionsApi.update(editing.id, payload)
      else await exemptionsApi.create(payload)
      startAdd(); load()
    } catch (err: any) {
      setError(err?.message || 'שגיאה בשמירה')
    } finally { setSaving(false) }
  }

  const del = async (x: Exemption) => {
    if (!confirm(`למחוק את הפטור לרכב ${x.plate_number}?`)) return
    await exemptionsApi.delete(x.id); load()
  }

  return (
    <div className="page-container">
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon"><ShieldCheck className="w-5 h-5" strokeWidth={1.5} /></span>
        <h1 className="page-header-title">פטורים (רשימת היתר)</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0 overflow-y-auto">
        {/* Form */}
        <div className="app-card p-4 space-y-3">
          <h2 className="font-semibold text-theme-text-primary">{editing ? `עריכת ${editing.plate_number}` : 'פטור חדש'}</h2>
          <form onSubmit={save} className="space-y-3">
            <div>
              <label className="label-base">מספר רכב</label>
              <input className="input-base font-mono tracking-widest" value={form.plate_number} onChange={e => setForm({ ...form, plate_number: e.target.value })} required />
            </div>
            <div>
              <label className="label-base">סוג פטור</label>
              <select className="input-base" value={form.exemption_type} onChange={e => setForm({ ...form, exemption_type: e.target.value })}>
                {TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="label-base">בתוקף מ־</label>
                <input type="date" className="input-base" value={form.valid_from} onChange={e => setForm({ ...form, valid_from: e.target.value })} />
              </div>
              <div className="flex-1">
                <label className="label-base">בתוקף עד</label>
                <input type="date" className="input-base" value={form.valid_until} onChange={e => setForm({ ...form, valid_until: e.target.value })} />
              </div>
            </div>
            <div>
              <label className="label-base">הערות</label>
              <textarea className="input-base min-h-[60px] resize-y" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
            </div>
            <label className="flex items-center gap-2 text-theme-sm text-theme-text-primary">
              <input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} /> פעיל
            </label>
            {error && <div className="text-red-600 text-theme-sm">{error}</div>}
            <div className="flex gap-2">
              <button type="submit" disabled={saving} className="btn-primary">{editing ? 'עדכן' : 'הוסף'}</button>
              {editing && <button type="button" onClick={startAdd} className="btn-secondary">ביטול</button>}
            </div>
          </form>
        </div>

        {/* List */}
        <div className="app-card p-4 lg:col-span-2 overflow-x-auto">
          {loading ? (
            <div className="text-theme-text-muted py-6 text-center">טוען...</div>
          ) : (
            <table className="w-full text-theme-sm">
              <thead>
                <tr className="text-theme-text-muted border-b border-theme-card-border text-right">
                  <th className="py-2">מספר רכב</th><th>סוג</th><th>תוקף</th><th>הערות</th><th>סטטוס</th><th></th>
                </tr>
              </thead>
              <tbody>
                {list.map(x => (
                  <tr key={x.id} className="border-b border-theme-card-border/50 text-right">
                    <td className="py-2 font-mono text-theme-text-primary">{x.plate_number}</td>
                    <td>{typeLabel(x.exemption_type)}</td>
                    <td className="whitespace-nowrap text-theme-xs">
                      {x.valid_from || x.valid_until
                        ? `${toDateInput(x.valid_from) || '—'} … ${toDateInput(x.valid_until) || '—'}`
                        : 'ללא הגבלה'}
                    </td>
                    <td className="max-w-[180px] truncate" title={x.notes || ''}>{x.notes || '—'}</td>
                    <td>{x.is_active ? <span className="badge badge-success">פעיל</span> : <span className="badge badge-neutral">לא פעיל</span>}</td>
                    <td className="text-left whitespace-nowrap">
                      <button onClick={() => startEdit(x)} className="btn-icon" title="עריכה"><Pencil className="w-4 h-4" /></button>
                      <button onClick={() => del(x)} className="btn-icon text-red-600" title="מחיקה"><Trash2 className="w-4 h-4" /></button>
                    </td>
                  </tr>
                ))}
                {list.length === 0 && <tr><td colSpan={6} className="text-center py-6 text-theme-text-muted">אין פטורים</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
