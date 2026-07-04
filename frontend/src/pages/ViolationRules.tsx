import { useState, useEffect } from 'react'
import { ShieldAlert } from 'lucide-react'
import { violationRulesApi } from '../api'
import { t } from '../i18n'

interface ViolationRule {
  id: number
  rule_id: string
  title_he: string
  title_en: string
  description_he?: string
  description_en?: string
  legal_basis_he?: string
  legal_basis_en?: string
  fine_ils?: number
  is_active: boolean
}

export default function ViolationRules() {
  const [rules, setRules] = useState<ViolationRule[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const [editFine, setEditFine] = useState<string>('')

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

  const toggleActive = async (rule: ViolationRule) => {
    setSaving(rule.rule_id)
    try {
      const { data } = await violationRulesApi.update(rule.rule_id, { is_active: !rule.is_active })
      setRules(prev => prev.map(r => r.rule_id === rule.rule_id ? data : r))
    } catch (err: unknown) {
      const ax = err as { message?: string }
      alert(ax.message)
    } finally {
      setSaving(null)
    }
  }

  const saveFine = async (rule: ViolationRule) => {
    const val = parseInt(editFine, 10)
    if (isNaN(val) || val < 0) { alert('סכום קנס לא תקין'); return }
    setSaving(rule.rule_id)
    try {
      const { data } = await violationRulesApi.update(rule.rule_id, { fine_ils: val })
      setRules(prev => prev.map(r => r.rule_id === rule.rule_id ? data : r))
      setEditing(null)
    } catch (err: unknown) {
      const ax = err as { message?: string }
      alert(ax.message)
    } finally {
      setSaving(null)
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
      </div>

      <p className="text-theme-text-muted">
        הפעל או השבת כללים לפי הצורך. כללים מושבתים לא ייבדקו בניתוח הוידאו.
        ניתן להגדיר לכל מצלמה אילו כללים פעילים עבורה בדף המצלמות.
      </p>

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
                  <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">מזהה</th>
                  <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">שם הכלל</th>
                  <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">בסיס חוקי</th>
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
                    <td className="px-3 py-2.5 align-top font-mono font-semibold text-theme-text-primary whitespace-nowrap">
                      {rule.rule_id}
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
                    <td className="px-3 py-2.5 align-top whitespace-nowrap">
                      {editing === rule.rule_id ? (
                        <span className="flex gap-1 items-center">
                          <div className="w-20">
                            <input
                              type="number"
                              value={editFine}
                              onChange={e => setEditFine(e.target.value)}
                              className="input-base"
                              min={0}
                            />
                          </div>
                          <button
                            onClick={() => saveFine(rule)}
                            disabled={saving === rule.rule_id}
                            className="inline-flex items-center px-2 py-1 rounded-md text-xs font-semibold bg-theme-accent text-white hover:bg-theme-accent-hover transition-colors disabled:opacity-50"
                          >✓</button>
                          <button
                            onClick={() => setEditing(null)}
                            className="inline-flex items-center px-2 py-1 rounded-md text-xs font-semibold text-theme-text-primary hover:bg-black/5 transition-colors"
                          >✕</button>
                        </span>
                      ) : (
                        <span
                          onClick={() => { setEditing(rule.rule_id); setEditFine(String(rule.fine_ils ?? '')) }}
                          className="cursor-pointer border-b border-dashed border-theme-card-border px-0.5"
                          title="לחץ לעריכה"
                        >
                          {rule.fine_ils != null ? `₪${rule.fine_ils}` : '—'}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 align-top text-center">
                      <label className="inline-flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={rule.is_active}
                          disabled={saving === rule.rule_id}
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
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
