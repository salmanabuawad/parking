import { useEffect, useRef, useState, useCallback } from 'react'
import { Upload, Video, RefreshCw, Plus, Check, X, Trash2, AlertTriangle, Clapperboard } from 'lucide-react'
import { camerasApi, cameraSegmentsApi } from '../api'

/**
 * Draw enforcement sections (polygons) directly on the camera snapshot. Polygon coordinates are
 * stored in the ORIGINAL snapshot resolution (the camera's calibration_width/height); the canvas is
 * scaled to fit and clicks are converted back to original pixels before saving.
 */

const COLORS = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#ec4899', '#14b8a6', '#f97316']
const DISPLAY_W = 720

type Pt = [number, number]
interface Section {
  id: number
  label: string
  violation_rule_ids?: string[] | null
  polygon_json?: Pt[] | null
  coordinate_type?: string | null
  display_order?: number
}

function pointInPoly(p: Pt, poly: Pt[]): boolean {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1]
    if (((yi > p[1]) !== (yj > p[1])) && (p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi)) inside = !inside
  }
  return inside
}

export default function CameraZoneConfigurator({ cameraId, rules }: { cameraId: number; rules: { id: string; label: string }[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const imgFileRef = useRef<HTMLInputElement>(null)
  const vidFileRef = useRef<HTMLInputElement>(null)
  const dragRef = useRef<{ idx: number } | null>(null)

  const [sections, setSections] = useState<Section[]>([])
  const [nat, setNat] = useState<{ w: number; h: number } | null>(null)
  const [calib, setCalib] = useState<{ w: number; h: number } | null>(null)
  const [hasRtsp, setHasRtsp] = useState(false)
  const [hasSim, setHasSim] = useState(false)
  const [drawing, setDrawing] = useState<Pt[] | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const loadImage = useCallback(() => {
    const img = new Image()
    img.onload = () => { imgRef.current = img; setNat({ w: img.naturalWidth, h: img.naturalHeight }); setMsg(null) }
    img.onerror = () => { imgRef.current = null; setNat(null); setMsg('אין תמונת מצלמה — העלה תמונה/וידאו או צלם מ-RTSP') }
    img.src = camerasApi.snapshotUrl(cameraId) + `?t=${Date.now()}`
  }, [cameraId])

  const load = useCallback(async () => {
    try {
      const [camRes, segs] = await Promise.all([camerasApi.get(cameraId), cameraSegmentsApi.list(cameraId)])
      const cam = camRes.data
      setCalib(cam.calibration_width ? { w: cam.calibration_width, h: cam.calibration_height } : null)
      setHasRtsp(Boolean(cam.rtsp_url))
      setHasSim(cam.source_type === 'simulation' || Boolean(cam.connection_config?.simulation_source))
      setSections((segs as Section[]).map(s => ({ ...s, polygon_json: (s.polygon_json as Pt[]) || [] })))
      loadImage()
    } catch { setMsg('שגיאה בטעינה') }
  }, [cameraId, loadImage])

  useEffect(() => { load() }, [load])

  // ── Render ──
  useEffect(() => {
    const canvas = canvasRef.current, img = imgRef.current
    if (!canvas || !img || !nat) return
    const displayW = Math.min(DISPLAY_W, nat.w)
    const scale = displayW / nat.w
    canvas.width = displayW
    canvas.height = Math.round(nat.h * scale)
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    const poly = (pts: Pt[], color: string, sel: boolean, open = false) => {
      if (!pts.length) return
      ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1])
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1])
      if (!open) ctx.closePath()
      ctx.fillStyle = color + '33'; ctx.strokeStyle = color; ctx.lineWidth = sel ? 3 : 2
      if (!open) ctx.fill()
      ctx.stroke()
    }
    const handle = (x: number, y: number, color: string) => {
      ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2)
      ctx.fillStyle = '#fff'; ctx.fill(); ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.stroke()
    }

    sections.forEach((s, i) => {
      const color = COLORS[i % COLORS.length]
      const pts = (s.polygon_json || []).map(([x, y]) => [x * scale, y * scale] as Pt)
      poly(pts, color, s.id === selectedId)
      if (pts.length) {
        const cx = pts.reduce((a, p) => a + p[0], 0) / pts.length
        const cy = pts.reduce((a, p) => a + p[1], 0) / pts.length
        const label = s.label || `מקטע ${i + 1}`
        ctx.font = 'bold 13px sans-serif'
        const tw = ctx.measureText(label).width
        ctx.fillStyle = color; ctx.fillRect(cx - tw / 2 - 5, cy - 10, tw + 10, 20)
        ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
        ctx.fillText(label, cx, cy)
        if (s.id === selectedId) pts.forEach(p => handle(p[0], p[1], color))
      }
    })
    if (drawing) {
      const pts = drawing.map(([x, y]) => [x * scale, y * scale] as Pt)
      poly(pts, '#111827', true, true)
      pts.forEach(p => handle(p[0], p[1], '#111827'))
    }
  }, [sections, drawing, selectedId, nat])

  const toOriginal = (e: React.MouseEvent): Pt => {
    const canvas = canvasRef.current!, rect = canvas.getBoundingClientRect()
    const cx = (e.clientX - rect.left) * (canvas.width / rect.width)
    const cy = (e.clientY - rect.top) * (canvas.height / rect.height)
    const scale = canvas.width / (nat?.w || 1)
    return [Math.round(cx / scale), Math.round(cy / scale)]
  }

  const onDown = (e: React.MouseEvent) => {
    if (!nat) return
    const [x, y] = toOriginal(e)
    if (drawing) { setDrawing([...drawing, [x, y]]); return }
    const sel = sections.find(s => s.id === selectedId)
    if (sel?.polygon_json) {
      const scale = canvasRef.current!.width / nat.w
      const idx = sel.polygon_json.findIndex(([px, py]) => Math.hypot((px - x) * scale, (py - y) * scale) < 9)
      if (idx >= 0) { dragRef.current = { idx }; return }
    }
    const hit = sections.find(s => (s.polygon_json?.length ?? 0) >= 3 && pointInPoly([x, y], s.polygon_json!))
    setSelectedId(hit ? hit.id : null)
  }
  const onMove = (e: React.MouseEvent) => {
    if (!dragRef.current || selectedId == null) return
    const [x, y] = toOriginal(e)
    setSections(secs => secs.map(s => s.id === selectedId && s.polygon_json
      ? { ...s, polygon_json: s.polygon_json.map((p, i) => (i === dragRef.current!.idx ? ([x, y] as Pt) : p)) } : s))
  }
  const onUp = async () => {
    if (dragRef.current && selectedId != null) {
      const s = sections.find(x => x.id === selectedId)
      if (s) { try { await cameraSegmentsApi.update(cameraId, s.id, { polygon_json: s.polygon_json, coordinate_type: 'polygon' }) } catch { /* keep local */ } }
    }
    dragRef.current = null
  }

  const finishDrawing = async () => {
    if (!drawing || drawing.length < 3) { setMsg('נדרשות לפחות 3 נקודות'); return }
    setBusy(true)
    try {
      const created = await cameraSegmentsApi.create(cameraId, {
        label: `מקטע ${sections.length + 1}`, coordinate_type: 'polygon',
        polygon_json: drawing, display_order: sections.length,
      })
      setSections([...sections, { ...created, polygon_json: drawing }])
      setSelectedId(created.id); setDrawing(null); setMsg(null)
    } finally { setBusy(false) }
  }

  const patchSection = async (id: number, patch: Partial<Section>) => {
    setSections(secs => secs.map(s => (s.id === id ? { ...s, ...patch } : s)))
    try { await cameraSegmentsApi.update(cameraId, id, patch as Record<string, unknown>) } catch { /* keep local */ }
  }
  const removeSection = async (id: number) => {
    try { await cameraSegmentsApi.delete(cameraId, id) } catch { /* ignore */ }
    setSections(secs => secs.filter(s => s.id !== id))
    if (selectedId === id) setSelectedId(null)
  }

  const uploadFile = async (file: File) => {
    setBusy(true); setMsg('מעלה...')
    try { const r = await camerasApi.setSnapshot(cameraId, file); setCalib({ w: r.calibration_width ?? r.width, h: r.calibration_height ?? r.height }); loadImage() }
    catch (e: any) { setMsg('שגיאה: ' + (e?.message || '')) } finally { setBusy(false) }
  }
  const grabLive = async () => {
    setBusy(true); setMsg('מצלם פריים...')
    try { const r = await camerasApi.grabSnapshot(cameraId); setCalib({ w: r.calibration_width ?? r.width, h: r.calibration_height ?? r.height }); loadImage() }
    catch (e: any) { setMsg('שגיאה: ' + (e?.message || 'המקור אינו זמין')) } finally { setBusy(false) }
  }

  const resMismatch = nat && calib && (nat.w !== calib.w || nat.h !== calib.h)
  const toggleRule = (sec: Section, rid: string) => {
    const cur = sec.violation_rule_ids || []
    patchSection(sec.id, { violation_rule_ids: cur.includes(rid) ? cur.filter(r => r !== rid) : [...cur, rid] })
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Snapshot source toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-theme-sm font-semibold">תמונת מצלמה:</span>
        <button type="button" onClick={() => imgFileRef.current?.click()} disabled={busy} className="btn-secondary"><Upload className="w-4 h-4" /> תמונה</button>
        <button type="button" onClick={() => vidFileRef.current?.click()} disabled={busy} className="btn-secondary"><Video className="w-4 h-4" /> וידאו</button>
        {hasRtsp && <button type="button" onClick={grabLive} disabled={busy} className="btn-secondary">צלם RTSP</button>}
        {hasSim && <button type="button" onClick={grabLive} disabled={busy} className="btn-secondary"><Clapperboard className="w-4 h-4" /> פריים מהסימולציה</button>}
        <button type="button" onClick={loadImage} disabled={busy} className="btn-icon" title="רענן"><RefreshCw className="w-4 h-4" /></button>
        {nat && <span className="text-theme-xs text-theme-text-muted">{nat.w}×{nat.h}px</span>}
        <input ref={imgFileRef} type="file" accept="image/*" className="hidden" onChange={e => e.target.files?.[0] && uploadFile(e.target.files[0])} />
        <input ref={vidFileRef} type="file" accept="video/*" className="hidden" onChange={e => e.target.files?.[0] && uploadFile(e.target.files[0])} />
      </div>

      {resMismatch && (
        <div className="flex items-center gap-2 text-theme-sm rounded px-2 py-1 bg-amber-50 text-amber-700">
          <AlertTriangle className="w-4 h-4" /> רזולוציית התמונה ({nat!.w}×{nat!.h}) שונה מהכיול השמור ({calib!.w}×{calib!.h}) — המקטעים עשויים לא להתאים. צייר מחדש או החזר תמונה באותה רזולוציה.
        </div>
      )}
      {msg && <div className="text-theme-sm text-theme-text-muted">{msg}</div>}

      <div className="flex flex-wrap gap-3">
        {/* Canvas */}
        <div>
          <div className="rounded-lg overflow-hidden border border-theme-card-border inline-block bg-black">
            <canvas
              ref={canvasRef}
              onMouseDown={onDown}
              onMouseMove={onMove}
              onMouseUp={onUp}
              onMouseLeave={onUp}
              onDoubleClick={() => drawing && finishDrawing()}
              className="block cursor-crosshair max-w-full"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            {!drawing ? (
              <button type="button" onClick={() => { setDrawing([]); setSelectedId(null) }} disabled={!nat || busy} className="btn-primary"><Plus className="w-4 h-4" /> מקטע חדש</button>
            ) : (
              <>
                <span className="text-theme-xs text-theme-text-muted">לחץ להוספת נקודות, לחיצה כפולה לסיום ({drawing.length})</span>
                <button type="button" onClick={finishDrawing} disabled={drawing.length < 3} className="btn-success"><Check className="w-4 h-4" /> סיים</button>
                <button type="button" onClick={() => setDrawing(null)} className="btn-cancel"><X className="w-4 h-4" /> בטל</button>
              </>
            )}
          </div>
        </div>

        {/* Section list */}
        <div className="grow basis-[260px] min-w-[240px]">
          <div className="text-theme-sm font-semibold mb-2">מקטעים ({sections.length})</div>
          <div className="flex flex-col gap-2">
            {sections.map((s, i) => (
              <div
                key={s.id}
                onClick={() => setSelectedId(s.id)}
                className={`rounded border p-2 cursor-pointer ${s.id === selectedId ? 'border-theme-accent bg-black/5' : 'border-theme-card-border'}`}
              >
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                  <input
                    className="input-base flex-1"
                    value={s.label}
                    onClick={e => e.stopPropagation()}
                    onChange={e => setSections(secs => secs.map(x => (x.id === s.id ? { ...x, label: e.target.value } : x)))}
                    onBlur={e => patchSection(s.id, { label: e.target.value })}
                  />
                  <button onClick={e => { e.stopPropagation(); removeSection(s.id) }} className="btn-icon text-red-600" title="מחק"><Trash2 className="w-4 h-4" /></button>
                </div>
                {s.id === selectedId && (
                  <div className="mt-2 flex flex-wrap gap-1" onClick={e => e.stopPropagation()}>
                    {rules.map(r => (
                      <label key={r.id} className={`text-theme-xs rounded border px-1.5 py-0.5 cursor-pointer ${(s.violation_rule_ids || []).includes(r.id) ? 'bg-green-100 border-green-300' : 'border-theme-card-border'}`}>
                        <input type="checkbox" className="me-1" checked={(s.violation_rule_ids || []).includes(r.id)} onChange={() => toggleRule(s, r.id)} />
                        {r.id}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {sections.length === 0 && <div className="text-theme-text-muted text-theme-sm">אין מקטעים — לחץ "מקטע חדש" וצייר על התמונה</div>}
          </div>
        </div>
      </div>
    </div>
  )
}
