import React, { useMemo, useRef, useState } from 'react';
import { he } from '../../i18n/he';

function formatMs(ms: number) {
  const totalSeconds = Math.floor(ms / 1000);
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const hh = String(h).padStart(2, '0');
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

export interface CapturePayload {
  blob: Blob;
  frameTimestampMs: number;
  videoTimestampLabel: string;
}

export function VideoPlayerPanel({
  videoUrl,
  videoStartedAt,
  onCapture,
}: {
  videoUrl: string;
  videoStartedAt?: string;
  onCapture: (payload: CapturePayload) => Promise<void> | void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [saving, setSaving] = useState(false);

  const startDate = useMemo(() => (videoStartedAt ? new Date(videoStartedAt) : null), [videoStartedAt]);

  const paintFrameWithTimestamp = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return null;

    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const frameTimestampMs = Math.floor(video.currentTime * 1000);
    const videoTimestampLabel = startDate
      ? new Date(startDate.getTime() + frameTimestampMs).toLocaleString('he-IL')
      : formatMs(frameTimestampMs);

    const label = `${he.app.sourceVideoTime}: ${videoTimestampLabel}`;
    ctx.font = 'bold 28px Arial';
    ctx.textAlign = 'right';
    const padding = 20;
    const textWidth = ctx.measureText(label).width;
    const boxWidth = textWidth + padding * 2;
    const boxHeight = 52;
    const x = canvas.width - 20;
    const y = canvas.height - 28;

    ctx.fillStyle = 'rgba(0,0,0,0.55)';
    ctx.fillRect(x - boxWidth, y - boxHeight + 10, boxWidth, boxHeight);
    ctx.fillStyle = '#ffffff';
    ctx.fillText(label, x - padding, y);

    return { frameTimestampMs, videoTimestampLabel };
  };

  const handleCapture = async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const meta = paintFrameWithTimestamp();
    if (!meta) return;
    setSaving(true);
    await new Promise<void>((resolve) => {
      canvas.toBlob(async (blob) => {
        if (blob) {
          await onCapture({ blob, ...meta });
        }
        resolve();
      }, 'image/jpeg', 0.92);
    });
    setSaving(false);
  };

  return (
    <section className="video-shell">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
        <div>
          <h2 style={{ marginBottom: 4 }}>{he.app.videoPanel}</h2>
          <div style={{ color: '#667085' }}>{he.app.smallerVideoHint}</div>
        </div>
      </div>
      <div className="video-stage">
        <video ref={videoRef} src={videoUrl} controls playsInline />
        <canvas ref={canvasRef} style={{ display: 'none' }} />
      </div>
      <div className="video-actions">
        <button onClick={handleCapture} disabled={saving}>
          {saving ? 'שומר...' : he.app.takeScreenshot}
        </button>
      </div>
    </section>
  );
}
