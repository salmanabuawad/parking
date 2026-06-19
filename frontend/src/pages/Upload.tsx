import { useState, useEffect, useRef } from 'react'
import { Camera, Image as ImageIcon, Video, MapPin } from 'lucide-react'
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

  return (
    <div className="page-container max-w-[480px] w-full mx-auto" dir="rtl">
      {/* Page header */}
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon">
          <Camera className="w-5 h-5" strokeWidth={1.5} />
        </span>
        <h1 className="page-header-title">דיווח על חנייה אסורה</h1>
      </div>

      {/* GPS status */}
      <div
        className={`app-card p-3 text-theme-sm flex items-center gap-2 ${
          gps ? 'text-green-700' : gpsError ? 'text-red-600' : 'text-theme-text-muted'
        }`}
      >
        <MapPin className="w-4 h-4 shrink-0" />
        <span>
          {gps
            ? `מיקום: ${gps.latitude.toFixed(5)}, ${gps.longitude.toFixed(5)}${gps.accuracy ? ` (±${Math.round(gps.accuracy)}מ')` : ''}`
            : gpsError
            ? `${gpsError} — הדיווח יישלח ללא GPS`
            : 'מאתר מיקום GPS…'}
        </span>
      </div>

      {/* Video capture */}
      <div>
        <label className="label-base" htmlFor="video-upload">בחר / צלם וידאו</label>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting}
            onClick={() => { if (inputRef.current) { (inputRef.current as any).capture = 'environment'; inputRef.current.click() } }}
            className="btn-primary flex-1"
          >
            <Camera className="w-4 h-4" />
            <span>צלם וידאו</span>
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={() => { if (inputRef.current) { (inputRef.current as any).removeAttribute?.('capture'); inputRef.current.removeAttribute('capture'); inputRef.current.click() } }}
            className="btn-cancel flex-1"
          >
            <ImageIcon className="w-4 h-4" />
            <span>בחר מהגלריה</span>
          </button>
        </div>
        <input
          ref={inputRef}
          id="video-upload"
          type="file"
          accept="video/*"
          onChange={onFileChange}
          disabled={submitting}
          className="hidden"
        />
        {selectedFile && (
          <div className="flex items-center gap-1.5 text-theme-sm text-theme-text-primary mt-2">
            <Video className="w-4 h-4 shrink-0" />
            <span>{selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(1)} MB)</span>
          </div>
        )}
      </div>

      {/* License plate (optional) */}
      <div>
        <label className="label-base">מספר רכב (אופציונלי)</label>
        <input
          type="text"
          value={licensePlate}
          onChange={e => setLicensePlate(e.target.value)}
          placeholder="לדוגמה: 1234567"
          className="input-base"
          inputMode="numeric"
        />
      </div>

      {/* Zone */}
      <div>
        <label className="label-base">סוג חנייה</label>
        <select value={zone} onChange={e => setZone(e.target.value)} className="input-base">
          <option value="red_white">אדום-לבן (אסור לחלוטין)</option>
          <option value="blue_white">כחול-לבן (תשלום)</option>
        </select>
      </div>

      {/* Submit */}
      <button onClick={handleSubmit} disabled={submitting || !selectedFile} className="btn-primary w-full justify-center">
        {submitting ? 'מעלה…' : 'שלח דיווח'}
      </button>

      {error && (
        <div className="app-card p-3 text-theme-sm text-red-600">
          ⚠ {error}
        </div>
      )}

      {jobId && (
        <div className="app-card p-4">
          <div className="text-theme-base font-medium text-green-700">
            ✓ הדיווח התקבל! מספר עבודה: {jobId}
          </div>
          <div className="text-theme-sm text-theme-text-muted mt-1.5">
            הוידאו מעובד ברקע. הדוח יופיע ברשימת הדוחות בקרוב.
          </div>
        </div>
      )}
    </div>
  )
}
