import { useState, useEffect, useRef } from 'react'
import api from '../api'

interface GpsCoords {
  latitude: number
  longitude: number
  accuracy?: number
}

export default function Upload() {
  const [capturedAt] = useState(new Date().toISOString())
  const [licensePlate, setLicensePlate] = useState('')
  const [zone, setZone] = useState('red_white')
  const [submitting, setSubmitting] = useState(false)
  const [jobId, setJobId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [gps, setGps] = useState<GpsCoords | null>(null)
  const [gpsError, setGpsError] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Acquire GPS on mount
  useEffect(() => {
    if (!navigator.geolocation) {
      setGpsError('GPS אינו זמין בדפדפן זה')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGps({ latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: pos.coords.accuracy })
        setGpsError(null)
      },
      (err) => {
        setGpsError(`GPS: ${err.message}`)
      },
      { enableHighAccuracy: true, timeout: 15000 }
    )
  }, [])

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null
    setSelectedFile(file)
    setJobId(null)
    setError(null)
  }

  const handleSubmit = async () => {
    if (!selectedFile) {
      setError('יש לבחור קובץ וידאו')
      return
    }
    setSubmitting(true)
    setError(null)
    setJobId(null)
    try {
      const fd = new FormData()
      fd.append('video', selectedFile)
      fd.append('captured_at', capturedAt)
      fd.append('license_plate', licensePlate.trim())
      fd.append('violation_zone', zone)
      if (gps) {
        fd.append('latitude', String(gps.latitude))
        fd.append('longitude', String(gps.longitude))
      }
      const { data } = await api.post<{ job_id: number }>('/upload/violation', fd)
      setJobId(data.job_id)
      setSelectedFile(null)
      if (inputRef.current) inputRef.current.value = ''
    } catch (err: any) {
      setError(err?.message || 'שגיאה בהעלאה')
    } finally {
      setSubmitting(false)
    }
  }

  const s: Record<string, React.CSSProperties> = {
    page: { padding: '1.25rem', maxWidth: 480, margin: '0 auto', fontFamily: 'system-ui', direction: 'rtl' },
    title: { fontSize: '1.4rem', marginBottom: '0.75rem', fontWeight: 700 },
    label: { display: 'block', marginTop: '1rem', fontWeight: 600, fontSize: '0.95rem', marginBottom: 4 },
    input: { width: '100%', padding: '0.75rem', fontSize: '1rem', borderRadius: 8, border: '1px solid #d1d5db', boxSizing: 'border-box' },
    btn: {
      width: '100%', padding: '0.9rem', fontSize: '1.05rem', marginTop: '1.25rem',
      borderRadius: 10, border: 'none', background: submitting ? '#93c5fd' : '#2563eb',
      color: '#fff', fontWeight: 700, cursor: submitting ? 'wait' : 'pointer',
    },
    gpsBox: { marginTop: '0.75rem', padding: '0.6rem 0.9rem', borderRadius: 8, fontSize: 13 },
    success: { background: '#d4edda', padding: '1rem', borderRadius: 10, marginTop: '1rem', fontSize: 15 },
    errBox: { background: '#fef2f2', color: '#dc2626', padding: '0.75rem 1rem', borderRadius: 8, marginTop: '0.75rem', fontSize: 14 },
  }

  return (
    <div style={s.page}>
      <h1 style={s.title}>דיווח על חנייה אסורה</h1>

      {/* GPS status */}
      <div style={{ ...s.gpsBox, background: gps ? '#f0fdf4' : gpsError ? '#fef2f2' : '#f9fafb', color: gps ? '#15803d' : gpsError ? '#dc2626' : '#6b7280' }}>
        {gps
          ? `📍 מיקום: ${gps.latitude.toFixed(5)}, ${gps.longitude.toFixed(5)}${gps.accuracy ? ` (±${Math.round(gps.accuracy)}מ')` : ''}`
          : gpsError
          ? `⚠ ${gpsError} — הדיווח יישלח ללא GPS`
          : '⏳ מאתר מיקום GPS…'}
      </div>

      {/* Video capture */}
      <label style={s.label} htmlFor="video-upload">בחר / צלם וידאו</label>
      <div style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
        <button
          type="button"
          disabled={submitting}
          onClick={() => { if (inputRef.current) { (inputRef.current as any).capture = 'environment'; inputRef.current.click() } }}
          style={{ flex: 1, padding: '0.6rem', borderRadius: 8, border: '1.5px solid #2563eb', background: '#eff6ff', color: '#1e40af', cursor: 'pointer', fontWeight: 600, fontFamily: 'inherit', fontSize: '0.9rem' }}
        >
          📷 צלם וידאו
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => { if (inputRef.current) { (inputRef.current as any).removeAttribute?.('capture'); inputRef.current.removeAttribute('capture'); inputRef.current.click() } }}
          style={{ flex: 1, padding: '0.6rem', borderRadius: 8, border: '1.5px solid #d1d5db', background: '#f9fafb', color: '#374151', cursor: 'pointer', fontWeight: 600, fontFamily: 'inherit', fontSize: '0.9rem' }}
        >
          🖼 בחר מהגלריה
        </button>
      </div>
      <input
        ref={inputRef}
        id="video-upload"
        type="file"
        accept="video/*"
        onChange={onFileChange}
        disabled={submitting}
        style={{ display: 'none' }}
      />
      {selectedFile && (
        <div style={{ fontSize: 13, color: '#374151', marginTop: 4 }}>
          📹 {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(1)} MB)
        </div>
      )}

      {/* License plate (optional) */}
      <label style={s.label}>מספר רכב (אופציונלי)</label>
      <input
        type="text"
        value={licensePlate}
        onChange={e => setLicensePlate(e.target.value)}
        placeholder="לדוגמה: 1234567"
        style={s.input}
        inputMode="numeric"
      />

      {/* Zone */}
      <label style={s.label}>סוג חנייה</label>
      <select value={zone} onChange={e => setZone(e.target.value)} style={s.input}>
        <option value="red_white">אדום-לבן (אסור לחלוטין)</option>
        <option value="blue_white">כחול-לבן (תשלום)</option>
      </select>

      {/* Submit */}
      <button onClick={handleSubmit} disabled={submitting || !selectedFile} style={s.btn}>
        {submitting ? 'מעלה…' : 'שלח דיווח'}
      </button>

      {error && <div style={s.errBox}>⚠ {error}</div>}

      {jobId && (
        <div style={s.success}>
          ✓ הדיווח התקבל! מספר עבודה: {jobId}
          <div style={{ fontSize: 13, marginTop: 6, color: '#374151' }}>
            הוידאו מעובד ברקע. הדוח יופיע ברשימת הדוחות בקרוב.
          </div>
        </div>
      )}
    </div>
  )
}
