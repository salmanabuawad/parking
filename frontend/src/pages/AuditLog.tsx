import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { History } from 'lucide-react'
import { auditApi } from '../api'

const ACTION_HE: Record<string, string> = {
  ticket_created: 'נוצר דוח',
  assign: 'שיוך',
  inspector_transfer: 'העברה',
  inspector_approve: 'אישור פקח',
  inspector_reject: 'דחיית פקח',
  inspector_update: 'עדכון פקח',
  admin_approved: 'אישור מנהל',
  admin_rejected: 'דחיית מנהל',
  registry_lookup: 'בדיקת מרשם',
  manual_review: 'נדרשת בדיקה ידנית',
}

interface AuditRow {
  id: number; ticket_id: number; action_type: string
  inspector_id?: number | null; inspector_name?: string | null
  old_value?: unknown; new_value?: unknown; notes?: string | null
  ip_address?: string | null; created_at?: string | null
}

/** Fleet-wide, immutable audit trail across all tickets (#12/#16). */
export default function AuditLog() {
  const [rows, setRows] = useState<AuditRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    auditApi.list({ limit: 300 }).then(setRows).catch(() => setRows([])).finally(() => setLoading(false))
  }, [])

  const fmt = (iso?: string | null) => (iso ? new Date(iso).toLocaleString('he-IL') : '—')
  const detail = (r: AuditRow) => {
    if (r.notes) return r.notes
    if (r.new_value) return JSON.stringify(r.new_value)
    return '—'
  }

  return (
    <div className="page-container">
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon"><History className="w-5 h-5" strokeWidth={1.5} /></span>
        <h1 className="page-header-title">יומן ביקורת</h1>
      </div>
      <p className="text-theme-text-muted text-theme-sm">כל הפעולות על דוחות — יומן בלתי ניתן לשינוי.</p>

      {loading ? (
        <p className="text-theme-text-muted">טוען…</p>
      ) : (
        <div className="app-card p-4 overflow-x-auto">
          <table className="w-full border-collapse text-theme-sm">
            <thead>
              <tr className="text-right">
                <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">זמן</th>
                <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">דוח</th>
                <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">פעולה</th>
                <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">מבצע</th>
                <th className="px-3 py-2 font-semibold border-b-2 border-theme-card-border">פרטים</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-theme-card-border">
                  <td className="px-3 py-2 whitespace-nowrap text-theme-xs text-theme-text-muted">{fmt(r.created_at)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <Link to={`/tickets/${r.ticket_id}`} className="text-theme-link font-semibold">#{r.ticket_id}</Link>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <span className="badge badge-neutral">{ACTION_HE[r.action_type] || r.action_type}</span>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-theme-xs">{r.inspector_name || (r.inspector_id ? `#${r.inspector_id}` : 'מנהל')}</td>
                  <td className="px-3 py-2 text-theme-xs text-theme-text-muted max-w-[360px] truncate" title={detail(r)}>{detail(r)}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={5} className="px-3 py-6 text-center text-theme-text-muted">אין רשומות</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
