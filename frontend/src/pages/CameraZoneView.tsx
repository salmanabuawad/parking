import { useEffect, useRef, useState, useCallback } from 'react'
import { camerasApi, cameraSegmentsApi } from '../api'

/**
 * Read-only view of a camera's configured enforcement zones: the calibration snapshot with the
 * painted grid cells and the polygon sections drawn on top, plus a legend. No editing — use the
 * zone configurator (edit modal) to change zones. Colors match the configurator (polygons by
 * section index, grid cells by violation rule).
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

export default function CameraZoneView({ cameraId, rules }: { cameraId: number; rules: { id: string; label: string; title?: string }[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const [sections, setSections] = useState<Section[]>([])
  const [grid, setGrid] = useState<GridState | null>(null)
  const [nat, setNat] = useState<{ w: number; h: number } | null>(null)
  const [calib, setCalib] = useState<{ w: number; h: number } | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const ruleColor = (ruleId: string) => {
    const i = rules.findIndex(r => r.id === ruleId)
    return i >= 0 ? COLORS[i % COLORS.length] : '#64748b'
  }

  const loadImage = useCallback(() => {
    const img = new Image()
    img.onload = () => { imgRef.current = img; setNat({ w: img.naturalWidth, h: img.naturalHeight }); setMsg(null) }
    img.onerror = () => { imgRef.current = null; setNat(null); setMsg('אין תמונת מצלמה — הגדר תמונת כיול במסך העריכה') }
    img.src = camerasApi.snapshotUrl(cameraId) + `?t=${Date.now()}`
  }, [cameraId])

  useEffect(() => {
    (async () => {
      try {
        const [camRes, segs] = await Promise.all([camerasApi.get(cameraId), cameraSegmentsApi.list(cameraId)])
        const cam = camRes.data
        setCalib(cam.calibration_width ? { w: cam.calibration_width, h: cam.calibration_height } : null)
        setSections((segs as Section[]).map(s => ({ ...s, polygon_json: (s.polygon_json as Pt[]) || [] })))
        const zg = cam.zone_grid as { cols: number; rows: number; cells: Record<string, string | string[]> } | null | undefined
        setGrid(zg && zg.cells && Object.keys(zg.cells).length ? { cols: zg.cols, rows: zg.rows, cells: normalizeCells(zg.cells) } : null)
        loadImage()
      } catch { setMsg('שגיאה בטעינה') }
    })()
  }, [cameraId, loadImage])

  useEffect(() => {
    const canvas = canvasRef.current, img = imgRef.current
    if (!canvas || !img || !nat) return
    const displayW = Math.min(DISPLAY_W, nat.w), scale = displayW / nat.w
    canvas.width = displayW
    canvas.height = Math.round(nat.h * scale)
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    // Grid painted cells (colored by violation rule)
    if (grid) {
      const cw = canvas.width / grid.cols, ch = canvas.height / grid.rows
      for (const [key, ids] of Object.entries(grid.cells)) {
        const [c, r] = key.split(',').map(Number)
        const n = ids.length
        if (!n) continue
        // One vertical stripe per violation type painted on the cell.
        ids.forEach((rid, i) => {
          ctx.fillStyle = ruleColor(rid) + 'aa'
          ctx.fillRect(c * cw + (i * cw) / n, r * ch, cw / n + 0.5, ch)
        })
      }
    }

    // Polygon sections (colored by index) with labels
    sections.forEach((s, i) => {
      const color = COLORS[i % COLORS.length]
      const pts = (s.polygon_json || []).map(([x, y]) => [x * scale, y * scale] as Pt)
      if (pts.length < 2) return
      ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1])
      for (let j = 1; j < pts.length; j++) ctx.lineTo(pts[j][0], pts[j][1])
      ctx.closePath()
      ctx.fillStyle = color + '33'; ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.fill(); ctx.stroke()
      const cx = pts.reduce((a, p) => a + p[0], 0) / pts.length
      const cy = pts.reduce((a, p) => a + p[1], 0) / pts.length
      const label = s.label || `מקטע ${i + 1}`
      ctx.font = 'bold 13px sans-serif'
      const tw = ctx.measureText(label).width
      ctx.fillStyle = color; ctx.fillRect(cx - tw / 2 - 5, cy - 10, tw + 10, 20)
      ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(label, cx, cy)
    })
  }, [sections, grid, nat])

  const usedRules = new Set<string>()
  if (grid) Object.values(grid.cells).forEach(ids => ids.forEach(r => usedRules.add(r)))
  const resMismatch = nat && calib && (nat.w !== calib.w || nat.h !== calib.h)

  return (
    <div className="flex flex-col gap-2">
      {msg && <div className="text-theme-sm text-theme-text-muted">{msg}</div>}
      <div className="rounded-lg overflow-hidden border border-theme-card-border inline-block bg-black self-start">
        <canvas ref={canvasRef} className="block max-w-full" />
      </div>

      <div className="flex flex-wrap gap-6">
        {sections.length > 0 && (
          <div>
            <div className="text-theme-xs font-semibold mb-1">מקטעים (מצולעים)</div>
            <div className="flex flex-col gap-1">
              {sections.map((s, i) => (
                <div key={s.id} className="flex items-center gap-1 text-theme-xs">
                  <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                  {s.label || `מקטע ${i + 1}`}
                  {s.violation_rule_ids?.length ? <span className="text-theme-text-muted"> — {s.violation_rule_ids.map(id => rules.find(r => r.id === id)?.title || id).join(', ')}</span> : null}
                </div>
              ))}
            </div>
          </div>
        )}
        {grid && (
          <div>
            <div className="text-theme-xs font-semibold mb-1">רשת — סוגי עבירה</div>
            <div className="flex flex-col gap-1">
              {[...usedRules].map(rid => {
                const count = Object.values(grid.cells).filter(v => v.includes(rid)).length
                return (
                  <div key={rid} className="flex items-center gap-1 text-theme-xs" title={rules.find(r => r.id === rid)?.label || rid}>
                    <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: ruleColor(rid) }} />
                    {rules.find(r => r.id === rid)?.title || rid} <span className="text-theme-text-muted">· {count} ריבועים</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
        {sections.length === 0 && !grid && (
          <div className="text-theme-text-muted text-theme-sm">לא הוגדרו מקטעים או רשת למצלמה זו — פתח עריכה כדי להגדיר.</div>
        )}
      </div>

      {resMismatch && <div className="text-theme-xs text-amber-600">רזולוציית התצוגה ({nat!.w}×{nat!.h}) שונה מהכיול השמור ({calib!.w}×{calib!.h}).</div>}
    </div>
  )
}
