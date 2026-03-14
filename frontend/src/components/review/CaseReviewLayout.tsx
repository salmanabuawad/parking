import React, { useState } from 'react';
import type { ScreenshotItem, TicketReviewData } from '../../types/ticket-review';
import { EvidenceSidebar } from './EvidenceSidebar';
import { ScreenshotStrip } from './ScreenshotStrip';
import { VideoPlayerPanel } from './VideoPlayerPanel';

export function CaseReviewLayout({
  ticket,
  onSaveScreenshot,
}: {
  ticket: TicketReviewData;
  onSaveScreenshot: (payload: FormData) => Promise<ScreenshotItem>;
}) {
  const [screenshots, setScreenshots] = useState<ScreenshotItem[]>(ticket.screenshots || []);

  return (
    <div className="ticket-review-page">
      <VideoPlayerPanel
        videoUrl={ticket.videoUrl}
        videoStartedAt={ticket.videoStartedAt}
        onCapture={async ({ blob, frameTimestampMs, videoTimestampLabel }) => {
          const form = new FormData();
          form.append('ticketId', String(ticket.id));
          form.append('frameTimestampMs', String(frameTimestampMs));
          form.append('videoTimestampLabel', videoTimestampLabel);
          form.append('sourceVideoHash', ticket.sourceVideoHash || '');
          form.append('file', blob, `ticket-${ticket.id}-${frameTimestampMs}.jpg`);
          const saved = await onSaveScreenshot(form);
          setScreenshots((prev) => [saved, ...prev]);
        }}
      />
      <EvidenceSidebar ticket={{ ...ticket, screenshots }} />
      <ScreenshotStrip items={screenshots} />
    </div>
  );
}
