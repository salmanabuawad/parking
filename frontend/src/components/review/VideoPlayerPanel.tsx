import { useRef, useState } from 'react'
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
  onReprocess?: () => void
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
  onReprocess,
  onCapture,
  metadataStartAt,
}: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [capturing, setCapturing] = useState(false)
  const modeLabel = videoMode === 'processed' ? he.review.processed : he.review.fallbackRaw

  const captureScreenshot = () => {
    const video = videoRef.current
    if (!video) return
    setCapturing(true)
    try {
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

      const fontSize = Math.max(20, Math.round(canvas.width * 0.018))
      const padding = Math.max(18, Math.round(canvas.width * 0.012))
      const boxHeight = fontSize + 22
      const textWidth = Math.ceil(stamp.length * fontSize * 0.66)
      ctx.fillStyle = 'rgba(0,0,0,0.62)'
      ctx.fillRect(padding, canvas.height - boxHeight - padding, textWidth + 28, boxHeight)
      ctx.fillStyle = '#ffffff'
      ctx.font = `${fontSize}px monospace`
      ctx.textBaseline = 'middle'
      ctx.fillText(stamp, padding + 14, canvas.height - padding - boxHeight / 2)

      onCapture({
        imageBase64: canvas.toDataURL('image/png'),
        atIso: actualTime.toISOString(),
        currentVideoTimeSec: video.currentTime,
      })
    } finally {
      setCapturing(false)
    }
  }

  return (
    <section className="review-card video-card">
      <div className="video-card-header">
        <div>
          <h2 className="card-title">{he.review.blurredVideo}</h2>
          <div className="video-note">{videoMode === 'processed' ? he.review.processedPreferred : he.review.originalVideoFallback}</div>
        </div>
        <div className="video-header-right">
          <StatusBadge status={status} />
          <span className={`mode-pill ${videoMode}`}>{modeLabel}</span>
        </div>
      </div>

      <div className="video-shell">
        {videoUrl ? (
          <video
            ref={videoRef}
            className="review-video"
            controls
            playsInline
            preload="metadata"
            src={videoUrl}
          />
        ) : (
          <div className="video-placeholder">{loading ? he.review.videoLoading : error || he.review.videoError}</div>
        )}
      </div>

      <div className="video-actions">
        <button className="btn secondary" onClick={onRetry}>{he.review.retry}</button>
        {onReprocess ? <button className="btn secondary" onClick={onReprocess}>{he.review.reprocess}</button> : null}
        <button className="btn primary" onClick={captureScreenshot} disabled={!videoUrl || capturing}>
          {he.review.captureScreenshot}
        </button>
      </div>

      <div className="video-help">{he.review.captureHelp}</div>
      {error ? <div className="warning-box">{error}</div> : null}
    </section>
  )
}
