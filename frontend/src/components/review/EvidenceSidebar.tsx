import { he } from '../../i18n/he'
import { StatusBadge } from './StatusBadge'
import type { TicketReviewRecord } from './types'

interface Props {
  ticket: TicketReviewRecord
  form: {
    license_plate: string
    location: string
    violation_zone: string
    description: string
    admin_notes: string
    fine_amount: string
  }
  onFormChange: (name: string, value: string) => void
  onSave: () => void
  onApprove: () => void
  onReject: () => void
  saving: boolean
}

export function EvidenceSidebar({ ticket, form, onFormChange, onSave, onApprove, onReject, saving }: Props) {
  return (
    <aside className="review-card sidebar-card">
      <div className="sidebar-header">
        <div>
          <h2 className="card-title">{he.review.details}</h2>
          <div className="subtle-line">{he.review.ticket} #{ticket.id}</div>
        </div>
        <StatusBadge status={ticket.status} />
      </div>

      <div className="field">
        <label>{he.review.plate}</label>
        <input value={form.license_plate} onChange={(e) => onFormChange('license_plate', e.target.value)} placeholder="12345678" />
      </div>

      {(form.license_plate === '11111' || !form.license_plate) && (
        <div className="warning-box">
          <strong>{he.review.plateReason}: </strong>
          {ticket.plate_detection_reason || 'לא תועדה סיבה מפורטת'}
        </div>
      )}

      <div className="field">
        <label>{he.review.location}</label>
        <input value={form.location} onChange={(e) => onFormChange('location', e.target.value)} />
      </div>

      <div className="field">
        <label>{he.review.violationZone}</label>
        <select value={form.violation_zone} onChange={(e) => onFormChange('violation_zone', e.target.value)}>
          <option value="red_white">{he.review.redWhite}</option>
          <option value="blue_white">{he.review.blueWhite}</option>
        </select>
      </div>

      <div className="field">
        <label>{he.review.description}</label>
        <textarea value={form.description} onChange={(e) => onFormChange('description', e.target.value)} />
      </div>

      <div className="field">
        <label>{he.review.adminNotes}</label>
        <textarea value={form.admin_notes} onChange={(e) => onFormChange('admin_notes', e.target.value)} />
      </div>

      <div className="field">
        <label>{he.review.fineAmount}</label>
        <input type="number" value={form.fine_amount} onChange={(e) => onFormChange('fine_amount', e.target.value)} />
      </div>

      {ticket.video_params && Object.keys(ticket.video_params).length > 0 && (
        <div className="meta-section">
          <h3 className="meta-title">{he.review.videoParams}</h3>
          <div className="meta-box">
            {Object.entries(ticket.video_params).map(([key, value]) => (
              <div className="meta-line" key={key}>
                <strong>{key}:</strong> {typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="btn-row">
        <button className="btn secondary" onClick={onSave} disabled={saving}>
          {saving ? he.review.saving : he.review.save}
        </button>
        {ticket.status === 'pending_review' && (
          <>
            <button className="btn success" onClick={onApprove} disabled={saving}>
              {he.review.approve}
            </button>
            <button className="btn danger" onClick={onReject} disabled={saving}>
              {he.review.reject}
            </button>
          </>
        )}
      </div>
    </aside>
  )
}
