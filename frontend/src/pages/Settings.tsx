import { useState, useEffect } from 'react'
import { settingsApi } from '../api'

export default function Settings() {
  const [settings, setSettings] = useState<{ blur_kernel_size: number; use_violation_pipeline: boolean } | null>(null)
  const [blurSize, setBlurSize] = useState(3)
  const [usePipeline, setUsePipeline] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    settingsApi.get().then(({ data }) => {
      setSettings(data)
      setBlurSize(data.blur_kernel_size)
      setUsePipeline(data.use_violation_pipeline)
    }).catch(() => {})
  }, [])

  const save = async () => {
    setSaving(true)
    try {
      const { data } = await settingsApi.update({ blur_kernel_size: blurSize, use_violation_pipeline: usePipeline })
      setSettings(data)
    } catch (err) {
      alert((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: 500, fontFamily: 'system-ui' }}>
      <h1>Settings</h1>
      <p style={{ color: '#666', marginBottom: '1.5rem' }}>
        Configure blur strength and violation pipeline.
      </p>
      {settings && (
        <div style={{ background: '#f8fafc', padding: '1.25rem', borderRadius: 8 }}>
          <label style={{ display: 'block', fontWeight: 600, marginBottom: 8 }}>
            Blur kernel size (0=off, 3=light, 5–51=strong)
          </label>
          <input
            type="number"
            min={0}
            max={51}
            step={2}
            value={blurSize}
            onChange={(e) => setBlurSize(Math.max(0, Math.min(99, parseInt(e.target.value, 10) || 0)))}
            style={{ width: '100%', padding: '0.5rem', marginBottom: '1rem' }}
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '1rem' }}>
            <input
              type="checkbox"
              checked={usePipeline}
              onChange={(e) => setUsePipeline(e.target.checked)}
            />
            Use violation pipeline (YOLO + selective blur)
          </label>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            style={{ padding: '0.5rem 1rem', background: '#1a1a2e', color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer' }}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      )}
    </div>
  )
}
