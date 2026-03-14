import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { uploadApi } from '../api'

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

  const handleRefresh = () => {
    setRefreshing(true)
    fetchJobs()
  }

  const styles: Record<string, React.CSSProperties> = {
    page: { padding: '1rem 2rem', maxWidth: 720, margin: 0, fontFamily: 'system-ui' },
    title: { fontSize: '1.5rem', marginBottom: '1rem' },
    card: { background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '1rem', marginBottom: '1rem' },
    btn: { padding: '0.5rem 1rem', fontSize: '0.9rem', background: '#374151', color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer' },
    link: { color: '#2563eb', textDecoration: 'underline', cursor: 'pointer' },
  }

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>Home</h1>
      <p style={{ color: '#666', marginBottom: '1.5rem' }}>
        <Link to="/upload" style={styles.link}>Upload a violation</Link> or view recent queue status below.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.2rem', margin: 0 }}>Queue status</h2>
        <button
          type="button"
          style={styles.btn}
          onClick={handleRefresh}
          disabled={refreshing}
        >
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {loading ? (
        <p>Loading...</p>
      ) : jobs.length === 0 ? (
        <div style={styles.card}>No upload jobs yet.</div>
      ) : (
        <div>
          {jobs.map((j) => (
            <div key={j.job_id} style={styles.card}>
              <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                <span style={{ fontWeight: 600 }}>Job #{j.job_id}</span>
                <span style={{ color: statusColors[j.status] || '#374151' }}>{j.status}</span>
                {j.license_plate && (
                  <span style={{ fontSize: '0.9rem', color: '#666' }}>{j.license_plate}</span>
                )}
                {j.created_at && (
                  <span style={{ fontSize: '0.85rem', color: '#888' }}>
                    {new Date(j.created_at).toLocaleString()}
                  </span>
                )}
              </div>
              {j.status === 'completed' && j.ticket_id && (
                <div style={{ marginTop: 8 }}>
                  Ticket:{' '}
                  <a
                    href={`/tickets/${j.ticket_id}`}
                    onClick={(e) => {
                      e.preventDefault()
                      navigate(`/tickets/${j.ticket_id}`)
                    }}
                    style={styles.link}
                  >
                    #{j.ticket_id}
                  </a>
                </div>
              )}
              {j.status === 'failed' && j.error_message && (
                <div style={{ marginTop: 8, color: '#dc2626' }}>{j.error_message}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
