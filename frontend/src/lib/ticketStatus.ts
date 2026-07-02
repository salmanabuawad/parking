/** Shared ticket-status → badge class + Hebrew label map (Tickets, TicketReview, Inbox). */
export const TICKET_STATUS: Record<string, { cls: string; label: string }> = {
  pending_review: { cls: 'badge-warning', label: 'ממתין לבדיקה' },
  approved:       { cls: 'badge-success', label: 'אושר' },
  final:          { cls: 'badge-success', label: 'סופי' },
  rejected:       { cls: 'badge-danger',  label: 'נדחה' },
  paid:           { cls: 'badge-info',    label: 'שולם' },
  exempt:         { cls: 'badge-neutral', label: 'פטור' },
  duplicate:      { cls: 'badge-neutral', label: 'כפול' },
}

export function ticketStatusBadge(value: string): { cls: string; label: string } {
  return TICKET_STATUS[value] ?? { cls: 'badge-neutral', label: value }
}
