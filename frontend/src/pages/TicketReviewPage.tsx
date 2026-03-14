import React from 'react';
import { CaseReviewLayout } from '../components/review/CaseReviewLayout';
import { useRtl } from '../hooks/useRtl';
import type { ScreenshotItem, TicketReviewData } from '../types/ticket-review';

const mockTicket: TicketReviewData = {
  id: '12345',
  status: 'not_100_percent_sure',
  plateText: '12345678',
  plateCandidates: ['12345678', '12345679'],
  videoUrl: '/videos/blurred-evidence.mp4',
  videoStartedAt: '2026-03-14T10:21:00+02:00',
  sourceVideoHash: 'sha256-demo',
  registry: { found: true, make: 'MAZDA', model: '3', color: 'WHITE', year: 2021 },
  vehicle: { make: 'MAZDA', model: '3', color: 'WHITE' },
  parkingContext: {
    nearRedWhiteCurb: true,
    onSidewalk: false,
    stationaryDurationSeconds: 43,
    trafficFlowState: 'flowing',
  },
  reason: 'המספר נמצא במאגר, אך נדרשת בדיקה אנושית נוספת לפני הפקת דוח.',
  screenshots: [],
};

async function saveScreenshot(formData: FormData): Promise<ScreenshotItem> {
  const res = await fetch('/api/tickets/screenshots', {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    throw new Error('Failed to save screenshot');
  }

  return res.json();
}

export default function TicketReviewPage() {
  useRtl('he');
  return <CaseReviewLayout ticket={mockTicket} onSaveScreenshot={saveScreenshot} />;
}
