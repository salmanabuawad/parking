import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

/**
 * Cameras on a real map (OpenStreetMap raster tiles via MapLibre GL — same library the solarica
 * site map uses). Each placed camera is a draggable pin; dragging updates its lat/lng. Cameras with
 * no coordinates are listed in an overlay and can be dropped at the map center.
 */

export interface MapCamera {
  id: number
  name: string
  location?: string | null
  is_active: boolean
  latitude?: number | null
  longitude?: number | null
}

// Netanya city center [lng, lat]
const NETANYA: [number, number] = [34.8532, 32.3215]

interface Cbs {
  onMove: (id: number, lat: number, lng: number) => void
  onSelect: (cam: MapCamera) => void
  onEdit: (cam: MapCamera) => void
}

function makePopup(cam: MapCamera, cb: React.MutableRefObject<Cbs>): maplibregl.Popup {
  const node = document.createElement('div')
  node.dir = 'rtl'
  node.style.minWidth = '160px'
  const title = document.createElement('div')
  title.textContent = cam.name
  title.style.cssText = 'font-weight:600;margin-bottom:2px'
  node.appendChild(title)
  if (cam.location) {
    const loc = document.createElement('div')
    loc.textContent = cam.location
    loc.style.cssText = 'font-size:12px;color:#64748b;margin-bottom:6px'
    node.appendChild(loc)
  }
  const row = document.createElement('div')
  row.style.cssText = 'display:flex;gap:6px;margin-top:4px'
  const mk = (label: string, fn: () => void, primary = false) => {
    const b = document.createElement('button')
    b.type = 'button'; b.textContent = label
    b.style.cssText = `flex:1;font-size:12px;padding:3px 8px;border-radius:6px;cursor:pointer;border:1px solid ${primary ? '#16a34a' : '#cbd5e1'};background:${primary ? '#16a34a' : '#fff'};color:${primary ? '#fff' : '#334155'}`
    b.onclick = fn
    return b
  }
  row.appendChild(mk('צפה באזורים', () => cb.current.onSelect(cam), true))
  row.appendChild(mk('ערוך', () => cb.current.onEdit(cam)))
  node.appendChild(row)
  return new maplibregl.Popup({ offset: 26, closeButton: true }).setDOMContent(node)
}

export default function CameraMap({ cameras, onMove, onSelect, onEdit }: { cameras: MapCamera[] } & Cbs) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<Record<number, maplibregl.Marker>>({})
  const cbRef = useRef<Cbs>({ onMove, onSelect, onEdit })
  useEffect(() => { cbRef.current = { onMove, onSelect, onEdit } }, [onMove, onSelect, onEdit])

  // Init the map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
      },
      center: NETANYA,
      zoom: 13,
      dragRotate: false,
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    // Flexbox can settle the container size a tick after mount — nudge MapLibre so it doesn't
    // render into a 0-height canvas and appear blank until the first interaction.
    map.on('load', () => map.resize())
    const rz = window.setTimeout(() => map.resize(), 60)
    mapRef.current = map
    return () => { window.clearTimeout(rz); map.remove(); mapRef.current = null; markersRef.current = {} }
  }, [])

  // Rebuild markers whenever the camera set changes (few cameras → cheap + always fresh)
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    Object.values(markersRef.current).forEach(m => m.remove())
    markersRef.current = {}
    for (const c of cameras) {
      if (c.latitude == null || c.longitude == null) continue
      const m = new maplibregl.Marker({ color: c.is_active ? '#16a34a' : '#94a3b8', draggable: true })
        .setLngLat([c.longitude, c.latitude])
        .setPopup(makePopup(c, cbRef))
        .addTo(map)
      m.getElement().style.cursor = 'grab'
      m.on('dragend', () => {
        const p = m.getLngLat()
        cbRef.current.onMove(c.id, +p.lat.toFixed(6), +p.lng.toFixed(6))
      })
      markersRef.current[c.id] = m
    }
  }, [cameras])

  const unplaced = cameras.filter(c => c.latitude == null || c.longitude == null)
  const placeAtCenter = (id: number) => {
    const c = mapRef.current?.getCenter()
    if (c) cbRef.current.onMove(id, +c.lat.toFixed(6), +c.lng.toFixed(6))
  }

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="absolute inset-0" />
      {unplaced.length > 0 && (
        <div className="absolute top-2 start-2 z-10 bg-white/95 rounded-lg shadow-lg p-2 max-w-[230px] text-theme-xs" dir="rtl">
          <div className="font-semibold mb-1">מצלמות ללא מיקום ({unplaced.length})</div>
          <div className="flex flex-col gap-0.5 max-h-40 overflow-auto">
            {unplaced.map(c => (
              <button key={c.id} onClick={() => placeAtCenter(c.id)} className="text-start hover:bg-black/5 rounded px-1.5 py-1 truncate" title={c.name}>
                📍 {c.name}
              </button>
            ))}
          </div>
          <div className="text-theme-text-muted mt-1">לחץ למיקום במרכז המפה, אז גרור לכיוונון</div>
        </div>
      )}
    </div>
  )
}
