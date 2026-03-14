import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ticketsApi } from '../api'
import { he } from '../i18n/he'
import { t } from '../i18n'
import { useRtl } from '../hooks/useRtl'
import '../styles/review.css'
import type { TicketReviewRecord } from '../components/review/types'
import { EvidenceSidebar } from '../components/review/EvidenceSidebar'
import { ScreenshotStrip, type SavedScreenshot } from '../components/review/ScreenshotStrip'
import { VideoPlayerPanel, type CaptureResult } from '../components/review/VideoPlayerPanel'

interface TicketForm {
  license_plate: string
  location: string
  violation_zone: string
  description: string
  admin_notes: string
  fine_amount: string
}

function pickMetadataStartAt(ticket: TicketReviewRecord | null): string | null {
  const params = ticket?.video_params || {}
  const nestedMetadata = typeof params['metadata'] === 'object' && params['metadata'] !== null
    ? (params['metadata'] as Record<string, unknown>)
    : {}
  const candidates = [
    params['capture_time'],
    params['creation_time'],
    params['video_start_time'],
    params['recorded_at'],
    ticket?.captured_at,
    ticket?.created_at,
    nestedMetadata['creation_time'],
  ]
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) return candidate
  }
  return null
}

export default function TicketReview() {
  useRtl(`${he.review.ticket} | ${he.app.title}`)

  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [ticket, setTicket] = useState<TicketReviewRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [videoError, setVideoError] = useState<string | null>(null)
  const [videoBlobUrl, setVideoBlobUrl] = useState<string | null>(null)
  const [videoMode, setVideoMode] = useState<'processed' | 'raw'>('processed')
  const [videoRetryKey, setVideoRetryKey] = useState(0)
  const [shots, setShots] = useState<SavedScreenshot[]>([])

  const [form, setForm] = useState<TicketForm>({
    license_plate: '',
    location: '',
    violation_zone: 'red_white',
    description: '',
    admin_notes: '',
    fine_amount: '',
  })

  const currentBlobUrl = useRef<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    ticketsApi
      .get(id)
      .then(({ data }) => {
        setTicket(data)
        setForm({
          license_plate: (data.license_plate as string) || '',
          location: (data.location as string) || '',
          violation_zone: (data.violation_zone as string) || 'red_white',
          description: (data.description as string) || '',
          admin_notes: (data.admin_notes as string) || '',
          fine_amount: data.fine_amount ? String(data.fine_amount) : '',
        })
      })
      .catch(() => setTicket(null))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!id || (!ticket?.video_id && !ticket?.video_path)) {
      setVideoBlobUrl(null)
      setVideoError(null)
      return
    }

    let cancelled = false
    let localUrl: string | null = null

    const isVideoBlob = (b: Blob) => b.size > 100 && b.type !== 'application/json'

    const replaceBlobUrl = (blob: Blob, mode: 'processed' | 'raw', error: string | null = null) => {
      localUrl = URL.createObjectURL(blob)
      if (currentBlobUrl.current) URL.revokeObjectURL(currentBlobUrl.current)
      currentBlobUrl.current = localUrl
      setVideoBlobUrl(localUrl)
      setVideoMode(mode)
      setVideoError(error)
    }

    const setErrorFromResponse = (err: any) => {
      const status = err?.response?.status
      if (status === 401) setVideoError(he.review.videoErrorAuth)
      else setVideoError(he.review.videoError)
    }

    const load = async () => {
      setVideoError(null)
      try {
        const processed = await ticketsApi.getProcessedVideo(id, videoRetryKey || Date.now())
        if (cancelled) return
        const processedBlob = processed.data instanceof Blob ? processed.data : new Blob([processed.data], { type: 'video/mp4' })
        if (isVideoBlob(processedBlob)) {
          replaceBlobUrl(processedBlob, 'processed')
          return
        }
      } catch {
        // Continue to fallback below.
      }

      try {
        const blurred = await ticketsApi.getVideo(id, videoRetryKey || Date.now())
        if (cancelled) return
        const blurredBlob = blurred.data instanceof Blob ? blurred.data : new Blob([blurred.data], { type: 'video/mp4' })
        if (isVideoBlob(blurredBlob)) {
          replaceBlobUrl(blurredBlob, 'processed')
          return
        }
      } catch {
        // Continue to raw fallback below.
      }

      try {
        const raw = await ticketsApi.getRawVideo(id, videoRetryKey || Date.now())
        if (cancelled) return
        const rawBlob = raw.data instanceof Blob ? raw.data : new Blob([raw.data], { type: 'video/mp4' })
        if (!isVideoBlob(rawBlob)) {
          setVideoError(he.review.videoError)
          return
        }
        replaceBlobUrl(rawBlob, 'raw', he.review.originalVideoFallback)
      } catch (err: any) {
        if (!cancelled) setErrorFromResponse(err)
      }
    }

    load()

    return () => {
      cancelled = true
      if (localUrl) URL.revokeObjectURL(localUrl)
      setVideoBlobUrl(null)
    }
  }, [id, ticket?.video_id, ticket?.video_path, videoRetryKey])

  useEffect(() => {
    if (!id) return
    ticketsApi
      .listScreenshots(id)
      .then(({ data }) => {
        if (!Array.isArray(data)) return
        setShots(
          data.map((item: any) => ({
            id: item.id,
            url: `tickets/${id}/screenshots/${item.id}/image`,
            takenAtIso: item.captured_at || item.taken_at_iso || new Date().toISOString(),
            currentVideoTimeSec: Number(item.frame_time_sec || 0),
            persisted: true,
          }))
        )
      })
      .catch(() => {
        // no-op; strip will stay empty
      })
  }, [id])

  const metadataStartAt = useMemo(() => pickMetadataStartAt(ticket), [ticket])

  const onFormChange = (name: string, value: string) => {
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  const save = async (status?: 'approved' | 'rejected') => {
    if (!id) return
    setSaving(true)
    try {
      const payload = {
        license_plate: form.license_plate,
        location: form.location || null,
        violation_zone: form.violation_zone,
        description: form.description || null,
        admin_notes: form.admin_notes || null,
        fine_amount: form.fine_amount ? parseInt(form.fine_amount, 10) : null,
        ...(status ? { status } : {}),
      }
      const { data } = await ticketsApi.update(id, payload)
      setTicket(data)
      if (status) navigate('/tickets')
    } catch (e) {
      const axErr = e as { response?: { data?: { detail?: string } } }
      alert(axErr?.response?.data?.detail || t('updateFailed'))
    } finally {
      setSaving(false)
    }
  }

  const handleCapture = async (capture: CaptureResult) => {
    if (!id) return
    const localShot: SavedScreenshot = {
      id: crypto.randomUUID(),
      url: capture.imageBase64,
      takenAtIso: capture.atIso,
      currentVideoTimeSec: capture.currentVideoTimeSec,
      persisted: false,
    }
    setShots((prev) => [localShot, ...prev])

    try {
      const { data } = await ticketsApi.saveScreenshot(id, {
        image_base64: capture.imageBase64,
        frame_time_sec: capture.currentVideoTimeSec,
        captured_at: capture.atIso,
      })
      const savedId = data.id ?? localShot.id
      setShots((prev) =>
        prev.map((item) =>
          item.id === localShot.id
            ? {
                ...item,
                id: savedId,
                url: typeof savedId !== 'undefined' ? `tickets/${id}/screenshots/${savedId}/image` : item.url,
                persisted: true,
              }
            : item
        )
      )
    } catch {
      // keep local-only preview; persistence failed
    }
  }

  const requestReprocess = async () => {
    if (!id) return
    try {
      await ticketsApi.reprocessVideo(id)
      setVideoRetryKey((v) => v + 1)
    } catch {
      // no-op; retry button still available
    }
  }

  if (loading) return <div className="review-page">{he.app.loading}</div>
  if (!ticket) return <div className="review-page">{he.review.notFound}</div>

  return (
    <div className="review-page">
      <div className="review-topbar">
        <div>
          <Link className="review-back" to="/tickets">
            ← {he.review.back}
          </Link>
          <h1 className="review-title">
            {he.review.ticket} #{ticket.id} — {form.license_plate && form.license_plate !== '11111' ? form.license_plate : he.review.plateNotIdentified}
          </h1>
          <div className="review-subtitle">
            {he.review.createdAt}: {ticket.created_at ? new Date(ticket.created_at).toLocaleString('he-IL') : '—'}
          </div>
        </div>
      </div>

      <div className="review-layout">
        <VideoPlayerPanel
          videoUrl={videoBlobUrl}
          videoMode={videoMode}
          loading={false}
          error={videoError}
          status={ticket.status}
          metadataStartAt={metadataStartAt}
          onRetry={() => setVideoRetryKey((v) => v + 1)}
          onReprocess={requestReprocess}
          onCapture={handleCapture}
          onVideoLoadError={() => {
            setVideoError(he.review.videoError)
            setVideoBlobUrl(null)
          }}
        />

        <EvidenceSidebar
          ticket={ticket}
          form={form}
          onFormChange={onFormChange}
          onSave={() => save()}
          onApprove={() => save('approved')}
          onReject={() => save('rejected')}
          saving={saving}
        />
      </div>

      <div className="strip-card">
        <div className="strip-card-header">
          <div>
            <h2 className="card-title">{he.review.screenshots}</h2>
            <div className="video-note">
              {he.review.metadataTimestamp}: {metadataStartAt ? new Date(metadataStartAt).toLocaleString('he-IL') : '—'}
            </div>
          </div>
        </div>
        <ScreenshotStrip items={shots} emptyLabel={he.review.noScreenshots} />
      </div>
    </div>
  )
}
