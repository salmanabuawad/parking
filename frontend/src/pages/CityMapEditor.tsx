import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

/**
 * Map for defining a city: click or drag the marker to set the city center; pan/zoom to frame the
 * city — the current viewport becomes its area (bounds + zoom). Reports the full view up on every
 * change. (The RTL-text plugin is registered globally by CameraMap.)
 */

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors' } },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
}
const ISRAEL: [number, number] = [35.0, 31.6]  // [lng, lat] — country view when adding a fresh city

export interface CityView {
  center_lat: number
  center_lng: number
  zoom: number
  bounds: [[number, number], [number, number]]   // [[w, s], [e, n]]
}

export default function CityMapEditor({ initial, styleUrl, onChange }: {
  initial: { center_lat: number; center_lng: number; zoom: number } | null
  styleUrl?: string | null
  onChange: (v: CityView) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markerRef = useRef<maplibregl.Marker | null>(null)
  const onChangeRef = useRef(onChange)
  useEffect(() => { onChangeRef.current = onChange }, [onChange])

  const report = () => {
    const map = mapRef.current
    const m = markerRef.current
    if (!map || !m) return
    const p = m.getLngLat()
    const b = map.getBounds()
    onChangeRef.current({
      center_lat: +p.lat.toFixed(6),
      center_lng: +p.lng.toFixed(6),
      zoom: +map.getZoom().toFixed(2),
      bounds: [
        [+b.getWest().toFixed(6), +b.getSouth().toFixed(6)],
        [+b.getEast().toFixed(6), +b.getNorth().toFixed(6)],
      ],
    })
  }

  const placeMarker = (lat: number, lng: number) => {
    const map = mapRef.current
    if (!map) return
    if (!markerRef.current) {
      const m = new maplibregl.Marker({ color: '#2563eb', draggable: true }).setLngLat([lng, lat]).addTo(map)
      m.on('dragend', report)
      markerRef.current = m
    } else {
      markerRef.current.setLngLat([lng, lat])
    }
  }

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const has = initial != null
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: styleUrl || OSM_STYLE,
      center: has ? [initial!.center_lng, initial!.center_lat] : ISRAEL,
      zoom: has ? initial!.zoom : 7,
      dragRotate: false,
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.on('load', () => { map.resize(); report() })
    const rz = window.setTimeout(() => { map.resize(); report() }, 80)
    map.on('click', (e) => { placeMarker(e.lngLat.lat, e.lngLat.lng); report() })
    map.on('moveend', report)   // pan/zoom updates the captured area
    mapRef.current = map
    placeMarker(has ? initial!.center_lat : ISRAEL[1], has ? initial!.center_lng : ISRAEL[0])
    return () => { window.clearTimeout(rz); map.remove(); mapRef.current = null; markerRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '320px' }}
      className="rounded-lg overflow-hidden border border-theme-card-border cursor-crosshair"
    />
  )
}
