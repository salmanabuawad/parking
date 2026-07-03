import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LayoutDashboard, RefreshCw, Sparkles, Download } from 'lucide-react'
import { camerasApi, mapConfigApi, simulationApi } from '../api'
import CameraMap, { STATUS_META, statusOf, type MapCamera } from './CameraMap'

interface CityInfo { key: string; label: string; center: [number, number]; zoom: number; bounds: [[number, number], [number, number]] }

/** Fleet dashboard: pick a city, see its cameras as status-colored pins on the map; per-status
 *  counts double as map filters. */
export default function CameraDashboard() {
  const navigate = useNavigate()
  const [cameras, setCameras] = useState<MapCamera[]>([])
  const [cities, setCities] = useState<CityInfo[]>([])
  const [cityKey, setCityKey] = useState<string>('netanya')
  const [styleUrl, setStyleUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [warming, setWarming] = useState(false)
  const [filter, setFilter] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [cams, cfg, cityList] = await Promise.all([
        camerasApi.list(),
        mapConfigApi.get().catch(() => ({ style_url: null as string | null })),
        simulationApi.cities().catch(() => [] as CityInfo[]),
      ])
      setCameras(cams.data as MapCamera[])
      setStyleUrl((cfg as { style_url: string | null }).style_url || null)
      setCities(cityList as CityInfo[])
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const city = cities.find(c => c.key === cityKey)
  const cityCameras = useMemo(() => cameras.filter(c => (c.city || 'netanya') === cityKey), [cameras, cityKey])
  const counts = useMemo(() => {
    const m: Record<string, number> = { online: 0, offline: 0, maintenance: 0, error: 0 }
    for (const c of cityCameras) { const s = statusOf(c); m[s] = (m[s] || 0) + 1 }
    return m
  }, [cityCameras])
  const cityCount = useMemo(() => {
    const m: Record<string, number> = {}
    for (const c of cameras) { const k = c.city || 'netanya'; m[k] = (m[k] || 0) + 1 }
    return m
  }, [cameras])
  const shown = useMemo(() => (filter ? cityCameras.filter(c => statusOf(c) === filter) : cityCameras), [cityCameras, filter])

  const generate = async () => {
    if (!confirm('לייצר 100 מצלמות לדוגמה לכל עיר? מצלמות דמו קודמות יימחקו.')) return
    setBusy(true)
    try { await simulationApi.generateFleet(100); setFilter(null); await load() }
    catch (e: any) { alert(e?.message || 'שגיאה בייצור מצלמות') }
    finally { setBusy(false) }
  }

  const warmMaps = async () => {
    setWarming(true)
    try {
      const r = await mapConfigApi.warm()
      const tiles = Object.values(r.cities).reduce((a, c) => a + c.tiles, 0)
      alert(`המפות נשמרו מקומית בשרת: ${tiles} אריחים, ${(r.cache.bytes / 1024 / 1024).toFixed(1)}MB.\nמעתה המפה נטענת מהשרת — ללא קריאות ל-MapTiler.`)
    } catch (e: any) { alert(e?.message || 'שגיאה בהורדת מפות') }
    finally { setWarming(false) }
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
          <p className="page-header-label opacity-90">מצלמות וסטטוס בזמן אמת — לפי עיר</p>
        </div>
        <button onClick={warmMaps} disabled={warming} className="btn-secondary" title="מוריד ושומר את מפות הערים מקומית בשרת (חד-פעמי)">
          <Download className="w-4 h-4" /> {warming ? 'מוריד...' : 'הורד מפות'}
        </button>
        <button onClick={generate} disabled={busy} className="btn-secondary" title="יוצר 100 מצלמות דמו לכל עיר">
          <Sparkles className="w-4 h-4" /> {busy ? 'מייצר...' : 'צור מצלמות לדוגמה'}
        </button>
        <button onClick={load} disabled={loading} className="btn-icon" title="רענן"><RefreshCw className="w-4 h-4" /></button>
      </div>

      {/* City switcher */}
      {cities.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {cities.map(c => (
            <button
              key={c.key}
              onClick={() => { setCityKey(c.key); setFilter(null) }}
              className={`px-3 py-1.5 rounded-lg text-theme-sm border transition-colors ${cityKey === c.key ? 'bg-theme-accent text-white border-theme-accent' : 'border-theme-card-border text-theme-text-muted hover:bg-black/5'}`}
            >
              {c.label}{cityCount[c.key] ? <span className="opacity-80"> ({cityCount[c.key]})</span> : null}
            </button>
          ))}
        </div>
      )}

      {/* Status summary for the selected city — click to filter the map */}
      <div className="flex flex-wrap items-center gap-2">
        <Chip label="סה״כ" count={cityCameras.length} color="#334155" value={null} />
        {STATUS_META.map(s => <Chip key={s.key} label={s.label} count={counts[s.key] || 0} color={s.color} value={s.key} />)}
        {city && <span className="text-theme-sm font-semibold text-theme-text-primary ms-auto">{city.label}</span>}
      </div>

      {/* Map */}
      <div className="grid-card overflow-hidden flex-1 min-h-0 relative">
        {loading ? (
          <p className="text-theme-text-muted py-6 text-center">טוען…</p>
        ) : (
          <CameraMap
            cameras={shown}
            styleUrl={styleUrl}
            center={city?.center}
            zoom={city?.zoom}
            bounds={city?.bounds}
            onMove={moveCamera}
            onSelect={() => navigate('/cameras')}
            onEdit={() => navigate('/cameras')}
          />
        )}
      </div>
    </div>
  )
}
