
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ticketsApi } from '../api'
import { he } from '../i18n/he'
import { useRtl } from '../hooks/useRtl'

interface Ticket {
  id: number
  license_plate: string
  location?: string
  status: string
  created_at?: string
}

export default function Tickets() {
  useRtl(`${he.tickets.title} | ${he.app.title}`)

  const [tickets, setTickets] = useState<Ticket[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)

    ticketsApi
      .list(filter || undefined)
      .then(({ data }) => setTickets(data))
      .catch((err) => {
        setTickets([])
        if (err?.response?.status === 401) setError(he.tickets.loginRequired)
        else setError(he.tickets.loadError)
      })
      .finally(() => setLoading(false))
  }, [filter])

  const badgeStyle = (status: string): React.CSSProperties => {
    if (status === 'pending_review') return { background: '#fff2d1', color: '#a16b00' }
    if (status === 'approved' || status === 'final') return { background: '#daf5e6', color: '#0f8b4c' }
    return { background: '#fde8e8', color: '#c83737' }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: 1000, margin: '0 auto' }}>
      <h1>{he.tickets.title}</h1>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '1rem' }}>
        {['', 'pending_review', 'approved', 'rejected'].map((key) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: 10,
              border: '1px solid #d7dfeb',
              background: filter === key ? '#1646a0' : '#fff',
              color: filter === key ? '#fff' : '#142033',
              cursor: 'pointer',
            }}
          >
            {he.tickets[key as keyof typeof he.tickets] || he.tickets.all}
          </button>
        ))}
      </div>

      {loading ? (
        <div>{he.tickets.loading}</div>
      ) : error ? (
        <div>{error}</div>
      ) : tickets.length === 0 ? (
        <div>{he.tickets.empty}</div>
      ) : (
        <div style={{ overflowX: 'auto', background: '#fff', border: '1px solid #d7dfeb', borderRadius: 14 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {[he.tickets.id, he.tickets.plate, he.tickets.location, he.tickets.status, he.tickets.created, he.tickets.action].map((label) => (
                  <th key={label} style={{ textAlign: 'right', padding: '0.85rem', borderBottom: '1px solid #e8edf5' }}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tickets.map((ticket) => (
                <tr key={ticket.id}>
                  <td style={{ padding: '0.85rem', borderBottom: '1px solid #f1f4f8' }}>{ticket.id}</td>
                  <td style={{ padding: '0.85rem', borderBottom: '1px solid #f1f4f8' }}>{ticket.license_plate || '—'}</td>
                  <td style={{ padding: '0.85rem', borderBottom: '1px solid #f1f4f8' }}>{ticket.location || '—'}</td>
                  <td style={{ padding: '0.85rem', borderBottom: '1px solid #f1f4f8' }}>
                    <span style={{ ...badgeStyle(ticket.status), padding: '4px 10px', borderRadius: 999 }}>
                      {he.tickets[ticket.status as keyof typeof he.tickets] || ticket.status}
                    </span>
                  </td>
                  <td style={{ padding: '0.85rem', borderBottom: '1px solid #f1f4f8' }}>
                    {ticket.created_at ? new Date(ticket.created_at).toLocaleDateString('he-IL') : '—'}
                  </td>
                  <td style={{ padding: '0.85rem', borderBottom: '1px solid #f1f4f8' }}>
                    <Link to={`/tickets/${ticket.id}`}>{he.tickets.review}</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
