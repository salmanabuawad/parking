import { useEffect, useState, type FormEvent } from 'react'
import { Users, Pencil, Trash2 } from 'lucide-react'
import { inspectorsApi } from '../api'
import { useRtl } from '../hooks/useRtl'

interface Inspector {
  id: number
  username: string
  full_name: string
  badge_number?: string | null
  phone?: string | null
  email?: string | null
  role: string
  is_active: boolean
}

const EMPTY = { username: '', password: '', full_name: '', badge_number: '', phone: '', email: '', role: 'inspector', is_active: true }

export default function Inspectors() {
  useRtl('פקחים | ניהול')
  const [list, setList] = useState<Inspector[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Inspector | null>(null)
  const [form, setForm] = useState<any>(EMPTY)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    inspectorsApi.list().then(setList).catch(() => setList([])).finally(() => setLoading(false))
  }
  useEffect(load, [])

  const startAdd = () => { setEditing(null); setForm(EMPTY); setError(null) }
  const startEdit = (i: Inspector) => { setEditing(i); setForm({ ...i, password: '' }); setError(null) }

  const save = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true); setError(null)
    try {
      if (editing) {
        const payload: any = {
          full_name: form.full_name, badge_number: form.badge_number, phone: form.phone,
          email: form.email, role: 'inspector', is_active: form.is_active,
        }
        if (form.password) payload.password = form.password
        await inspectorsApi.update(editing.id, payload)
      } else {
        await inspectorsApi.create({
          username: form.username, password: form.password, full_name: form.full_name,
          badge_number: form.badge_number, phone: form.phone, email: form.email,
          role: 'inspector', is_active: form.is_active,
        })
      }
      startAdd(); load()
    } catch (err: any) {
      setError(err?.message || 'שגיאה בשמירה')
    } finally { setSaving(false) }
  }

  const del = async (i: Inspector) => {
    if (!confirm(`למחוק את הפקח ${i.full_name}?`)) return
    await inspectorsApi.delete(i.id); load()
  }

  return (
    <div className="page-container">
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon"><Users className="w-5 h-5" strokeWidth={1.5} /></span>
        <h1 className="page-header-title">פקחים</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0 overflow-y-auto">
        {/* Form */}
        <div className="app-card p-4 space-y-3">
          <h2 className="font-semibold text-theme-text-primary">{editing ? `עריכת ${editing.full_name}` : 'פקח חדש'}</h2>
          <form onSubmit={save} className="space-y-3">
            {!editing && (
              <div>
                <label className="label-base">שם משתמש</label>
                <input className="input-base" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} required />
              </div>
            )}
            <div>
              <label className="label-base">שם מלא</label>
              <input className="input-base" value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} required />
            </div>
            <div>
              <label className="label-base">{editing ? 'סיסמה חדשה (ריק = ללא שינוי)' : 'סיסמה'}</label>
              <input className="input-base" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required={!editing} />
            </div>
            <div>
              <label className="label-base">מספר תג</label>
              <input className="input-base" value={form.badge_number || ''} onChange={e => setForm({ ...form, badge_number: e.target.value })} />
            </div>
            <div>
              <label className="label-base">טלפון</label>
              <input className="input-base" value={form.phone || ''} onChange={e => setForm({ ...form, phone: e.target.value })} />
            </div>
            <div>
              <label className="label-base">דוא"ל</label>
              <input className="input-base" value={form.email || ''} onChange={e => setForm({ ...form, email: e.target.value })} />
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
                  <th className="py-2">שם מלא</th><th>שם משתמש</th><th>תג</th><th>סטטוס</th><th></th>
                </tr>
              </thead>
              <tbody>
                {list.map(i => (
                  <tr key={i.id} className="border-b border-theme-card-border/50 text-right">
                    <td className="py-2 text-theme-text-primary">{i.full_name}</td>
                    <td>{i.username}</td>
                    <td>{i.badge_number || '—'}</td>
                    <td>{i.is_active ? <span className="badge badge-success">פעיל</span> : <span className="badge badge-neutral">לא פעיל</span>}</td>
                    <td className="text-left whitespace-nowrap">
                      <button onClick={() => startEdit(i)} className="btn-icon" title="עריכה"><Pencil className="w-4 h-4" /></button>
                      <button onClick={() => del(i)} className="btn-icon text-red-600" title="מחיקה"><Trash2 className="w-4 h-4" /></button>
                    </td>
                  </tr>
                ))}
                {list.length === 0 && <tr><td colSpan={5} className="text-center py-6 text-theme-text-muted">אין פקחים</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
