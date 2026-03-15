import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import api from '../api'
import { t } from '../i18n'

export default function Upload() {
  const [capturedAt, setCapturedAt] = useState(new Date().toISOString())
  const [licensePlate, setLicensePlate] = useState('')
  const [zone, setZone] = useState('red_white')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<{ message?: string } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setCapturedAt(new Date().toISOString())
    const intervalId = setInterval(() => setCapturedAt(new Date().toISOString()), 1000)
    return () => clearInterval(intervalId)
  }, [])

  const uploadFile = async (file: File) => {
    setSubmitting(true)
    setResult(null)
    try {
      const fd = new FormData()
      fd.append('video', file)
      fd.append('captured_at', capturedAt)
      fd.append('license_plate', licensePlate.trim())
      fd.append('violation_zone', zone)
      const { data } = await api.post('/upload/violation', fd)
      setResult(data)
      if (inputRef.current) inputRef.current.value = ''
    } catch (err) {
      const axErr = err as { response?: { data?: { detail?: string } } }
      alert(axErr?.response?.data?.detail || err)
    } finally {
      setSubmitting(false)
    }
  }

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const chosen = e.target.files?.[0]
    if (chosen) uploadFile(chosen)
  }

  const styles: Record<string, React.CSSProperties> = {
    page: { padding: '1rem', maxWidth: 480, margin: '0 auto', fontFamily: 'system-ui' },
    title: { fontSize: '1.5rem', marginBottom: '1rem' },
    label: { display: 'block', marginTop: '1rem', fontWeight: 600 },
    input: { width: '100%', padding: '0.75rem', fontSize: '1rem', marginTop: 4 },
    success: { background: '#d4edda', padding: '1rem', borderRadius: 8, marginTop: '1rem' },
  }

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>{t('uploadViolation')}</h1>
      <p style={{ color: '#666' }}>{t('uploadIntro')}</p>

      <label style={styles.label} htmlFor="video-upload">{t('videoSelect')}</label>
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        capture="environment"
        onChange={onFileChange}
        disabled={submitting}
        style={{ padding: '0.35rem', cursor: submitting ? 'wait' : 'pointer' }}
        id="video-upload"
      />
      {submitting && <p style={{ marginTop: 6, fontSize: '0.9rem', color: '#666' }}>{t('uploading')}</p>}

      <label style={styles.label}>{t('licensePlateOptional')}</label>
      <input
        type="text"
        value={licensePlate}
        onChange={e => setLicensePlate(e.target.value)}
        placeholder=""
        style={styles.input}
      />

      <label style={styles.label}>{t('zone')}</label>
      <select value={zone} onChange={e => setZone(e.target.value)} style={styles.input}>
        <option value="red_white">{t('zoneRedWhite')}</option>
        <option value="blue_white">{t('zoneBlueWhite')}</option>
      </select>

      {result && (
        <div style={styles.success}>
          ✓ {result.message}
          <p style={{ margin: '0.5rem 0 0', fontSize: '0.9rem' }}>
            {t('viewQueueOnHome')} <Link to="/" style={{ color: '#2563eb', textDecoration: 'underline' }}>{t('home')}</Link>.
          </p>
        </div>
      )}
    </div>
  )
}
