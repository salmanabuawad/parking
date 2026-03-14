import React from 'react';
import { he } from '../../i18n/he';
import type { ReviewStatus } from '../../types/ticket-review';

export function StatusBadge({ status }: { status: ReviewStatus }) {
  return (
    <span className={`status-badge status-${status}`}>
      {he.status[status]}
    </span>
  );
}
