import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../api'
import { uploadApi, settingsApi } from '../api'

interface UploadJob {
  job_id: number
  status: string
  source?: string
  target?: string
  license_plate?: string | null
  error_message?: string | null
}

interface Settings {
  blur_kernel_size: number
  use_violation_pipeline?: boolean
}

const statusColors: Record<string, string> = {
  queued: '#6b7280',
  processing: '#2563eb',
  completed: '#22c55e',
  failed: '#dc2626',
}

export default function QueueMaintenance() {
  const [jobs, setJobs] = useState<UploadJob[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [rerunning, setRerunning] = useState<number | null>(null)
  const [resettingStuck, setResettingStuck] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadLat, setUploadLat] = useState('0')
  const [uploadLng, setUploadLng] = useState('0')
  const [uploadPlate, setUploadPlate] = useState('')

  const fetchJobs = async () => {
    try {
      const { data } = await uploadApi.listJobs(50)
      setJobs(data)
    } catch (err) {
      console.error('Failed to fetch jobs', err)
    }
  }

  const fetchSettings = async () => {
    try {
      const { data } = await settingsApi.get()
      setSettings(data)
    } catch (err) {
      console.error('Failed to fetch settings', err)
    }
  }

  const load = async () => {
    setLoading(true)
    await Promise.all([fetchJobs(), fetchSettings()])
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  // Auto-refresh jobs every 5 seconds
  useEffect(() => {
    const interval = setInterval(fetchJobs, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleResetStuck = async () => {
    setResettingStuck(true)
    try {
      const { data } = await uploadApi.resetStuckJobs()
      await fetchJobs()
      alert(data.message || `Reset ${data.reset_count} stuck job(s)`)
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      alert(ax.response?.data?.detail || ax.message)
    } finally {
      setResettingStuck(false)
    }
  }

  const handleRerun = async (jobId: number) => {
    setRerunning(jobId)
    try {
      await uploadApi.rerunJob(jobId)
      await fetchJobs()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      alert(ax.response?.data?.detail || ax.message)
    } finally {
      setRerunning(null)
    }
  }

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!uploadFile) {
      alert('Select a video')
      return
    }
    const lat = parseFloat(uploadLat)
    const lng = parseFloat(uploadLng)
    if (Number.isNaN(lat) || Number.isNaN(lng)) {
      alert('Enter valid latitude and longitude')
      return
    }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('video', uploadFile)
      fd.append('latitude', String(lat))
      fd.append('longitude', String(lng))
      fd.append('captured_at', new Date().toISOString())
      fd.append('license_plate', uploadPlate.trim() || '11111')
      fd.append('violation_zone', 'red_white')
      await api.post('/upload/violation', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setUploadFile(null)
      await fetchJobs()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      alert(ax.response?.data?.detail || ax.message)
    } finally {
      setUploading(false)
    }
  }

  const styles: Record<string, React.CSSProperties> = {
    page: { padding: '1rem 2rem', fontFamily: 'system-ui', maxWidth: 1200 },
    title: { fontSize: '1.5rem', marginBottom: '0.5rem' },
    subtitle: { color: '#666', marginBottom: '1rem', fontSize: '0.95rem' },
    table: { width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' },
    th: { padding: '0.75rem 1rem', textAlign: 'left', background: '#1a1a2e', color: 'white', fontWeight: 600 },
    td: { padding: '0.6rem 1rem', borderBottom: '1px solid #e2e8f0' },
    btn: { padding: '0.35rem 0.75rem', fontSize: '0.85rem', background: '#374151', color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer' },
    link: { color: '#2563eb', textDecoration: 'underline' },
    blurBadge: { display: 'inline-block', padding: '0.2rem 0.5rem', background: '#e0e7ff', color: '#4338ca', borderRadius: 4, fontSize: '0.9rem' },
  }

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>Queue Maintenance</h1>
      <p style={styles.subtitle}>
        View source/target paths, blur ratio, and rerun jobs.
        <Link to="/settings" style={{ ...styles.link, marginLeft: '0.5rem' }}>Edit blur settings</Link>
      </p>

      <form onSubmit={handleUpload} style={{ marginBottom: '1.5rem', padding: '1rem', background: '#f8fafc', borderRadius: 8, display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '1rem' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>Video</label>
          <input
            type="file"
            accept="video/*"
            onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
            style={{ padding: '0.35rem' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>Latitude</label>
          <input
            type="text"
            value={uploadLat}
            onChange={(e) => setUploadLat(e.target.value)}
            placeholder="0"
            style={{ padding: '0.35rem 0.5rem', width: 100 }}
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>Longitude</label>
          <input
            type="text"
            value={uploadLng}
            onChange={(e) => setUploadLng(e.target.value)}
            placeholder="0"
            style={{ padding: '0.35rem 0.5rem', width: 100 }}
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 4 }}>License plate (optional)</label>
          <input
            type="text"
            value={uploadPlate}
            onChange={(e) => setUploadPlate(e.target.value)}
            placeholder="Leave blank to auto-detect"
            style={{ padding: '0.35rem 0.5rem', width: 140 }}
          />
        </div>
        <button type="submit" style={styles.btn} disabled={uploading}>
          {uploading ? 'Uploading...' : 'Add to queue'}
        </button>
      </form>

      {loading ? (
        <p>Loading...</p>
      ) : (
        <>
          {settings && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem', background: '#f8fafc', borderRadius: 8, display: 'inline-block' }}>
              <strong>Blur kernel size:</strong>{' '}
              <span style={styles.blurBadge}>{settings.blur_kernel_size}</span>
              <span style={{ color: '#64748b', marginLeft: 8, fontSize: '0.9rem' }}>
                (0=off, 3=light, 5–51=strong)
              </span>
            </div>
          )}

          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Job #</th>
                  <th style={styles.th}>Source</th>
                  <th style={styles.th}>Target</th>
                  <th style={styles.th}>Status</th>
                  <th style={styles.th}>Plate</th>
                  <th style={styles.th}>Failing reason</th>
                  <th style={styles.th}>Blur ratio</th>
                  <th style={styles.th}>Rerun</th>
                </tr>
              </thead>
              <tbody>
                {jobs.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ ...styles.td, textAlign: 'center', color: '#64748b' }}>
                      No jobs yet.
                    </td>
                  </tr>
                ) : (
                  jobs.map((j) => (
                    <tr key={j.job_id}>
                      <td style={styles.td}>{j.job_id}</td>
                      <td style={styles.td}>
                        <code style={{ fontSize: '0.85rem', wordBreak: 'break-all' }}>{j.source || '—'}</code>
                      </td>
                      <td style={styles.td}>
                        <code style={{ fontSize: '0.85rem', wordBreak: 'break-all' }}>{j.target || '—'}</code>
                      </td>
                      <td style={styles.td}>
                        <span style={{ color: statusColors[j.status] || '#374151', fontWeight: 500 }}>
                          {j.status}
                        </span>
                      </td>
                      <td style={styles.td}>
                        <span style={{ fontWeight: 500 }}>{j.license_plate || '—'}</span>
                      </td>
                      <td style={styles.td}>
                        {j.error_message ? (
                          <span style={{ color: '#dc2626', fontSize: '0.85rem', maxWidth: 200, display: 'inline-block' }} title={j.error_message}>
                            {j.error_message.length > 80 ? `${j.error_message.slice(0, 80)}…` : j.error_message}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td style={styles.td}>
                        <span style={styles.blurBadge}>{settings?.blur_kernel_size ?? '—'}</span>
                      </td>
                      <td style={styles.td}>
                        <button
                          type="button"
                          style={styles.btn}
                          onClick={() => handleRerun(j.job_id)}
                          disabled={rerunning === j.job_id}
                        >
                          {rerunning === j.job_id ? 'Rerunning...' : 'Rerun'}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
