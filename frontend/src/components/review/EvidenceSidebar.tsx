import React from 'react';
import { he } from '../../i18n/he';
import type { TicketReviewData } from '../../types/ticket-review';
import { StatusBadge } from './StatusBadge';

function yn(v?: boolean) {
  if (v === true) return he.app.yes;
  if (v === false) return he.app.no;
  return he.app.unknown;
}

export function EvidenceSidebar({ ticket }: { ticket: TicketReviewData }) {
  return (
    <aside className="sidebar-shell">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>{he.app.evidencePanel}</h2>
        <StatusBadge status={ticket.status} />
      </div>

      <div className="info-grid">
        <section className="info-block">
          <h3>{he.app.plate}</h3>
          <div>{ticket.plateText || he.app.unknown}</div>
          {!!ticket.plateCandidates?.length && (
            <div style={{ marginTop: 8 }}>
              <strong>{he.app.candidates}:</strong> {ticket.plateCandidates.join(' / ')}
            </div>
          )}
        </section>

        <section className="info-block">
          <h3>{he.app.registry}</h3>
          <div className="meta-row"><span>נמצא במאגר</span><span>{yn(ticket.registry?.found)}</span></div>
          <div className="meta-row"><span>יצרן</span><span>{ticket.registry?.make || he.app.unknown}</span></div>
          <div className="meta-row"><span>דגם</span><span>{ticket.registry?.model || he.app.unknown}</span></div>
          <div className="meta-row"><span>צבע</span><span>{ticket.registry?.color || he.app.unknown}</span></div>
        </section>

        <section className="info-block">
          <h3>{he.app.vehicle}</h3>
          <div className="meta-row"><span>יצרן</span><span>{ticket.vehicle?.make || he.app.unknown}</span></div>
          <div className="meta-row"><span>דגם</span><span>{ticket.vehicle?.model || he.app.unknown}</span></div>
          <div className="meta-row"><span>צבע</span><span>{ticket.vehicle?.color || he.app.unknown}</span></div>
        </section>

        <section className="info-block">
          <h3>{he.app.parkingContext}</h3>
          <div className="meta-row"><span>{he.app.nearRedWhiteCurb}</span><span>{yn(ticket.parkingContext?.nearRedWhiteCurb)}</span></div>
          <div className="meta-row"><span>{he.app.onSidewalk}</span><span>{yn(ticket.parkingContext?.onSidewalk)}</span></div>
          <div className="meta-row"><span>{he.app.stationaryDuration}</span><span>{ticket.parkingContext?.stationaryDurationSeconds ?? he.app.unknown}</span></div>
          <div className="meta-row"><span>{he.app.trafficFlow}</span><span>{ticket.parkingContext?.trafficFlowState ? he.traffic[ticket.parkingContext.trafficFlowState] : he.app.unknown}</span></div>
        </section>

        <section className="info-block">
          <h3>החלטה</h3>
          <div>{ticket.reason || he.app.unknown}</div>
          <div style={{ marginTop: 8, color: '#667085' }}>{he.app.screenshotHint}</div>
        </section>
      </div>
    </aside>
  );
}
