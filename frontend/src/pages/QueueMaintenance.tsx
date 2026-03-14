import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import api from '../api'
import { uploadApi, settingsApi } from '../api'
import { t } from '../i18n'

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
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('video', file)
      fd.append('latitude', '0')
      fd.append('longitude', '0')
      fd.append('captured_at', new Date().toISOString())
      fd.append('license_plate', '')
      fd.append('violation_zone', 'red_white')
      await api.post('/upload/violation', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      await fetchJobs()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      alert(ax.response?.data?.detail || ax.message)
    } finally {
      setUploading(false)
      e.target.value = ''
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
      <h1 style={styles.title}>{t('queueMaintenance')}</h1>
      <p style={styles.subtitle}>
        {t('queueSubtitle')}
        <Link to="/settings" style={{ ...styles.link, marginLeft: '0.5rem' }}>{t('editBlurSettings')}</Link>
      </p>

      <div style={{ marginBottom: '1.5rem', padding: '1rem', background: '#f8fafc', borderRadius: 8 }}>
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          onChange={handleFileChange}
          disabled={uploading}
          style={{ display: 'none' }}
        />
        <button
          type="button"
          style={styles.btn}
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? t('uploading') : t('uploadVideo')}
        </button>
      </div>

      {loading ? (
        <p>{t('loading')}</p>
      ) : (
        <>
          {settings && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem', background: '#f8fafc', borderRadius: 8, display: 'inline-block' }}>
              <strong>{t('blurKernelSize')}:</strong>{' '}
              <span style={styles.blurBadge}>{settings.blur_kernel_size}</span>
              <span style={{ color: '#64748b', marginLeft: 8, fontSize: '0.9rem' }}>
                {t('blurKernelHint')}
              </span>
            </div>
          )}

          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t('jobNum')}</th>
                  <th style={styles.th}>{t('source')}</th>
                  <th style={styles.th}>{t('target')}</th>
                  <th style={styles.th}>{t('status')}</th>
                  <th style={styles.th}>{t('plate')}</th>
                  <th style={styles.th}>{t('failingReason')}</th>
                  <th style={styles.th}>{t('blurRatio')}</th>
                  <th style={styles.th}>{t('rerun')}</th>
                </tr>
              </thead>
              <tbody>
                {jobs.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ ...styles.td, textAlign: 'center', color: '#64748b' }}>
                      {t('noJobsYet')}
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
                          {j.status === 'queued' ? t('statusQueued') : j.status === 'processing' ? t('statusProcessing') : j.status === 'completed' ? t('statusCompleted') : j.status === 'failed' ? t('statusFailed') : j.status}
                        </span>
                      </td>
                      <td style={styles.td}>
                        <span style={{ fontWeight: 500 }}>{j.license_plate && j.license_plate !== '11111' ? j.license_plate : t('plateNotIdentified')}</span>
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
                          {rerunning === j.job_id ? t('rerunning') : t('rerun')}
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
