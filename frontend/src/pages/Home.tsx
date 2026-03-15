
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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

const STATUS_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  queued:     { color: '#92400e', bg: '#fef3c7', label: 'ממתין בתור' },
  processing: { color: '#1e40af', bg: '#dbeafe', label: 'מעובד' },
  completed:  { color: '#065f46', bg: '#d1fae5', label: 'הושלם' },
  failed:     { color: '#991b1b', bg: '#fee2e2', label: 'נכשל' },
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{
      background: '#fff',
      border: '1px solid #e2e8f0',
      borderRadius: 12,
      padding: '1rem 1.25rem',
      minWidth: 110,
      flex: 1,
      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
    }}>
      <div style={{ fontSize: '1.75rem', fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: 2 }}>{label}</div>
    </div>
  )
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

  useEffect(() => { fetchJobs() }, [])

  const counts = {
    total: jobs.length,
    pending: jobs.filter((j) => j.status === 'queued').length,
    completed: jobs.filter((j) => j.status === 'completed').length,
    failed: jobs.filter((j) => j.status === 'failed').length,
  }

  return (
    <div style={{ padding: '1.5rem 2rem', maxWidth: 960, margin: '0 auto' }}>
      <div style={{ marginBottom: '1.25rem' }}>
        <h1 style={{ margin: '0 0 4px', fontSize: '1.5rem', color: '#0f172a' }}>{he.home.title}</h1>
        <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>{he.home.subtitle}</p>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: '1.5rem' }}>
        <StatCard label="סה״כ" value={counts.total} color="#1e40af" />
        <StatCard label="ממתינים" value={counts.pending} color="#d97706" />
        <StatCard label="הושלמו" value={counts.completed} color="#065f46" />
        <StatCard label="נכשלו" value={counts.failed} color="#dc2626" />
      </div>

      {/* Job list */}
      <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.85rem 1rem', borderBottom: '1px solid #f1f5f9' }}>
          <h2 style={{ margin: 0, fontSize: '1rem', color: '#0f172a' }}>{he.home.queueTitle}</h2>
          <button
            onClick={() => { setRefreshing(true); fetchJobs() }}
            style={{
              padding: '6px 14px',
              borderRadius: 8,
              border: 'none',
              background: '#1e40af',
              color: '#fff',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontFamily: 'inherit',
            }}
          >
            {refreshing ? he.home.refreshing : he.home.refresh}
          </button>
        </div>

        {loading ? (
          <div style={{ padding: '2rem', color: '#64748b', textAlign: 'center' }}>{he.home.loading}</div>
        ) : jobs.length === 0 ? (
          <div style={{ padding: '2rem', color: '#94a3b8', textAlign: 'center' }}>{he.home.empty}</div>
        ) : (
          <div>
            {jobs.map((job, idx) => {
              const ss = STATUS_STYLE[job.status] ?? { color: '#374151', bg: '#f3f4f6', label: job.status }
              return (
                <div
                  key={job.job_id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px 1rem',
                    borderBottom: idx < jobs.length - 1 ? '1px solid #f1f5f9' : 'none',
                    gap: 12,
                    flexWrap: 'wrap',
                  }}
                >
                  <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'center' }}>
                    <span style={{ color: '#94a3b8', fontSize: '0.85rem', minWidth: 50 }}>#{job.job_id}</span>
                    <span style={{
                      padding: '3px 10px',
                      borderRadius: 999,
                      background: ss.bg,
                      color: ss.color,
                      fontWeight: 600,
                      fontSize: '0.82rem',
                    }}>
                      {ss.label}
                    </span>
                    <span style={{ fontSize: '0.9rem', color: '#334155' }}>
                      {job.license_plate && job.license_plate !== '11111'
                        ? job.license_plate
                        : he.home.plateNotIdentified}
                    </span>
                    {job.created_at && (
                      <span style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
                        {new Date(job.created_at).toLocaleString('he-IL')}
                      </span>
                    )}
                    {job.error_message && (
                      <span style={{ fontSize: '0.82rem', color: '#dc2626', maxWidth: 260 }} title={job.error_message}>
                        {job.error_message.length > 60 ? `${job.error_message.slice(0, 60)}…` : job.error_message}
                      </span>
                    )}
                  </div>
                  {job.ticket_id ? (
                    <button
                      onClick={() => navigate(`/tickets/${job.ticket_id}`)}
                      style={{
                        padding: '6px 14px',
                        borderRadius: 8,
                        border: '1px solid #e2e8f0',
                        background: '#f8fafc',
                        color: '#1e40af',
                        cursor: 'pointer',
                        fontSize: '0.85rem',
                        fontWeight: 600,
                        fontFamily: 'inherit',
                      }}
                    >
                      {he.home.openTicket}
                    </button>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
