
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { uploadApi } from '../api'
import { he } from '../i18n/he'
import { useRtl } from '../hooks/useRtl'

interface UploadJob {
  job_id: number
  status: string
  ticket_id?: number
  license_plate?: string
  created_at?: string
  error_message?: string
}

const statusColors: Record<string, string> = {
  queued: '#6b7280',
  processing: '#2563eb',
  completed: '#22c55e',
  failed: '#dc2626',
}

export default function Home() {
  useRtl(`${he.home.title} | ${he.app.title}`)

  const navigate = useNavigate()
  const [jobs, setJobs] = useState<UploadJob[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchJobs = async () => {
    try {
      const { data } = await uploadApi.listJobs()
      setJobs(data)
    } catch (err) {
      console.error('Failed to fetch jobs', err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchJobs()
  }, [])

  return (
    <div style={{ padding: '1rem 2rem', maxWidth: 920, margin: '0 auto' }}>
      <h1>{he.home.title}</h1>
      <p>{he.home.subtitle}</p>

      <div style={{ background: '#fff', border: '1px solid #d7dfeb', borderRadius: 14, padding: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>{he.home.queueTitle}</h2>
          <button
            onClick={() => {
              setRefreshing(true)
              fetchJobs()
            }}
            style={{ padding: '0.5rem 1rem', borderRadius: 10, border: 'none', background: '#1646a0', color: '#fff' }}
          >
            {refreshing ? he.home.refreshing : he.home.refresh}
          </button>
        </div>

        {loading ? (
          <div>{he.home.loading}</div>
        ) : jobs.length === 0 ? (
          <div>{he.home.empty}</div>
        ) : (
          <div style={{ display: 'grid', gap: 12 }}>
            {jobs.map((job) => (
              <div key={job.job_id} style={{ border: '1px solid #e8edf5', borderRadius: 12, padding: '12px 14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                  <div>
                    <div><strong>{he.home.job}:</strong> {job.job_id}</div>
                    <div><strong>{he.home.status}:</strong> <span style={{ color: statusColors[job.status] || '#142033' }}>{job.status}</span></div>
                    <div><strong>{he.home.plate}:</strong> {job.license_plate && job.license_plate !== '11111' ? job.license_plate : he.home.plateNotIdentified}</div>
                    <div><strong>{he.home.created}:</strong> {job.created_at ? new Date(job.created_at).toLocaleString('he-IL') : '—'}</div>
                    {job.error_message ? <div><strong>{he.home.error}:</strong> {job.error_message}</div> : null}
                  </div>
                  {job.ticket_id ? (
                    <button
                      onClick={() => navigate(`/tickets/${job.ticket_id}`)}
                      style={{ alignSelf: 'start', padding: '0.55rem 0.9rem', borderRadius: 10, border: 'none', background: '#eef2f7' }}
                    >
                      {he.home.openTicket}
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
