import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ticketsApi } from '../api'

interface TicketForm {
  license_plate: string
  location: string
  violation_zone: string
  description: string
  admin_notes: string
  fine_amount: string
}

export default function TicketReview() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [ticket, setTicket] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [reprocessing, setReprocessing] = useState(false)
  const [videoError, setVideoError] = useState<string | null>(null)
  const [videoRetryKey, setVideoRetryKey] = useState(0)
  const [videoBlobUrl, setVideoBlobUrl] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [form, setForm] = useState<TicketForm>({
    license_plate: '',
    location: '',
    violation_zone: 'red_white',
    description: '',
    admin_notes: '',
    fine_amount: '',
  })

  useEffect(() => {
    if (!id) return
    ticketsApi.get(id)
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

  const videoBlobUrlRef = useRef<string | null>(null)

  useEffect(() => {
    if ((!ticket?.video_id && !ticket?.video_path) || !id) return
    setVideoError(null)
    let blobUrl: string | null = null
    let cancelled = false
    const load = async () => {
      try {
        const res = await ticketsApi.getVideo(id, videoRetryKey || Date.now())
        if (cancelled) return
        if (res.status < 200 || res.status >= 300) {
          setVideoError('Server error')
          return
        }
        const data = res.data
        if (!(data instanceof Blob) || data.size < 100) {
          setVideoError('Invalid video response')
          return
        }
        const blob = data instanceof Blob ? data : new Blob([data], { type: 'video/mp4' })
        blobUrl = URL.createObjectURL(blob)
        if (videoBlobUrlRef.current) URL.revokeObjectURL(videoBlobUrlRef.current)
        videoBlobUrlRef.current = blobUrl
        setVideoBlobUrl(blobUrl)
      } catch (err) {
        const axErr = err as { response?: { status?: number } }
        if (!cancelled) setVideoError(axErr?.response?.status === 404 ? 'Video not ready' : 'Could not load video')
      }
    }
    load()
    return () => {
      cancelled = true
      if (blobUrl) URL.revokeObjectURL(blobUrl)
      videoBlobUrlRef.current = null
      setVideoBlobUrl(null)
    }
  }, [ticket?.video_id, ticket?.video_path, id, videoRetryKey])

  const save = async () => {
    if (!id) return
    setSaving(true)
    try {
      const { data } = await ticketsApi.update(id, {
        license_plate: form.license_plate,
        location: form.location || null,
        violation_zone: form.violation_zone,
        description: form.description || null,
        admin_notes: form.admin_notes || null,
        fine_amount: form.fine_amount ? parseInt(form.fine_amount, 10) : null,
      })
      setTicket(data)
    } catch (e) {
      const axErr = e as { response?: { data?: { detail?: string } } }
      alert(axErr?.response?.data?.detail || 'Update failed')
    } finally {
      setSaving(false)
    }
  }

  const approve = async () => {
    if (!id) return
    setSaving(true)
    try {
      await ticketsApi.update(id, {
        license_plate: form.license_plate,
        location: form.location || null,
        violation_zone: form.violation_zone,
        description: form.description || null,
        admin_notes: form.admin_notes || null,
        fine_amount: form.fine_amount ? parseInt(form.fine_amount, 10) : null,
        status: 'approved',
      })
      navigate('/tickets')
    } catch (e) {
      const axErr = e as { response?: { data?: { detail?: string } } }
      alert(axErr?.response?.data?.detail || 'Approve failed')
    } finally {
      setSaving(false)
    }
  }

  const reprocessVideo = async () => {
    if (!id) return
    setReprocessing(true)
    try {
      await ticketsApi.reprocessVideo(id)
      setVideoRetryKey(k => k + 1)
    } catch (e) {
      const axErr = e as { response?: { data?: { detail?: string } } }
      alert(axErr?.response?.data?.detail || 'Reprocess failed')
    } finally {
      setReprocessing(false)
    }
  }

  const reject = async () => {
    if (!id) return
    setSaving(true)
    try {
      await ticketsApi.update(id, {
        license_plate: form.license_plate,
        location: form.location || null,
        violation_zone: form.violation_zone,
        description: form.description || null,
        admin_notes: form.admin_notes || null,
        fine_amount: form.fine_amount ? parseInt(form.fine_amount, 10) : null,
        status: 'rejected',
      })
      navigate('/tickets')
    } catch (e) {
      const axErr = e as { response?: { data?: { detail?: string } } }
      alert(axErr?.response?.data?.detail || 'Reject failed')
    } finally {
      setSaving(false)
    }
  }

  const styles: Record<string, React.CSSProperties> = {
    page: { padding: '1.5rem', maxWidth: 900, margin: '0 auto', fontFamily: 'system-ui' },
    title: { fontSize: '1.5rem', marginBottom: '1rem' },
    back: { color: '#2563eb', cursor: 'pointer', marginBottom: '1rem' },
    grid: { display: 'grid', gap: '1.5rem' },
    video: { background: '#111', borderRadius: 8, overflow: 'hidden', maxWidth: 640 },
    label: { display: 'block', marginBottom: 4, fontWeight: 600 },
    input: { width: '100%', padding: '0.5rem', marginBottom: '1rem' },
    select: { width: '100%', padding: '0.5rem', marginBottom: '1rem' },
    textarea: { width: '100%', padding: '0.5rem', minHeight: 80, marginBottom: '1rem' },
    row: { display: 'flex', gap: 12, marginTop: '1rem' },
    btn: { padding: '0.75rem 1.5rem', borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 600 },
    btnSave: { background: '#e5e7eb', color: '#111' },
    btnApprove: { background: '#22c55e', color: 'white' },
    btnReject: { background: '#ef4444', color: 'white' },
  }

  if (loading) return <div style={styles.page}><p>Loading...</p></div>
  if (!ticket) return <div style={styles.page}><p>Ticket not found.</p></div>

  return (
    <div style={styles.page}>
      <div style={styles.back} onClick={() => navigate('/tickets')}>← Back to tickets</div>
      <h1 style={styles.title}>
        Ticket #{String(ticket.id)}
        <span style={{ fontWeight: 600, color: form.license_plate && form.license_plate !== '11111' ? '#1a1a2e' : '#64748b', marginLeft: 12 }}>
          — Plate: {form.license_plate || '11111'}
        </span>
      </h1>

      <div style={styles.grid}>
        {(ticket.video_id || ticket.video_path) && (
          <div>
            <h3 style={{ marginBottom: 8 }}>Video</h3>
            <div style={styles.video}>
              {videoBlobUrl ? (
                <div style={{ position: 'relative' }}>
                  <video
                    ref={videoRef}
                    controls
                    playsInline
                    width="100%"
                    src={videoBlobUrl}
                    key={videoBlobUrl}
                    preload="auto"
                    onError={() => setVideoError('Video could not be played (format may not be supported)')}
                  />
                  <button
                    type="button"
                    onClick={() => { videoRef.current?.play().catch(() => setVideoError('Video could not be played')) }}
                    style={{
                      position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%, -50%)',
                      padding: '16px 32px', fontSize: '1.1rem', background: 'rgba(0,0,0,0.85)', color: 'white',
                      border: 'none', borderRadius: 8, cursor: 'pointer', zIndex: 10,
                    }}
                  >
                    ▶ Play
                  </button>
                </div>
              ) : videoError ? (
                <p style={{ color: '#e11', padding: '2rem' }}>
                  {videoError}
                  <button
                    type="button"
                    onClick={() => { setVideoError(null); setVideoRetryKey(k => k + 1); }}
                    style={{ marginLeft: 8, padding: '4px 12px', cursor: 'pointer' }}
                  >
                    Retry
                  </button>
                </p>
              ) : (
                <p style={{ color: '#888', padding: '2rem' }}>Loading video...</p>
              )}
            </div>
            <button
              type="button"
              onClick={reprocessVideo}
              disabled={reprocessing}
              style={{
                marginTop: 8, padding: '8px 16px', cursor: reprocessing ? 'wait' : 'pointer',
                background: '#f59e0b', color: 'white', border: 'none', borderRadius: 6, fontWeight: 600,
              }}
            >
              {reprocessing ? 'Reprocessing…' : 'Reprocess video (apply blur)'}
            </button>
          </div>
        )}
        <div>
          <h3 style={{ marginBottom: 12 }}>Details</h3>
          <label style={styles.label}>License plate</label>
          <input
            type="text"
            value={form.license_plate}
            onChange={e => setForm(f => ({ ...f, license_plate: e.target.value }))}
            placeholder={form.license_plate === '11111' ? 'Not detected — enter manually' : ''}
            style={styles.input}
          />
          {form.license_plate === '11111' && (
            <div style={{ fontSize: '0.85rem', color: '#b91c1c', marginTop: -8, marginBottom: '1rem', padding: '0.5rem 0.75rem', background: '#fef2f2', borderRadius: 6, borderLeft: '3px solid #dc2626' }}>
              <strong>Plate not retrieved:</strong>{' '}
              {(ticket?.plate_detection_reason as string) || 'No specific reason recorded.'} Enter the plate above if visible.
            </div>
          )}
          <label style={styles.label}>Location</label>
          <input
            type="text"
            value={form.location}
            onChange={e => setForm(f => ({ ...f, location: e.target.value }))}
            style={styles.input}
          />
          <label style={styles.label}>Violation zone</label>
          <select
            value={form.violation_zone}
            onChange={e => setForm(f => ({ ...f, violation_zone: e.target.value }))}
            style={styles.select}
          >
            <option value="red_white">Red/White</option>
            <option value="blue_white">Blue/White</option>
          </select>
          <label style={styles.label}>Description</label>
          <textarea
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            style={styles.textarea}
          />
          <label style={styles.label}>Admin notes</label>
          <textarea
            value={form.admin_notes}
            onChange={e => setForm(f => ({ ...f, admin_notes: e.target.value }))}
            style={styles.textarea}
          />
          <label style={styles.label}>Fine amount (cents)</label>
          <input
            type="number"
            value={form.fine_amount}
            onChange={e => setForm(f => ({ ...f, fine_amount: e.target.value }))}
            placeholder="e.g. 5000"
            style={styles.input}
          />

          <div style={styles.row}>
            <button style={{ ...styles.btn, ...styles.btnSave }} onClick={save} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </button>
            {ticket.status === 'pending_review' && (
              <>
                <button style={{ ...styles.btn, ...styles.btnApprove }} onClick={approve} disabled={saving}>
                  Approve
                </button>
                <button style={{ ...styles.btn, ...styles.btnReject }} onClick={reject} disabled={saving}>
                  Reject
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
