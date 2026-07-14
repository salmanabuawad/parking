import { useState, useEffect } from 'react'
import { ShieldAlert, Plus, Pencil, Trash2, X } from 'lucide-react'
import { violationRulesApi } from '../api'
import { t } from '../i18n'

interface ViolationRule {
  id: number
  rule_id: string
  violation_code?: string
  title_he: string
  title_en: string
  description_he?: string
  description_en?: string
  legal_basis_he?: string
  legal_basis_en?: string
  fine_ils?: number
  default_min_stay_seconds?: number
  default_evidence_video_seconds?: number
  requires_start_image?: boolean
  requires_end_image?: boolean
  requires_clear_plate_image?: boolean
  requires_context_image?: boolean
  requires_continuous_video?: boolean
  is_active: boolean
}

type RuleForm = {
  rule_id: string
  violation_code: string
  title_he: string
  title_en: string
  description_he: string
  description_en: string
  legal_basis_he: string
  legal_basis_en: string
  fine_ils: string
  default_min_stay_seconds: string
  default_evidence_video_seconds: string
  requires_start_image: boolean
  requires_end_image: boolean
  requires_clear_plate_image: boolean
  requires_context_image: boolean
  requires_continuous_video: boolean
  is_active: boolean
}

const EMPTY_FORM: RuleForm = {
  rule_id: '', violation_code: '', title_he: '', title_en: '',
  description_he: '', description_en: '', legal_basis_he: '', legal_basis_en: '',
  fine_ils: '', default_min_stay_seconds: '30', default_evidence_video_seconds: '20',
  requires_start_image: true, requires_end_image: true, requires_clear_plate_image: true,
  requires_context_image: true, requires_continuous_video: true, is_active: true,
}

const REQUIREMENTS: { key: keyof RuleForm; label: string }[] = [
  { key: 'requires_start_image', label: 'תמונת התחלה' },
  { key: 'requires_end_image', label: 'תמונת סיום' },
  { key: 'requires_clear_plate_image', label: 'תמונת לוחית' },
  { key: 'requires_context_image', label: 'תמונת הקשר' },
  { key: 'requires_continuous_video', label: 'וידאו רציף' },
]

