import { useEffect, useRef, useState, useCallback } from 'react'
import { Upload, Video, RefreshCw, Plus, Check, X, Trash2, AlertTriangle, Clapperboard, Grid3x3, Eraser } from 'lucide-react'
import { camerasApi, cameraSegmentsApi } from '../api'

/**
 * Draw enforcement sections (polygons) directly on the camera snapshot. Polygon coordinates are
 * stored in the ORIGINAL snapshot resolution (the camera's calibration_width/height); the canvas is
 * scaled to fit and clicks are converted back to original pixels before saving.
 */

const COLORS = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#ec4899', '#14b8a6', '#f97316']
const DISPLAY_W = 720

type Pt = [number, number]
// A cell maps to a list of violation rule-ids (0/1/many painted on the same square).
type GridState = { cols: number; rows: number; cells: Record<string, string[]> }
interface Section {
  id: number
  label: string
  violation_rule_ids?: string[] | null
  polygon_json?: Pt[] | null
  coordinate_type?: string | null
  display_order?: number
}

// Cells may load in the legacy single-string shape; normalize every cell to a rule-id array.
function normalizeCells(cells: Record<string, string | string[]> | undefined | null): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const [k, v] of Object.entries(cells || {})) {
    const arr = Array.isArray(v) ? v.filter(Boolean) : v ? [v] : []
    if (arr.length) out[k] = arr
  }
  return out
}

function pointInPoly(p: Pt, poly: Pt[]): boolean {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1]
    if (((yi > p[1]) !== (yj > p[1])) && (p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi)) inside = !inside
  }
  return inside
}

