import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LayoutDashboard, RefreshCw, Sparkles } from 'lucide-react'
import { camerasApi, mapConfigApi, simulationApi } from '../api'
import CameraMap, { STATUS_META, statusOf, type MapCamera } from './CameraMap'

/** Fleet dashboard: a Netanya map with every camera as a status-colored pin, plus per-status
 *  counts that double as map filters. */
export default function CameraDashboard() {
  const navigate = useNavigate()
  const [cameras, setCameras] = useState<MapCamera[]>([])
  const [styleUrl, setStyleUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [filter, setFilter] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [cams, cfg] = await Promise.all([
        camerasApi.list(),
        mapConfigApi.get().catch(() => ({ style_url: null as string | null })),
      ])
      setCameras(cams.data as MapCamera[])
      setStyleUrl((cfg as { style_url: string | null }).style_url || null)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const counts = useMemo(() => {
    const c: Record<string, number> = { online: 0, offline: 0, maintenance: 0, error: 0 }
    for (const cam of cameras) { const s = statusOf(cam); c[s] = (c[s] || 0) + 1 }
    return c
  }, [cameras])

  const placed = useMemo(() => cameras.filter(c => c.latitude != null && c.longitude != null).length, [cameras])
  const shown = useMemo(() => (filter ? cameras.filter(c => statusOf(c) === filter) : cameras), [cameras, filter])

  const generate = async () => {
    if (!confirm('לייצר 100 מצלמות לדוגמה על מפת נתניה? מצלמות דמו קודמות יימחקו.')) return
    setBusy(true)
    try { await simulationApi.generateFleet(100); setFilter(null); await load() }
    catch (e: any) { alert(e?.message || 'שגיאה בייצור מצלמות') }
    finally { setBusy(false) }
  }

  const moveCamera = async (id: number, lat: number, lng: number) => {
    setCameras(cs => cs.map(c => (c.id === id ? { ...c, latitude: lat, longitude: lng } : c)))
    try { await camerasApi.update(id, { latitude: lat, longitude: lng }) } catch { load() }
  }

  const Chip = ({ label, count, color, value }: { label: string; count: number; color: string; value: string | null }) => (
    <button
      onClick={() => setFilter(value)}
      className={`flex items-center gap-2 rounded-lg border px-3 py-2 transition-colors ${filter === value ? 'border-theme-accent bg-theme-accent/10' : 'border-theme-card-border hover:bg-black/5'}`}
    >
      <span className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
      <span className="text-theme-sm text-theme-text-primary">{label}</span>
      <span className="text-base font-bold text-theme-text-primary">{count}</span>
    </button>
  )

  return (
    <div className="page-container">
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon"><LayoutDashboard className="w-5 h-5" strokeWidth={1.5} /></span>
        <div className="flex-1 min-w-0">
          <h1 className="page-header-title">לוח מצלמות</h1>
          <p className="page-header-label opacity-90">מפת נתניה — מצלמות וסטטוס בזמן אמת</p>
        </div>
        <button onClick={generate} disabled={busy} className="btn-secondary" title="יוצר 100 מצלמות דמו על מפת נתניה">
          <Sparkles className="w-4 h-4" /> {busy ? 'מייצר...' : 'צור 100 מצלמות'}
        </button>
        <button onClick={load} disabled={loading} className="btn-icon" title="רענן"><RefreshCw className="w-4 h-4" /></button>
      </div>

      {/* Status summary — click to filter the map */}
      <div className="flex flex-wrap items-center gap-2">
        <Chip label="סה״כ" count={cameras.length} color="#334155" value={null} />
        {STATUS_META.map(s => <Chip key={s.key} label={s.label} count={counts[s.key] || 0} color={s.color} value={s.key} />)}
        <span className="text-theme-xs text-theme-text-muted ms-auto">{placed}/{cameras.length} ממוקמות על המפה</span>
      </div>

      {/* Map */}
      <div className="grid-card overflow-hidden flex-1 min-h-0">
        {loading ? (
          <p className="text-theme-text-muted py-6 text-center">טוען…</p>
        ) : (
          <CameraMap
            cameras={shown}
            styleUrl={styleUrl}
            onMove={moveCamera}
            onSelect={() => navigate('/cameras')}
            onEdit={() => navigate('/cameras')}
          />
        )}
      </div>
    </div>
  )
}
