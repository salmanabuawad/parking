import React from 'react';
import { he } from '../../i18n/he';
import type { ScreenshotItem } from '../../types/ticket-review';

export function ScreenshotStrip({ items }: { items: ScreenshotItem[] }) {
  return (
    <section className="screenshot-strip">
      <h3>{he.app.screenshots}</h3>
      <div className="screenshot-list">
        {items.map((item) => (
          <article className="screenshot-card" key={item.id}>
            <img src={item.imageUrl} alt={item.videoTimestampLabel} />
            <div style={{ padding: 10 }}>
              <div><strong>{he.app.sourceVideoTime}:</strong> {item.videoTimestampLabel}</div>
              <div><strong>{he.app.capturedAt}:</strong> {item.capturedAt}</div>
              {item.note ? <div>{item.note}</div> : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