export default function CameraZoneConfigurator({ cameraId, rules }: { cameraId: number; rules: { id: string; label: string; title?: string }[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const objUrlRef = useRef<string | null>(null)
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
  const [newZoneRules, setNewZoneRules] = useState<string[]>([])   // marked violation-type group → applied to the next new zone

  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<'polygon' | 'grid'>('polygon')
  const [grid, setGrid] = useState<GridState>({ cols: 24, rows: 14, cells: {} })
  const [activeRule, setActiveRule] = useState<string | null>(rules[0]?.id ?? null)
  const paintingRef = useRef(false)
  // Whole-drag action, decided on mouse-down from the first cell: add/remove the active rule, or clear.
  const paintModeRef = useRef<'add' | 'remove' | 'clear'>('add')
  const gridRef = useRef<GridState>(grid)

  // Each violation rule gets a stable color (shared with the polygon sections palette).
  const ruleColor = (ruleId: string) => {
    const i = rules.findIndex(r => r.id === ruleId)
    return i >= 0 ? COLORS[i % COLORS.length] : '#64748b'
  }

  const noImg = () => { imgRef.current = null; setNat(null); setMsg('אין תמונת מצלמה — העלה תמונה/וידאו או צלם מ-RTSP') }
  const loadImage = useCallback(async () => {
    try {
      const url = await camerasApi.snapshotObjectUrl(cameraId)   // fetched with auth (img tags can't)
      if (objUrlRef.current) URL.revokeObjectURL(objUrlRef.current)
      objUrlRef.current = url
      const img = new Image()
      img.onload = () => { imgRef.current = img; setNat({ w: img.naturalWidth, h: img.naturalHeight }); setMsg(null) }
      img.onerror = noImg
      img.src = url
    } catch { noImg() }
  }, [cameraId])
  useEffect(() => () => { if (objUrlRef.current) URL.revokeObjectURL(objUrlRef.current) }, [])

  const load = useCallback(async () => {
    try {
      const [camRes, segs] = await Promise.all([camerasApi.get(cameraId), cameraSegmentsApi.list(cameraId)])
      const cam = camRes.data
      setCalib(cam.calibration_width ? { w: cam.calibration_width, h: cam.calibration_height } : null)
      setHasRtsp(Boolean(cam.rtsp_url))
      setHasSim(cam.source_type === 'simulation' || Boolean(cam.connection_config?.simulation_source))
      setSections((segs as Section[]).map(s => ({ ...s, polygon_json: (s.polygon_json as Pt[]) || [] })))
      const zg = cam.zone_grid as { cols: number; rows: number; cells: Record<string, string | string[]> } | null | undefined
      if (zg && zg.cells && Object.keys(zg.cells).length) {
        setGrid({ cols: zg.cols, rows: zg.rows, cells: normalizeCells(zg.cells) })
        setMode('grid')
      } else if (cam.calibration_width && cam.calibration_height) {
        const cols = 24
        setGrid({ cols, rows: Math.max(4, Math.round((cols * cam.calibration_height) / cam.calibration_width)), cells: {} })
      }
      loadImage()
    } catch { setMsg('שגיאה בטעינה') }
  }, [cameraId, loadImage])

  useEffect(() => { load() }, [load])
  useEffect(() => { gridRef.current = grid }, [grid])

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

    if (mode === 'grid') {
      const cw = canvas.width / grid.cols, ch = canvas.height / grid.rows
      for (const [key, ids] of Object.entries(grid.cells)) {
        const [c, r] = key.split(',').map(Number)
        const n = ids.length
        if (!n) continue
        // Split the cell into one vertical stripe per violation type painted on it.
        ids.forEach((rid, i) => {
          ctx.fillStyle = ruleColor(rid) + 'aa'
          ctx.fillRect(c * cw + (i * cw) / n, r * ch, cw / n + 0.5, ch)
        })
      }
      ctx.strokeStyle = 'rgba(255,255,255,0.30)'; ctx.lineWidth = 1; ctx.beginPath()
      for (let c = 0; c <= grid.cols; c++) { ctx.moveTo(c * cw, 0); ctx.lineTo(c * cw, canvas.height) }
      for (let r = 0; r <= grid.rows; r++) { ctx.moveTo(0, r * ch); ctx.lineTo(canvas.width, r * ch) }
      ctx.stroke()
      return
    }

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
  }, [sections, drawing, selectedId, nat, mode, grid])

  const toOriginal = (e: React.MouseEvent): Pt => {
    const canvas = canvasRef.current!, rect = canvas.getBoundingClientRect()
    const cx = (e.clientX - rect.left) * (canvas.width / rect.width)
    const cy = (e.clientY - rect.top) * (canvas.height / rect.height)
    const scale = canvas.width / (nat?.w || 1)
    return [Math.round(cx / scale), Math.round(cy / scale)]
  }

  // ── Grid painting ──
  const cellAt = (e: React.MouseEvent): [number, number] => {
    const canvas = canvasRef.current!, rect = canvas.getBoundingClientRect()
    const cx = (e.clientX - rect.left) * (canvas.width / rect.width)
    const cy = (e.clientY - rect.top) * (canvas.height / rect.height)
    const c = Math.floor(cx / (canvas.width / grid.cols))
    const r = Math.floor(cy / (canvas.height / grid.rows))
    return [Math.max(0, Math.min(grid.cols - 1, c)), Math.max(0, Math.min(grid.rows - 1, r))]
  }
  const paintAt = (e: React.MouseEvent) => {
    const [c, r] = cellAt(e), key = `${c},${r}`
    const pm = paintModeRef.current
    setGrid(g => {
      const cells = { ...g.cells }
      const cur = cells[key] || []
      if (pm === 'clear') {
        if (!(key in cells)) return g
        delete cells[key]                                   // eraser: remove all types from the cell
      } else if (pm === 'add') {
        if (!activeRule || cur.includes(activeRule)) return g
        cells[key] = [...cur, activeRule]                   // layer the active type onto the cell
      } else {
        if (!activeRule || !cur.includes(activeRule)) return g
        const next = cur.filter(x => x !== activeRule)      // remove just the active type
        if (next.length) cells[key] = next; else delete cells[key]
      }
      return { ...g, cells }
    })
  }
  const saveGrid = async (g?: GridState) => {
    try { await camerasApi.saveZoneGrid(cameraId, g ?? gridRef.current) }
    catch (e: any) { setMsg('שגיאה בשמירת רשת: ' + (e?.message || '')) }
  }
  const changeCols = (cols: number) => {
    const aspectW = calib?.w ?? nat?.w ?? 16, aspectH = calib?.h ?? nat?.h ?? 9
    const rows = Math.max(4, Math.round((cols * aspectH) / aspectW))
    const cells: Record<string, string[]> = {}
    for (const [key, ids] of Object.entries(grid.cells)) {
      const [c, r] = key.split(',').map(Number)
      const nc = Math.min(cols - 1, Math.floor(((c + 0.5) / grid.cols) * cols))
      const nr = Math.min(rows - 1, Math.floor(((r + 0.5) / grid.rows) * rows))
      const k = `${nc},${nr}`
      cells[k] = [...new Set([...(cells[k] || []), ...ids])]
    }
    const next = { cols, rows, cells }; setGrid(next); saveGrid(next)
  }
  const clearGrid = () => { const next = { ...grid, cells: {} }; setGrid(next); saveGrid(next) }

  const onDown = (e: React.MouseEvent) => {
    if (mode === 'grid') {
      paintingRef.current = true
      const [c, r] = cellAt(e)
      const cur = grid.cells[`${c},${r}`] || []
      // Decide the drag action from the first cell so dragging paints (or unpaints) consistently.
      paintModeRef.current = activeRule == null ? 'clear' : cur.includes(activeRule) ? 'remove' : 'add'
      paintAt(e)
      return
    }
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
    if (mode === 'grid') { if (paintingRef.current) paintAt(e); return }
    if (!dragRef.current || selectedId == null) return
    const [x, y] = toOriginal(e)
    setSections(secs => secs.map(s => s.id === selectedId && s.polygon_json
      ? { ...s, polygon_json: s.polygon_json.map((p, i) => (i === dragRef.current!.idx ? ([x, y] as Pt) : p)) } : s))
  }
  const onUp = async () => {
    if (mode === 'grid') { if (paintingRef.current) { paintingRef.current = false; await saveGrid() } return }
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
        violation_rule_ids: newZoneRules,   // new zone carries the marked group (#4)
      })
      setSections([...sections, { ...created, polygon_json: drawing, violation_rule_ids: newZoneRules }])
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
      {/* Marking method: freehand polygons or paint grid squares */}
      <div className="flex flex-wrap items-center gap-1">
        <span className="text-theme-sm font-semibold ms-1">שיטת סימון:</span>
        <button type="button" onClick={() => setMode('polygon')} className={mode === 'polygon' ? 'btn-primary' : 'btn-secondary'}>מצולעים</button>
        <button type="button" onClick={() => setMode('grid')} className={mode === 'grid' ? 'btn-primary' : 'btn-secondary'}><Grid3x3 className="w-4 h-4" /> ריבועים</button>
      </div>

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
          {mode === 'polygon' && (
            <div className="flex flex-col gap-2 mt-2">
              {/* Mark violation types (a group) → the next new zone is created carrying them (#4). */}
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-theme-xs font-semibold">סוגי עבירה לאזור חדש:</span>
                {rules.map(r => {
                  const on = newZoneRules.includes(r.id)
                  return (
                    <button key={r.id} type="button" title={r.label}
                      onClick={() => setNewZoneRules(g => on ? g.filter(x => x !== r.id) : [...g, r.id])}
                      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-theme-xs max-w-[180px] ${on ? 'bg-green-100 border-green-400' : 'border-theme-card-border'}`}>
                      <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: ruleColor(r.id) }} />
                      <span className="truncate min-w-0">{r.title || r.id}</span>
                      {on && <Check className="w-3 h-3 shrink-0 text-green-700" />}
                    </button>
                  )
                })}
                {rules.length === 0 && <span className="text-theme-xs text-amber-600">אין כללי הפרה</span>}
                {newZoneRules.length > 0 && (
                  <button type="button" onClick={() => setNewZoneRules([])} className="text-theme-xs text-theme-text-muted underline">נקה בחירה</button>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {!drawing ? (
                  <button type="button" onClick={() => { setDrawing([]); setSelectedId(null) }} disabled={!nat || busy} className="btn-primary"><Plus className="w-4 h-4" /> מקטע חדש{newZoneRules.length ? ` (${newZoneRules.length} סוגי עבירה)` : ''}</button>
                ) : (
                  <>
                    <span className="text-theme-xs text-theme-text-muted">לחץ להוספת נקודות, לחיצה כפולה לסיום ({drawing.length}){newZoneRules.length ? ` · האזור ייווצר עם ${newZoneRules.length} סוגי עבירה` : ''}</span>
                    <button type="button" onClick={finishDrawing} disabled={drawing.length < 3} className="btn-success"><Check className="w-4 h-4" /> סיים</button>
                    <button type="button" onClick={() => setDrawing(null)} className="btn-cancel"><X className="w-4 h-4" /> בטל</button>
                  </>
                )}
              </div>
            </div>
          )}
          {mode === 'grid' && (
            <div className="flex flex-col gap-2 mt-2">
              <div className="text-theme-xs text-theme-text-muted">בחר סוג עבירה (צבע) וצבע על הריבועים בגרירה. אפשר לצבוע כמה סוגים על אותו ריבוע (מוצגים כפסים) — צביעה חוזרת עם אותו סוג מסירה אותו. בחר "מחק" לניקוי ריבוע. השמירה אוטומטית.</div>
              <div className="flex flex-wrap items-center gap-1.5">
                {rules.map(r => {
                  const count = Object.values(grid.cells).filter(v => v.includes(r.id)).length
                  return (
                    <button key={r.id} type="button" onClick={() => setActiveRule(r.id)} title={r.label}
                      className={`flex items-center gap-1 rounded border px-2 py-1 text-theme-xs max-w-[180px] ${activeRule === r.id ? 'ring-2 ring-theme-accent' : ''}`}
                      style={{ borderColor: ruleColor(r.id) }}>
                      <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: ruleColor(r.id) }} />
                      <span className="truncate min-w-0">{r.title || r.id}</span>
                      {count ? <span className="shrink-0 text-theme-text-muted">· {count}</span> : null}
                    </button>
                  )
                })}
                <button type="button" onClick={() => setActiveRule(null)}
                  className={`flex items-center gap-1 rounded border px-2 py-1 text-theme-xs ${activeRule === null ? 'ring-2 ring-theme-accent border-gray-400' : 'border-theme-card-border'}`}>
                  <Eraser className="w-3.5 h-3.5" /> מחק
                </button>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-theme-xs text-theme-text-muted">צפיפות:</label>
                <select value={grid.cols} onChange={e => changeCols(parseInt(e.target.value))} className="input-base w-28">
                  {[12, 16, 24, 32, 40].map(n => <option key={n} value={n}>{n} עמודות</option>)}
                </select>
                <span className="text-theme-xs text-theme-text-muted">{grid.cols}×{grid.rows}</span>
                <button type="button" onClick={clearGrid} className="btn-cancel"><Trash2 className="w-4 h-4" /> נקה רשת</button>
              </div>
              {rules.length === 0 && <div className="text-theme-xs text-amber-600">לא הוגדרו כללי הפרה — הוסף כללים כדי לצבוע לפי סוג עבירה.</div>}
            </div>
          )}
        </div>

        {/* Section list (polygon mode only) */}
        {mode === 'polygon' && (
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
                      <label key={r.id} title={r.label} className={`inline-flex items-center max-w-[190px] text-theme-xs rounded border px-1.5 py-0.5 cursor-pointer ${(s.violation_rule_ids || []).includes(r.id) ? 'bg-green-100 border-green-300' : 'border-theme-card-border'}`}>
                        <input type="checkbox" className="me-1 shrink-0" checked={(s.violation_rule_ids || []).includes(r.id)} onChange={() => toggleRule(s, r.id)} />
                        <span className="truncate min-w-0">{r.title || r.id}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {sections.length === 0 && <div className="text-theme-text-muted text-theme-sm">אין מקטעים — לחץ "מקטע חדש" וצייר על התמונה</div>}
          </div>
        </div>
        )}
      </div>
    </div>
  )
}
