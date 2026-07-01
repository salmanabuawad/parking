import { useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { cameraSegmentsApi } from '../api'

interface Segment {
  id: number
  label: string
  violation_rule_ids?: string[] | null
  display_order: number
  is_active: boolean
}
interface RuleOpt { id: string; label: string }

export default function CameraSegmentsEditor({ cameraId, rules }: { cameraId: number; rules: RuleOpt[] }) {
  const [segments, setSegments] = useState<Segment[]>([])
  const [label, setLabel] = useState('')
  const [selRules, setSelRules] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    cameraSegmentsApi.list(cameraId).then(setSegments).catch(() => setSegments([])).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [cameraId])

  const add = async () => {
    if (!label.trim()) return
    await cameraSegmentsApi.create(cameraId, { label: label.trim(), violation_rule_ids: selRules, display_order: segments.length })
    setLabel(''); setSelRules([]); load()
  }
  const del = async (id: number) => { await cameraSegmentsApi.delete(cameraId, id); load() }
  const toggleRule = (rid: string) => setSelRules(s => (s.includes(rid) ? s.filter(x => x !== rid) : [...s, rid]))

  return (
    <div className="mt-3 border-t border-theme-card-border pt-3">
      <div className="text-theme-sm font-semibold mb-2">מקטעים ({segments.length})</div>

      {loading ? (
        <div className="text-theme-text-muted text-theme-sm">טוען...</div>
      ) : (
        <div className="flex flex-col gap-1.5 mb-2">
          {segments.map(s => (
            <div key={s.id} className="flex items-center justify-between gap-2 bg-black/5 rounded px-2 py-1">
              <div className="text-theme-sm">
                <strong>{s.label}</strong>
                {s.violation_rule_ids && s.violation_rule_ids.length > 0 && (
                  <span className="text-theme-xs text-theme-text-muted"> — {s.violation_rule_ids.join(', ')}</span>
                )}
              </div>
              <button onClick={() => del(s.id)} className="btn-icon text-red-600" title="מחק מקטע"><Trash2 className="w-4 h-4" /></button>
            </div>
          ))}
          {segments.length === 0 && <div className="text-theme-text-muted text-theme-sm">אין מקטעים</div>}
        </div>
      )}

      {/* Add a segment: label + its violation types */}
      <div className="flex flex-col gap-2 bg-black/5 rounded p-2">
        <input className="input-base" placeholder="מלל ליד המקטע" value={label} onChange={e => setLabel(e.target.value)} />
        <div className="flex flex-wrap gap-1.5">
          {rules.map(r => (
            <label key={r.id} className={`text-theme-xs rounded border px-2 py-0.5 cursor-pointer ${selRules.includes(r.id) ? 'bg-green-100 border-green-300' : 'border-theme-card-border'}`}>
              <input type="checkbox" className="me-1" checked={selRules.includes(r.id)} onChange={() => toggleRule(r.id)} />
              {r.id}
            </label>
          ))}
        </div>
        <button type="button" onClick={add} disabled={!label.trim()} className="btn-secondary self-start"><Plus className="w-4 h-4" /> הוסף מקטע</button>
      </div>
    </div>
  )
}