export default function ViolationRules() {
  const [rules, setRules] = useState<ViolationRule[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)   // null = create mode
  const [form, setForm] = useState<RuleForm>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [listErr, setListErr] = useState<string | null>(null)
  const [busyRow, setBusyRow] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await violationRulesApi.list()
      setRules(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const set = <K extends keyof RuleForm>(k: K, v: RuleForm[K]) => setForm(f => ({ ...f, [k]: v }))

  const openCreate = () => { setForm(EMPTY_FORM); setEditingId(null); setErr(null); setModalOpen(true) }
  const openEdit = (r: ViolationRule) => {
    setForm({
      rule_id: r.rule_id, violation_code: r.violation_code ?? '',
      title_he: r.title_he ?? '', title_en: r.title_en ?? '',
      description_he: r.description_he ?? '', description_en: r.description_en ?? '',
      legal_basis_he: r.legal_basis_he ?? '', legal_basis_en: r.legal_basis_en ?? '',
      fine_ils: r.fine_ils != null ? String(r.fine_ils) : '',
      default_min_stay_seconds: String(r.default_min_stay_seconds ?? 30),
      default_evidence_video_seconds: String(r.default_evidence_video_seconds ?? 20),
      requires_start_image: r.requires_start_image ?? true,
      requires_end_image: r.requires_end_image ?? true,
      requires_clear_plate_image: r.requires_clear_plate_image ?? true,
      requires_context_image: r.requires_context_image ?? true,
      requires_continuous_video: r.requires_continuous_video ?? true,
      is_active: r.is_active,
    })
    setEditingId(r.rule_id); setErr(null); setModalOpen(true)
  }

  const save = async () => {
    if (!form.rule_id.trim()) { setErr('נדרש מזהה כלל (למשל IL-STATIC-020)'); return }
    if (!form.title_he.trim() || !form.title_en.trim()) { setErr('נדרשת כותרת בעברית ובאנגלית'); return }
    const payload: Record<string, unknown> = {
      rule_id: form.rule_id.trim(),
      violation_code: form.violation_code.trim() || null,
      title_he: form.title_he.trim(), title_en: form.title_en.trim(),
      description_he: form.description_he.trim() || null,
      description_en: form.description_en.trim() || null,
      legal_basis_he: form.legal_basis_he.trim() || null,
      legal_basis_en: form.legal_basis_en.trim() || null,
      fine_ils: form.fine_ils.trim() === '' ? null : parseInt(form.fine_ils, 10),
      default_min_stay_seconds: parseInt(form.default_min_stay_seconds, 10) || 0,
      default_evidence_video_seconds: parseInt(form.default_evidence_video_seconds, 10) || 0,
      requires_start_image: form.requires_start_image,
      requires_end_image: form.requires_end_image,
      requires_clear_plate_image: form.requires_clear_plate_image,
      requires_context_image: form.requires_context_image,
      requires_continuous_video: form.requires_continuous_video,
      is_active: form.is_active,
    }
    setSaving(true); setErr(null)
    try {
      if (editingId) {
        const { rule_id: _rid, ...upd } = payload   // rule_id is the identity — not editable
        await violationRulesApi.update(editingId, upd)
      } else {
        await violationRulesApi.create(payload)
      }
      setModalOpen(false)
      await load()
    } catch (e: unknown) {
      setErr((e as { message?: string })?.message || 'שגיאה בשמירה')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (r: ViolationRule) => {
    if (!confirm(`למחוק את סוג העבירה "${r.title_he}" (${r.rule_id})?\nדוחות קיימים לא יושפעו (נשמר תצלום כלל בכל דוח).`)) return
    setBusyRow(r.rule_id)
    setListErr(null)
    try {
      await violationRulesApi.remove(r.rule_id)
      setRules(prev => prev.filter(x => x.rule_id !== r.rule_id))
    } catch (e: unknown) {
      setListErr((e as { message?: string })?.message || 'שגיאה במחיקת סוג העבירה')
    } finally {
      setBusyRow(null)
    }
  }

  const toggleActive = async (rule: ViolationRule) => {
    setBusyRow(rule.rule_id)
    setListErr(null)
    try {
      const { data } = await violationRulesApi.update(rule.rule_id, { is_active: !rule.is_active })
      setRules(prev => prev.map(r => r.rule_id === rule.rule_id ? data : r))
    } catch (e: unknown) {
      setListErr((e as { message?: string })?.message || 'שגיאה בעדכון סוג העבירה')
    } finally {
      setBusyRow(null)
    }
  }

  const activeCount = rules.filter(r => r.is_active).length

  return (
    <div className="page-container">
      {/* Page header */}
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon">
          <ShieldAlert className="w-5 h-5" strokeWidth={1.5} />
        </span>
        <h1 className="page-header-title">כללי הפרת חניה</h1>
        <button type="button" onClick={openCreate} className="btn-primary ms-auto">
          <Plus className="w-4 h-4" /> הוסף סוג עבירה
        </button>
      </div>

      <p className="text-theme-text-muted">
        הוסף, ערוך או מחק סוגי עבירה. כללים מושבתים לא ייבדקו בניתוח הוידאו.
        ניתן להגדיר לכל מצלמה אילו כללים פעילים עבורה בדף המצלמות.
      </p>

      {listErr && (
        <div className="flex items-start gap-2 rounded-lg px-3 py-2 text-theme-sm border bg-red-50 text-red-700 border-red-200">
          <span className="flex-1">{listErr}</span>
          <button onClick={() => setListErr(null)} className="shrink-0 opacity-60 hover:opacity-100 leading-none" title="סגור">✕</button>
        </div>
      )}

      {loading ? (
        <p className="text-theme-text-muted">{t('loading')}</p>
      ) : (
        <>
          <p className="text-theme-sm text-theme-text-muted">
            {activeCount} מתוך {rules.length} כללים פעילים
          </p>
          <div className="app-card p-4 overflow-x-auto">
            <table className="w-full border-collapse text-theme-sm">
              <thead>
                <tr className="text-right">
                  <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">פעולות</th>
                  <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">מזהה</th>
                  <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">קוד</th>
                  <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">שם הכלל</th>
                  <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">בסיס חוקי</th>
                  <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">דרישות ראיה</th>
                  <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">קנס (₪)</th>
                  <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">פעיל</th>
                </tr>
              </thead>
              <tbody>
                {rules.map(rule => (
                  <tr
                    key={rule.rule_id}
                    className={`border-b border-theme-card-border ${rule.is_active ? '' : 'opacity-50'}`}
                  >
                    <td className="px-3 py-2.5 align-top whitespace-nowrap">
                      <span className="flex gap-1">
                        <button
                          onClick={() => openEdit(rule)}
                          disabled={busyRow === rule.rule_id}
                          title="עריכה"
                          className="inline-flex items-center justify-center w-7 h-7 rounded-md text-theme-text-primary hover:bg-black/5 transition-colors disabled:opacity-50"
                        ><Pencil className="w-4 h-4" /></button>
                        <button
                          onClick={() => remove(rule)}
                          disabled={busyRow === rule.rule_id}
                          title="מחיקה"
                          className="inline-flex items-center justify-center w-7 h-7 rounded-md text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
                        ><Trash2 className="w-4 h-4" /></button>
                      </span>
                    </td>
                    <td className="px-3 py-2.5 align-top font-mono font-semibold text-theme-text-primary whitespace-nowrap">
                      {rule.rule_id}
                    </td>
                    <td className="px-3 py-2.5 align-top font-mono text-theme-xs text-theme-text-muted whitespace-nowrap">
                      {rule.violation_code || '—'}
                    </td>
                    <td className="px-3 py-2.5 align-top">
                      <div className="font-medium">{rule.title_he}</div>
                      <div className="text-theme-xs text-theme-text-muted">{rule.title_en}</div>
                      {rule.description_he && (
                        <div className="text-theme-xs text-theme-text-muted mt-0.5">{rule.description_he}</div>
                      )}
                    </td>
                    <td className="px-3 py-2.5 align-top text-theme-xs text-theme-text-muted max-w-[200px]">
                      {rule.legal_basis_he && <div>{rule.legal_basis_he}</div>}
                      {rule.legal_basis_en && <div className="text-theme-text-muted">{rule.legal_basis_en}</div>}
                    </td>
                    <td className="px-3 py-2.5 align-top text-theme-xs text-theme-text-muted">
                      <div className="flex flex-wrap gap-1">
                        {rule.requires_start_image && <span className="badge badge-neutral">התחלה</span>}
                        {rule.requires_end_image && <span className="badge badge-neutral">סיום</span>}
                        {rule.requires_clear_plate_image && <span className="badge badge-neutral">לוחית</span>}
                        {rule.requires_context_image && <span className="badge badge-neutral">הקשר</span>}
                        {rule.requires_continuous_video && <span className="badge badge-neutral">וידאו רציף</span>}
                      </div>
                      <div className="mt-1 whitespace-nowrap">שהייה {rule.default_min_stay_seconds ?? '—'}ש׳ · ראיה {rule.default_evidence_video_seconds ?? '—'}ש׳</div>
                    </td>
                    <td className="px-3 py-2.5 align-top whitespace-nowrap">
                      {rule.fine_ils != null ? `₪${rule.fine_ils}` : '—'}
                    </td>
                    <td className="px-3 py-2.5 align-top text-center">
                      <label className="inline-flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={rule.is_active}
                          disabled={busyRow === rule.rule_id}
                          onChange={() => toggleActive(rule)}
                          className="w-[18px] h-[18px] cursor-pointer"
                        />
                        <span className={`badge ${rule.is_active ? 'badge-success' : 'badge-neutral'}`}>
                          {rule.is_active ? 'פעיל' : 'כבוי'}
                        </span>
                      </label>
                    </td>
                  </tr>
                ))}
                {rules.length === 0 && (
                  <tr><td colSpan={8} className="px-3 py-6 text-center text-theme-text-muted">אין כללים. לחץ "הוסף סוג עבירה".</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Add / edit modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-start justify-center overflow-y-auto p-4" onClick={() => setModalOpen(false)}>
          <div className="app-card w-full max-w-2xl my-6 flex flex-col max-h-[90vh] overflow-hidden" dir="rtl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 px-5 py-3 border-b border-theme-card-border">
              <ShieldAlert className="w-5 h-5" strokeWidth={1.5} />
              <h2 className="font-semibold text-base">{editingId ? 'עריכת סוג עבירה' : 'סוג עבירה חדש'}</h2>
              <button onClick={() => setModalOpen(false)} className="ms-auto inline-flex items-center justify-center w-8 h-8 rounded-md hover:bg-black/5"><X className="w-4 h-4" /></button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4">
              {err && <div className="text-red-600 text-theme-sm">✗ {err}</div>}

              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="text-theme-xs font-semibold">מזהה כלל (rule_id) *</span>
                  <input className="input-base font-mono" value={form.rule_id} disabled={!!editingId}
                    placeholder="IL-STATIC-020" onChange={e => set('rule_id', e.target.value)} />
                  {editingId && <span className="text-theme-xs text-theme-text-muted">המזהה אינו ניתן לשינוי</span>}
                </label>
                <label className="block">
                  <span className="text-theme-xs font-semibold">קוד עבירה</span>
                  <input className="input-base font-mono" value={form.violation_code}
                    placeholder="NO_PARKING" onChange={e => set('violation_code', e.target.value)} />
                </label>
                <label className="block">
                  <span className="text-theme-xs font-semibold">שם בעברית *</span>
                  <input className="input-base" value={form.title_he} onChange={e => set('title_he', e.target.value)} />
                </label>
                <label className="block">
                  <span className="text-theme-xs font-semibold">שם באנגלית *</span>
                  <input className="input-base" value={form.title_en} onChange={e => set('title_en', e.target.value)} />
                </label>
                <label className="block col-span-2">
                  <span className="text-theme-xs font-semibold">תיאור (עברית)</span>
                  <input className="input-base" value={form.description_he} onChange={e => set('description_he', e.target.value)} />
                </label>
                <label className="block col-span-2">
                  <span className="text-theme-xs font-semibold">תיאור (אנגלית)</span>
                  <input className="input-base" value={form.description_en} onChange={e => set('description_en', e.target.value)} />
                </label>
                <label className="block">
                  <span className="text-theme-xs font-semibold">בסיס חוקי (עברית)</span>
                  <input className="input-base" value={form.legal_basis_he} onChange={e => set('legal_basis_he', e.target.value)} />
                </label>
                <label className="block">
                  <span className="text-theme-xs font-semibold">בסיס חוקי (אנגלית)</span>
                  <input className="input-base" value={form.legal_basis_en} onChange={e => set('legal_basis_en', e.target.value)} />
                </label>
                <label className="block">
                  <span className="text-theme-xs font-semibold">קנס (₪)</span>
                  <input type="number" min={0} className="input-base" value={form.fine_ils} onChange={e => set('fine_ils', e.target.value)} />
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block">
                    <span className="text-theme-xs font-semibold">שהייה מזערית (ש׳)</span>
                    <input type="number" min={0} className="input-base" value={form.default_min_stay_seconds} onChange={e => set('default_min_stay_seconds', e.target.value)} />
                  </label>
                  <label className="block">
                    <span className="text-theme-xs font-semibold">אורך ראיה (ש׳)</span>
                    <input type="number" min={0} className="input-base" value={form.default_evidence_video_seconds} onChange={e => set('default_evidence_video_seconds', e.target.value)} />
                  </label>
                </div>
              </div>

              <div>
                <span className="text-theme-xs font-semibold">דרישות ראיה לאישור</span>
                <div className="flex flex-wrap gap-2 mt-1">
                  {REQUIREMENTS.map(req => (
                    <label key={req.key} className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 cursor-pointer text-theme-xs ${form[req.key] ? 'bg-green-100 border-green-400' : 'border-theme-card-border'}`}>
                      <input type="checkbox" checked={form[req.key] as boolean} onChange={e => set(req.key, e.target.checked as never)} />
                      {req.label}
                    </label>
                  ))}
                </div>
              </div>

              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_active} onChange={e => set('is_active', e.target.checked)} className="w-[18px] h-[18px]" />
                <span className="text-theme-sm font-semibold">כלל פעיל</span>
              </label>
            </div>

            <div className="flex gap-2 px-5 py-3 border-t border-theme-card-border">
              <button onClick={save} disabled={saving} className="btn-success">{saving ? 'שומר…' : (editingId ? 'שמור שינויים' : 'צור כלל')}</button>
              <button onClick={() => setModalOpen(false)} className="btn-cancel">ביטול</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
