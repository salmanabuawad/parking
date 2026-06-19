import { useState, useEffect } from 'react'
import { Settings as SettingsIcon } from 'lucide-react'
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
    <div className="page-container">
      {/* Page header */}
      <div className="page-header rounded-lg px-3 py-2 flex items-center gap-2">
        <span className="page-header-icon">
          <SettingsIcon className="w-5 h-5" strokeWidth={1.5} />
        </span>
        <h1 className="page-header-title">{t('settings')}</h1>
      </div>

      <p className="text-theme-text-muted">{t('settingsIntro')}</p>

      {/* Appearance */}
      <div className="app-card p-5">
        <label className="label-base text-theme-text-primary font-semibold">בהירות ותצוגה</label>
        <div className="flex flex-wrap gap-2 mb-3">
          {(['normal', 'dark', 'contrast'] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setBrightness(mode)}
              className={`px-4 py-1.5 rounded-full text-theme-sm font-medium border transition-colors ${
                brightness === mode
                  ? 'bg-theme-accent text-white border-theme-accent'
                  : 'bg-white text-theme-text-primary border-theme-card-border hover:bg-black/5'
              }`}
            >
              {mode === 'normal' ? 'רגיל' : mode === 'dark' ? 'כהה' : 'ניגודיות גבוהה'}
            </button>
          ))}
        </div>
        <label className="label-base text-theme-text-primary font-semibold">גודל פונט</label>
        <div className="flex flex-wrap gap-2">
          {(['small', 'normal', 'large'] as const).map((size) => (
            <button
              key={size}
              type="button"
              onClick={() => setFontSize(size)}
              className={`px-4 py-1.5 rounded-full text-theme-sm font-medium border transition-colors ${
                fontSize === size
                  ? 'bg-theme-accent text-white border-theme-accent'
                  : 'bg-white text-theme-text-primary border-theme-card-border hover:bg-black/5'
              }`}
            >
              {size === 'small' ? 'קטן' : size === 'normal' ? 'רגיל' : 'גדול'}
            </button>
          ))}
        </div>
      </div>

      {settings && (
        <div className="app-card p-5">
          <label className="label-base text-theme-text-primary font-semibold">{t('blurKernelLabel')}</label>
          <div className="w-64 mb-4">
            <input
              type="number"
              min={0}
              max={51}
              step={2}
              value={blurSize}
              onChange={(e) => setBlurSize(Math.max(0, Math.min(99, parseInt(e.target.value, 10) || 0)))}
              className="input-base"
            />
          </div>
          <label className="flex items-center gap-2 mb-4 text-theme-text-primary">
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
            className="btn-primary"
          >
            {saving ? t('saving') : t('save')}
          </button>
        </div>
      )}
    </div>
  )
}
