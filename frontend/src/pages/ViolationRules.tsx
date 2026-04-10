import { useState, useEffect } from 'react'
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
    <div style={{ padding: '1.5rem', fontFamily: 'system-ui', maxWidth: 960, color: 'var(--app-text)' }}>
      <h1>כללי הפרת חניה / Violation Rules</h1>
      <p style={{ color: 'var(--app-text-muted)', marginBottom: '1.5rem' }}>
        הפעל או השבת כללים לפי הצורך. כללים מושבתים לא ייבדקו בניתוח הוידאו.
        ניתן להגדיר לכל מצלמה אילו כללים פעילים עבורה בדף המצלמות.
      </p>

      {loading ? <p>{t('loading')}</p> : (
        <>
          <p style={{ fontSize: '0.85rem', color: 'var(--app-text-muted)', marginBottom: '1rem' }}>
            {activeCount} מתוך {rules.length} כללים פעילים
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ background: 'var(--app-surface-muted)', textAlign: 'right' }}>
                <th style={thStyle}>מזהה</th>
                <th style={thStyle}>שם הכלל</th>
                <th style={thStyle}>בסיס חוקי</th>
                <th style={thStyle}>קנס (₪)</th>
                <th style={thStyle}>פעיל</th>
              </tr>
            </thead>
            <tbody>
              {rules.map(rule => (
                <tr key={rule.rule_id} style={{
                  borderBottom: '1px solid var(--app-border)',
                  opacity: rule.is_active ? 1 : 0.5,
                  background: rule.is_active ? 'var(--app-surface)' : 'var(--app-surface-muted)',
                }}>
                  <td style={{ ...tdStyle, fontFamily: 'monospace', fontWeight: 600, color: 'var(--app-text)', whiteSpace: 'nowrap' }}>
                    {rule.rule_id}
                  </td>
                  <td style={tdStyle}>
                    <div style={{ fontWeight: 500 }}>{rule.title_he}</div>
                    <div style={{ color: 'var(--app-text-muted)', fontSize: '0.8rem' }}>{rule.title_en}</div>
                    {rule.description_he && (
                      <div style={{ color: 'var(--app-text-muted)', fontSize: '0.78rem', marginTop: 2 }}>{rule.description_he}</div>
                    )}
                  </td>
                  <td style={{ ...tdStyle, fontSize: '0.8rem', color: 'var(--app-text-muted)', maxWidth: 200 }}>
                    {rule.legal_basis_he && <div>{rule.legal_basis_he}</div>}
                    {rule.legal_basis_en && <div style={{ color: 'var(--app-text-muted)' }}>{rule.legal_basis_en}</div>}
                  </td>
                  <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                    {editing === rule.rule_id ? (
                      <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                        <input
                          type="number"
                          value={editFine}
                          onChange={e => setEditFine(e.target.value)}
                          style={{ width: 70, padding: '2px 4px' }}
                          min={0}
                        />
                        <button
                          onClick={() => saveFine(rule)}
                          disabled={saving === rule.rule_id}
                          style={{ padding: '2px 8px', fontSize: '0.8rem' }}
                        >✓</button>
                        <button
                          onClick={() => setEditing(null)}
                          style={{ padding: '2px 6px', fontSize: '0.8rem' }}
                        >✕</button>
                      </span>
                    ) : (
                      <span
                        onClick={() => { setEditing(rule.rule_id); setEditFine(String(rule.fine_ils ?? '')) }}
                        style={{ cursor: 'pointer', borderBottom: '1px dashed var(--app-text-muted)', padding: '0 2px' }}
                        title="לחץ לעריכה"
                      >
                        {rule.fine_ils != null ? `₪${rule.fine_ils}` : '—'}
                      </span>
                    )}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={rule.is_active}
                        disabled={saving === rule.rule_id}
                        onChange={() => toggleActive(rule)}
                        style={{ width: 18, height: 18, cursor: 'pointer' }}
                      />
                      <span style={{ fontSize: '0.8rem', color: rule.is_active ? 'var(--app-success)' : 'var(--app-text-muted)' }}>
                        {rule.is_active ? 'פעיל' : 'כבוי'}
                      </span>
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}

const thStyle: React.CSSProperties = {
  padding: '8px 12px',
  borderBottom: '2px solid var(--app-border)',
  fontWeight: 600,
}

const tdStyle: React.CSSProperties = {
  padding: '10px 12px',
  verticalAlign: 'top',
}
