import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ticketsApi } from '../api'

interface Ticket {
  id: number
  license_plate: string
  location?: string
  status: string
  created_at?: string
}

export default function Tickets() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    ticketsApi.list(filter || undefined)
      .then(({ data }) => {
        setTickets(data)
      })
      .catch((err) => {
        setTickets([])
        if (err?.response?.status === 401) {
          setError('Please log in to view tickets.')
        } else {
          setError('Failed to load tickets.')
        }
      })
      .finally(() => setLoading(false))
  }, [filter])

  const styles: Record<string, React.CSSProperties> = {
    page: { padding: '1.5rem', maxWidth: 800, margin: '0 auto', fontFamily: 'system-ui' },
    title: { fontSize: '1.5rem', marginBottom: '1rem' },
    filter: { marginBottom: '1rem', display: 'flex', gap: 8, flexWrap: 'wrap' },
    filterBtn: { padding: '0.5rem 1rem', border: '1px solid #ccc', borderRadius: 6, background: 'white', cursor: 'pointer' },
    filterBtnActive: { background: '#1a1a2e', color: 'white', borderColor: '#1a1a2e' },
    table: { width: '100%', borderCollapse: 'collapse' },
    th: { textAlign: 'left', padding: '0.75rem', borderBottom: '2px solid #ddd' },
    td: { padding: '0.75rem', borderBottom: '1px solid #eee' },
    link: { color: '#2563eb', textDecoration: 'none' },
    badge: { padding: '0.2rem 0.5rem', borderRadius: 4, fontSize: '0.85rem' },
    badgePending: { background: '#fef3c7', color: '#92400e' },
    badgeApproved: { background: '#d1fae5', color: '#065f46' },
    badgeRejected: { background: '#fee2e2', color: '#991b1b' },
  }

  const badgeStyle = (s: string): React.CSSProperties => {
    if (s === 'pending_review') return { ...styles.badge, ...styles.badgePending }
    if (s === 'approved' || s === 'final') return { ...styles.badge, ...styles.badgeApproved }
    return { ...styles.badge, ...styles.badgeRejected }
  }

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>Tickets</h1>
      <div style={styles.filter}>
        {['', 'pending_review', 'approved', 'rejected'].map((f) => (
          <button
            key={f || 'all'}
            style={{ ...styles.filterBtn, ...(filter === f ? styles.filterBtnActive : {}) }}
            onClick={() => setFilter(f)}
          >
            {f || 'All'}
          </button>
        ))}
      </div>

      {loading ? (
        <p>Loading...</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>ID</th>
              <th style={styles.th}>Plate</th>
              <th style={styles.th}>Location</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Created</th>
              <th style={styles.th}>Action</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr key={t.id}>
                <td style={styles.td}>{t.id}</td>
                <td style={styles.td}>{t.license_plate}</td>
                <td style={styles.td}>{t.location || '-'}</td>
                <td style={styles.td}><span style={badgeStyle(t.status)}>{t.status}</span></td>
                <td style={styles.td}>{t.created_at ? new Date(t.created_at).toLocaleDateString() : '-'}</td>
                <td style={styles.td}>
                  <Link to={`/tickets/${t.id}`} style={styles.link}>Review</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!loading && error && (
        <p style={{ color: '#b91c1c', marginTop: '1rem' }}>{error}</p>
      )}
      {!loading && !error && tickets.length === 0 && (
        <p style={{ color: '#666', marginTop: '1rem' }}>No tickets found.</p>
      )}
    </div>
  )
}
