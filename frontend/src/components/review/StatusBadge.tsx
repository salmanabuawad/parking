
import { he } from '../../i18n/he'

export function StatusBadge({ status }: { status: string }) {
  const key = status === 'approved' ? 'approved' : status === 'rejected' ? 'rejected' : 'pending'
  const label =
    status === 'approved'
      ? he.review.approved
      : status === 'rejected'
        ? he.review.rejected
        : he.review.pendingReview

  return <span className={`status-pill ${key}`}>{label}</span>
}
