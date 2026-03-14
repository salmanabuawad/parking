import { he } from '../../i18n/he'

function labelFor(status: string) {
  if (status === 'approved') return he.review.approved
  if (status === 'rejected') return he.review.rejected
  return he.review.pendingReview
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge status-${status}`}>{labelFor(status)}</span>
}
