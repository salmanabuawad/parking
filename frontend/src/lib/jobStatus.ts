/** Shared upload-job status → badge class + Hebrew label (Home, QueueMaintenance). */
export const JOB_STATUS: Record<string, { cls: string; label: string }> = {
  queued:     { cls: 'badge-warning', label: 'ממתין בתור' },
  processing: { cls: 'badge-info',    label: 'מעובד' },
  completed:  { cls: 'badge-success', label: 'הושלם' },
  failed:     { cls: 'badge-danger',  label: 'נכשל' },
}

export function jobStatusBadge(value: string): { cls: string; label: string } {
  return JOB_STATUS[value] ?? { cls: 'badge-neutral', label: value }
}
