import { useState, useEffect } from 'react'
import { settingsApi } from '../api'
import { t } from '../i18n'
import { useTheme } from '../context/ThemeContext'

export default function Settings() {
  const { brightness, setBrightness, fontSize, setFontSize } = useTheme()
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
      alert((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t('failedToSave'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: 620, fontFamily: 'system-ui', color: 'var(--app-text)' }}>
      <h1>{t('settings')}</h1>
      <p style={{ color: 'var(--app-text-muted)', marginBottom: '1.5rem' }}>
        {t('settingsIntro')}
      </p>
      <div style={{ background: 'var(--app-surface)', border: '1px solid var(--app-border)', padding: '1rem', borderRadius: 10, marginBottom: '1rem' }}>
        <label style={{ display: 'block', fontWeight: 700, marginBottom: 8 }}>בהירות ותצוגה</label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          {(['normal', 'dark', 'contrast'] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setBrightness(mode)}
              style={{
                padding: '0.45rem 0.8rem',
                borderRadius: 8,
                border: '1px solid var(--app-border)',
                background: brightness === mode ? 'var(--app-accent)' : 'var(--app-surface-muted)',
                color: brightness === mode ? '#fff' : 'var(--app-text)',
                cursor: 'pointer',
              }}
            >
              {mode === 'normal' ? 'רגיל' : mode === 'dark' ? 'כהה' : 'ניגודיות גבוהה'}
            </button>
          ))}
        </div>
        <label style={{ display: 'block', fontWeight: 700, marginBottom: 8 }}>גודל פונט</label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {(['small', 'normal', 'large'] as const).map((size) => (
            <button
              key={size}
              type="button"
              onClick={() => setFontSize(size)}
              style={{
                padding: '0.45rem 0.8rem',
                borderRadius: 8,
                border: '1px solid var(--app-border)',
                background: fontSize === size ? 'var(--app-accent)' : 'var(--app-surface-muted)',
                color: fontSize === size ? '#fff' : 'var(--app-text)',
                cursor: 'pointer',
              }}
            >
              {size === 'small' ? 'קטן' : size === 'normal' ? 'רגיל' : 'גדול'}
            </button>
          ))}
        </div>
      </div>
      {settings && (
        <div style={{ background: 'var(--app-surface)', border: '1px solid var(--app-border)', padding: '1.25rem', borderRadius: 8 }}>
          <label style={{ display: 'block', fontWeight: 600, marginBottom: 8 }}>
            {t('blurKernelLabel')}
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
            {t('useViolationPipeline')}
          </label>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            style={{ padding: '0.5rem 1rem', background: 'var(--app-accent)', color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer' }}
          >
            {saving ? t('saving') : t('save')}
          </button>
        </div>
      )}
    </div>
  )
}
