
import { he } from '../../i18n/he'
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

export function EvidenceSidebar({
  ticket,
  form,
  onFormChange,
  onSave,
  onApprove,
  onReject,
  saving,
}: Props) {
  return (
    <div className="sidebar-card">
      <div className="sidebar-card-header">
        <div>
          <h2 style={{ margin: 0 }}>{he.review.details}</h2>
          <div className="video-note">
            {he.review.ticket} #{ticket.id}
          </div>
        </div>
      </div>

      <div className="form-grid">
        <div className="field">
          <label>{he.review.plate}</label>
          <input
            value={form.license_plate}
            onChange={(e) => onFormChange('license_plate', e.target.value)}
            placeholder="12345678"
          />
        </div>

        {form.license_plate === '11111' || !form.license_plate ? (
          <div className="callout">
            <strong>{he.review.plateReason}: </strong>
            {ticket.plate_detection_reason || 'לא תועדה סיבה מפורטת'}
          </div>
        ) : null}

        <div className="field">
          <label>{he.review.location}</label>
          <input value={form.location} onChange={(e) => onFormChange('location', e.target.value)} />
        </div>

        <div className="field">
          <label>{he.review.violationZone}</label>
          <select
            value={form.violation_zone}
            onChange={(e) => onFormChange('violation_zone', e.target.value)}
          >
            <option value="red_white">{he.review.redWhite}</option>
            <option value="blue_white">{he.review.blueWhite}</option>
          </select>
        </div>

        <div className="field">
          <label>{he.review.description}</label>
          <textarea
            value={form.description}
            onChange={(e) => onFormChange('description', e.target.value)}
          />
        </div>

        <div className="field">
          <label>{he.review.adminNotes}</label>
          <textarea
            value={form.admin_notes}
            onChange={(e) => onFormChange('admin_notes', e.target.value)}
          />
        </div>

        <div className="field">
          <label>{he.review.fineAmount}</label>
          <input
            type="number"
            value={form.fine_amount}
            onChange={(e) => onFormChange('fine_amount', e.target.value)}
          />
        </div>

        {ticket.video_params && Object.keys(ticket.video_params).length > 0 ? (
          <div>
            <h3 style={{ marginBottom: 8 }}>{he.review.videoParams}</h3>
            <div className="meta-box">
              {Object.entries(ticket.video_params).map(([key, value]) => (
                <div className="meta-line" key={key}>
                  <strong>{key}:</strong>{' '}
                  {typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="btn-row" style={{ marginTop: 6 }}>
          <button className="btn secondary" onClick={onSave} disabled={saving}>
            {saving ? he.review.saving : he.review.save}
          </button>
          {ticket.status === 'pending_review' ? (
            <>
              <button className="btn success" onClick={onApprove} disabled={saving}>
                {he.review.approve}
              </button>
              <button className="btn danger" onClick={onReject} disabled={saving}>
                {he.review.reject}
              </button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}
