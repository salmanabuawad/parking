import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

/**
 * Small map for the camera settings form: click anywhere to place the camera, or drag the pin — both
 * report the picked lat/lng back to the form. Uses the self-hosted basemap style when available, else
 * a plain OSM raster fallback. (The RTL-text plugin is registered globally by CameraMap.)
 */

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors' } },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
}
const ISRAEL: [number, number] = [35.0, 31.6] // [lng, lat] — country view for picking a fresh spot

export default function CameraLocationPicker({ lat, lng, styleUrl, onChange }: {
  lat: number | null
  lng: number | null
  styleUrl?: string | null
  onChange: (lat: number, lng: number) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markerRef = useRef<maplibregl.Marker | null>(null)
  const onChangeRef = useRef(onChange)
  useEffect(() => { onChangeRef.current = onChange }, [onChange])

  const placeMarker = (la: number, ln: number) => {
    const map = mapRef.current
    if (!map) return
    if (!markerRef.current) {
      const m = new maplibregl.Marker({ color: '#2563eb', draggable: true }).setLngLat([ln, la]).addTo(map)
      m.on('dragend', () => { const p = m.getLngLat(); onChangeRef.current(+p.lat.toFixed(6), +p.lng.toFixed(6)) })
      markerRef.current = m
    } else {
      markerRef.current.setLngLat([ln, la])
    }
  }

  // Init once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const has = lat != null && lng != null
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: styleUrl || OSM_STYLE,
      center: has ? [lng as number, lat as number] : ISRAEL,
      zoom: has ? 14 : 7,
      dragRotate: false,
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.on('load', () => map.resize())
    const rz = window.setTimeout(() => map.resize(), 60)
    map.on('click', (e) => {
      placeMarker(e.lngLat.lat, e.lngLat.lng)
      onChangeRef.current(+e.lngLat.lat.toFixed(6), +e.lngLat.lng.toFixed(6))
    })
    mapRef.current = map
    if (has) placeMarker(lat as number, lng as number)
    return () => { window.clearTimeout(rz); map.remove(); mapRef.current = null; markerRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Reflect coords typed into the form inputs onto the marker
  useEffect(() => {
    if (lat != null && lng != null) {
      placeMarker(lat, lng)
    } else if (markerRef.current) {
      markerRef.current.remove()
      markerRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, lng])

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '240px' }}
      className="rounded-lg overflow-hidden border border-theme-card-border cursor-crosshair"
    />
  )
}
