import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../api'

interface LocationState {
  lat: number | null
  lng: number | null
  error: string | null
}

export default function Upload() {
  const [file, setFile] = useState<File | null>(null)
  const [location, setLocation] = useState<LocationState>({ lat: null, lng: null, error: null })
  const [capturedAt, setCapturedAt] = useState(new Date().toISOString())
  const [licensePlate, setLicensePlate] = useState('11111')
  const [zone, setZone] = useState('red_white')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<{ message?: string } | null>(null)

  useEffect(() => {
    setCapturedAt(new Date().toISOString())
    const t = setInterval(() => setCapturedAt(new Date().toISOString()), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (!navigator.geolocation) {
      setLocation(l => ({ ...l, error: 'GPS not supported' }))
      return
    }
    navigator.geolocation.getCurrentPosition(
      pos => setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude, error: null }),
      err => setLocation(l => ({ ...l, error: err.message || 'Location denied' }))
    )
  }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) { alert('Please select a video file before uploading.'); return }
    if (location.error || location.lat == null) { alert('Allow location access'); return }
    setSubmitting(true)
    setResult(null)
    try {
      const fd = new FormData()
      fd.append('video', file)
      fd.append('latitude', String(location.lat))
      fd.append('longitude', String(location.lng))
      fd.append('captured_at', capturedAt)
      fd.append('license_plate', licensePlate || '11111')
      fd.append('violation_zone', zone)
      const { data } = await api.post('/upload/violation', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setResult(data)
      setFile(null)
    } catch (err) {
      const axErr = err as { response?: { data?: { detail?: string } } }
      alert(axErr?.response?.data?.detail || err)
    } finally {
      setSubmitting(false)
    }
  }

  const styles: Record<string, React.CSSProperties> = {
    page: { padding: '1rem', maxWidth: 480, margin: '0 auto', fontFamily: 'system-ui' },
    title: { fontSize: '1.5rem', marginBottom: '1rem' },
    label: { display: 'block', marginTop: '1rem', fontWeight: 600 },
    input: { width: '100%', padding: '0.75rem', fontSize: '1rem', marginTop: 4 },
    btn: { width: '100%', padding: '1rem', marginTop: '1.5rem', fontSize: '1.1rem', background: '#1a1a2e', color: 'white', border: 'none', borderRadius: 8 },
    info: { background: '#f0f0f0', padding: '0.75rem', borderRadius: 8, marginTop: 8, fontSize: '0.9rem' },
    success: { background: '#d4edda', padding: '1rem', borderRadius: 8, marginTop: '1rem' },
  }

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>Upload Violation</h1>
      <p style={{ color: '#666' }}>Record or select a video. GPS and time are captured automatically. The system will analyze and blur the video (license plates only visible) for privacy before admin review.</p>

      <form onSubmit={submit}>
        <label style={styles.label} htmlFor="video-upload">Video * — Select a video</label>
        <div style={{ marginTop: 4 }}>
          <input
            type="file"
            accept="video/*"
            capture="environment"
            onChange={e => setFile(e.target.files?.[0] ?? null)}
            style={{ ...styles.input, cursor: 'pointer' }}
            id="video-upload"
          />
          {file && (
            <p style={{ marginTop: 6, fontSize: '0.9rem', color: '#22c55e' }}>
              Selected: {file.name}
            </p>
          )}
        </div>

        <label style={styles.label}>GPS location</label>
        <div style={styles.info}>
          {location.error ? (
            <span style={{ color: 'red' }}>{location.error}</span>
          ) : location.lat != null ? (
            <>
              {location.lat.toFixed(6)}, {location.lng!.toFixed(6)}
            </>
          ) : (
            'Getting location...'
          )}
        </div>

        <label style={styles.label}>Time captured</label>
        <div style={styles.info}>
          {new Date(capturedAt).toLocaleString()}
        </div>

        <label style={styles.label}>License plate (optional)</label>
        <input
          type="text"
          value={licensePlate}
          onChange={e => setLicensePlate(e.target.value)}
          placeholder="11111"
          style={styles.input}
        />

        <label style={styles.label}>Zone</label>
        <select value={zone} onChange={e => setZone(e.target.value)} style={styles.input}>
          <option value="red_white">Red/White</option>
          <option value="blue_white">Blue/White</option>
        </select>

        <button type="submit" style={styles.btn} disabled={submitting}>
          {submitting ? 'Uploading...' : 'Upload'}
        </button>
      </form>

      {result && (
        <div style={styles.success}>
          ✓ {result.message}
          <p style={{ margin: '0.5rem 0 0', fontSize: '0.9rem' }}>
            View queue status on <Link to="/" style={{ color: '#2563eb', textDecoration: 'underline' }}>Home</Link>.
          </p>
        </div>
      )}
    </div>
  )
}
