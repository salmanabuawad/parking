
import { useMemo, useRef } from 'react'
import { he } from '../../i18n/he'
import { StatusBadge } from './StatusBadge'

export interface CaptureResult {
  imageBase64: string
  atIso: string
  currentVideoTimeSec: number
}

interface Props {
  videoUrl: string | null
  videoMode: 'processed' | 'raw'
  loading: boolean
  error: string | null
  status: string
  onRetry: () => void
  onCapture: (result: CaptureResult) => void
  metadataStartAt?: string | null
}

export function VideoPlayerPanel({
  videoUrl,
  videoMode,
  loading,
  error,
  status,
  onRetry,
  onCapture,
  metadataStartAt,
}: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null)

  const modeLabel = useMemo(
    () => (videoMode === 'processed' ? he.review.processed : he.review.fallbackRaw),
    [videoMode]
  )

  const captureScreenshot = () => {
    const video = videoRef.current
    if (!video) return

    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth || 1280
    canvas.height = video.videoHeight || 720

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

    const baseDate = metadataStartAt ? new Date(metadataStartAt) : new Date()
    const actualTime = new Date(baseDate.getTime() + video.currentTime * 1000)
    const stamp = actualTime.toLocaleString('he-IL', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })

    const pad = Math.max(18, Math.round(canvas.width * 0.012))
    ctx.fillStyle = 'rgba(0,0,0,0.56)'
    ctx.fillRect(pad, canvas.height - 68, 360, 44)
    ctx.fillStyle = '#ffffff'
    ctx.font = `${Math.max(18, Math.round(canvas.width * 0.018))}px monospace`
    ctx.fillText(stamp, pad + 14, canvas.height - 38)

    const imageBase64 = canvas.toDataURL('image/png')
    onCapture({
      imageBase64,
      atIso: actualTime.toISOString(),
      currentVideoTimeSec: video.currentTime,
    })
  }

  return (
    <div className="video-card">
      <div className="video-card-header">
        <div>
          <h2 style={{ margin: 0 }}>{he.review.blurredVideo}</h2>
          <div className="video-note">
            {videoMode === 'processed' ? he.review.blurredVideo : he.review.originalVideoFallback}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className="mode-pill">{modeLabel}</span>
          <StatusBadge status={status} />
        </div>
      </div>

      <div className="video-stage">
        {videoUrl ? (
          <video
            ref={videoRef}
            className="video-element"
            src={videoUrl}
            controls
            playsInline
            onError={() => undefined}
          />
        ) : error ? (
          <div className="video-note">{error}</div>
        ) : (
          <div className="video-note">{loading ? he.review.videoLoading : he.review.videoError}</div>
        )}
      </div>

      <div className="video-toolbar">
        <div className="btn-row">
          <button className="btn secondary" onClick={onRetry}>
            {he.review.retry}
          </button>
          <button className="btn primary" onClick={captureScreenshot} disabled={!videoUrl}>
            {he.review.captureScreenshot}
          </button>
        </div>
        {error ? <div className="video-note">{error}</div> : null}
      </div>
    </div>
  )
}
