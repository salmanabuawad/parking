import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, ArrowUp, ArrowDown } from 'lucide-react'
import { settingsApi, simulationApi } from '../api'
import { t } from '../i18n'
import { useTheme } from '../context/ThemeContext'

export default function Settings() {
  const { brightness, setBrightness, fontSize, setFontSize } = useTheme()
  const [settings, setSettings] = useState<{
    blur_kernel_size: number
    use_violation_pipeline: boolean
    vehicle_registry_api_enabled: boolean
    vehicle_registry_api_url: string
    vehicle_registry_resource_id: string
    vehicle_registry_plate_field: string
    vehicle_registry_timeout_seconds: number
    vehicle_registry_cache_ttl_hours: number
  } | null>(null)
  const [blurSize, setBlurSize] = useState(3)
  const [usePipeline, setUsePipeline] = useState(false)
  const [vehicleRegistryEnabled, setVehicleRegistryEnabled] = useState(true)
  const [vehicleRegistryApiUrl, setVehicleRegistryApiUrl] = useState('')
  const [vehicleRegistryResourceId, setVehicleRegistryResourceId] = useState('')
  const [vehicleRegistryPlateField, setVehicleRegistryPlateField] = useState('mispar_rechev')
  const [vehicleRegistryTimeoutSeconds, setVehicleRegistryTimeoutSeconds] = useState(10)
  const [vehicleRegistryCacheTtlHours, setVehicleRegistryCacheTtlHours] = useState(24)
  const [violationDwellSeconds, setViolationDwellSeconds] = useState(300)
  const [requiredVideoSeconds, setRequiredVideoSeconds] = useState(10)
  const [videoRetentionDays, setVideoRetentionDays] = useState(90)
  const [videoTimestampOverlay, setVideoTimestampOverlay] = useState(true)
  const [blurExpandRatio, setBlurExpandRatio] = useState(0.18)
  const [evidencePreSeconds, setEvidencePreSeconds] = useState(5)
  const [evidencePostSeconds, setEvidencePostSeconds] = useState(5)
  const [originalRetentionDays, setOriginalRetentionDays] = useState(180)
  const [processedRetentionDays, setProcessedRetentionDays] = useState(90)
  const [candidateRetentionDays, setCandidateRetentionDays] = useState(365)
  const [saving, setSaving] = useState(false)
  const [cityList, setCityList] = useState<{ key: string; label: string }[]>([])
  const [savingCities, setSavingCities] = useState(false)

  useEffect(() => {
    settingsApi.get().then(({ data }) => {
      setSettings(data)
      setBlurSize(data.blur_kernel_size)
      setUsePipeline(data.use_violation_pipeline)
      setVehicleRegistryEnabled(data.vehicle_registry_api_enabled ?? true)
      setVehicleRegistryApiUrl(data.vehicle_registry_api_url ?? '')
      setVehicleRegistryResourceId(data.vehicle_registry_resource_id ?? '')
      setVehicleRegistryPlateField(data.vehicle_registry_plate_field ?? 'mispar_rechev')
      setVehicleRegistryTimeoutSeconds(data.vehicle_registry_timeout_seconds ?? 10)
      setVehicleRegistryCacheTtlHours(data.vehicle_registry_cache_ttl_hours ?? 24)
      setViolationDwellSeconds(data.violation_dwell_seconds ?? 300)
      setRequiredVideoSeconds(data.required_video_seconds ?? 10)
      setVideoRetentionDays(data.video_retention_days ?? 90)
      setVideoTimestampOverlay(data.video_timestamp_overlay ?? true)
      setBlurExpandRatio(data.blur_expand_ratio ?? 0.18)
      setEvidencePreSeconds(data.evidence_video_pre_seconds ?? 5)
      setEvidencePostSeconds(data.evidence_video_post_seconds ?? 5)
      setOriginalRetentionDays(data.original_video_retention_days ?? 180)
      setProcessedRetentionDays(data.processed_video_retention_days ?? 90)
      setCandidateRetentionDays(data.ticket_candidate_retention_days ?? 365)
    }).catch(() => {})
  }, [])

  // Cities come back in the currently-saved order; the card below lets the admin reorder them.
  useEffect(() => {
    simulationApi.cities()
      .then((cs) => setCityList(cs.map((c) => ({ key: c.key, label: c.label }))))
      .catch(() => {})
  }, [])

  const moveCity = (idx: number, dir: -1 | 1) => {
    setCityList((prev) => {
      const j = idx + dir
      if (j < 0 || j >= prev.length) return prev
      const next = [...prev]
      ;[next[idx], next[j]] = [next[j], next[idx]]
      return next
    })
  }

  const saveCityOrder = async () => {
    setSavingCities(true)
    try {
      await settingsApi.update({ city_order: cityList.map((c) => c.key) })
    } catch (err) {
      alert((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t('failedToSave'))
    } finally {
      setSavingCities(false)
    }
  }

  const save = async () => {
    setSaving(true)
    try {
      const { data } = await settingsApi.update({
        blur_kernel_size: blurSize,
        use_violation_pipeline: usePipeline,
        vehicle_registry_api_enabled: vehicleRegistryEnabled,
        vehicle_registry_api_url: vehicleRegistryApiUrl,
        vehicle_registry_resource_id: vehicleRegistryResourceId,
        vehicle_registry_plate_field: vehicleRegistryPlateField,
        vehicle_registry_timeout_seconds: vehicleRegistryTimeoutSeconds,
        vehicle_registry_cache_ttl_hours: vehicleRegistryCacheTtlHours,
        violation_dwell_seconds: violationDwellSeconds,
        required_video_seconds: requiredVideoSeconds,
        video_retention_days: videoRetentionDays,
        video_timestamp_overlay: videoTimestampOverlay,
        blur_expand_ratio: blurExpandRatio,
        evidence_video_pre_seconds: evidencePreSeconds,
        evidence_video_post_seconds: evidencePostSeconds,
        original_video_retention_days: originalRetentionDays,
        processed_video_retention_days: processedRetentionDays,
        ticket_candidate_retention_days: candidateRetentionDays,
      })
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
        <div className="app-card p-5 space-y-4">
          <label className="label-base text-theme-text-primary font-semibold">הגדרות אכיפה ומערכת</label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="label-base text-theme-text-primary">זמן שהייה שנחשב לעבירה (שניות)</label>
              <input type="number" min={0} value={violationDwellSeconds}
                onChange={(e) => setViolationDwellSeconds(Math.max(0, parseInt(e.target.value, 10) || 0))} className="input-base" />
            </div>
            <div>
              <label className="label-base text-theme-text-primary">אורך סרטון נדרש (שניות)</label>
              <input type="number" min={0} value={requiredVideoSeconds}
                onChange={(e) => setRequiredVideoSeconds(Math.max(0, parseInt(e.target.value, 10) || 0))} className="input-base" />
            </div>
            <div>
              <label className="label-base text-theme-text-primary">שניות הקלטה לפני העבירה</label>
              <input type="number" min={0} max={120} value={evidencePreSeconds}
                onChange={(e) => setEvidencePreSeconds(Math.max(0, Math.min(120, parseInt(e.target.value, 10) || 0)))} className="input-base" />
            </div>
            <div>
              <label className="label-base text-theme-text-primary">שניות הקלטה אחרי העבירה</label>
              <input type="number" min={0} max={120} value={evidencePostSeconds}
                onChange={(e) => setEvidencePostSeconds(Math.max(0, Math.min(120, parseInt(e.target.value, 10) || 0)))} className="input-base" />
            </div>
            <div>
              <label className="label-base text-theme-text-primary">שמירת סרטונים (ימים)</label>
              <input type="number" min={0} value={videoRetentionDays}
                onChange={(e) => setVideoRetentionDays(Math.max(0, parseInt(e.target.value, 10) || 0))} className="input-base" />
            </div>
            <div>
              <label className="label-base text-theme-text-primary">שמירת סרטון מקור (ימים)</label>
              <input type="number" min={0} value={originalRetentionDays}
                onChange={(e) => setOriginalRetentionDays(Math.max(0, parseInt(e.target.value, 10) || 0))} className="input-base" />
            </div>
            <div>
              <label className="label-base text-theme-text-primary">שמירת סרטון מעובד (ימים)</label>
              <input type="number" min={0} value={processedRetentionDays}
                onChange={(e) => setProcessedRetentionDays(Math.max(0, parseInt(e.target.value, 10) || 0))} className="input-base" />
            </div>
            <div>
              <label className="label-base text-theme-text-primary">שמירת מועמדים לדוח (ימים)</label>
              <input type="number" min={0} value={candidateRetentionDays}
                onChange={(e) => setCandidateRetentionDays(Math.max(0, parseInt(e.target.value, 10) || 0))} className="input-base" />
            </div>
            <label className="flex items-center gap-2 text-theme-text-primary self-end pb-2">
              <input type="checkbox" checked={videoTimestampOverlay} onChange={(e) => setVideoTimestampOverlay(e.target.checked)} />
              הצג תאריך ושעה בסרטון
            </label>
          </div>
          <button type="button" onClick={save} disabled={saving} className="btn-primary">
            {saving ? t('saving') : t('save')}
          </button>
        </div>
      )}

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
          <div className="w-64 mb-4">
            <label className="label-base text-theme-text-primary">יחס הרחבת אזור הטשטוש (0–1)</label>
            <input
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={blurExpandRatio}
              onChange={(e) => setBlurExpandRatio(Math.max(0, Math.min(1, parseFloat(e.target.value) || 0)))}
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
          <div className="border-t border-theme-card-border pt-4 mt-4">
            <label className="flex items-center gap-2 mb-4 text-theme-text-primary">
              <input
                type="checkbox"
                checked={vehicleRegistryEnabled}
                onChange={(e) => setVehicleRegistryEnabled(e.target.checked)}
              />
              אפשר חיפוש במרשם הרכבים הישראלי
            </label>

            <label className="label-base text-theme-text-primary font-semibold">כתובת API של data.gov.il</label>
            <input
              type="url"
              value={vehicleRegistryApiUrl}
              onChange={(e) => setVehicleRegistryApiUrl(e.target.value)}
              className="input-base mb-3"
              dir="ltr"
            />

            <label className="label-base text-theme-text-primary font-semibold">מזהה משאב (Resource ID)</label>
            <input
              type="text"
              value={vehicleRegistryResourceId}
              onChange={(e) => setVehicleRegistryResourceId(e.target.value)}
              className="input-base mb-3"
              dir="ltr"
            />

            <label className="label-base text-theme-text-primary font-semibold">שם שדה מספר הרכב</label>
            <input
              type="text"
              value={vehicleRegistryPlateField}
              onChange={(e) => setVehicleRegistryPlateField(e.target.value)}
              className="input-base mb-3"
              dir="ltr"
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
              <div>
                <label className="label-base text-theme-text-primary font-semibold">פסק זמן (שניות)</label>
                <input
                  type="number"
                  min={1}
                  max={60}
                  value={vehicleRegistryTimeoutSeconds}
                  onChange={(e) => setVehicleRegistryTimeoutSeconds(Math.max(1, Math.min(60, parseInt(e.target.value, 10) || 10)))}
                  className="input-base"
                />
              </div>
              <div>
                <label className="label-base text-theme-text-primary font-semibold">תוקף מטמון (שעות)</label>
                <input
                  type="number"
                  min={1}
                  max={720}
                  value={vehicleRegistryCacheTtlHours}
                  onChange={(e) => setVehicleRegistryCacheTtlHours(Math.max(1, Math.min(720, parseInt(e.target.value, 10) || 24)))}
                  className="input-base"
                />
              </div>
            </div>
          </div>

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

      {/* City order — controls the order of cities in the fleet dashboard + camera dropdowns */}
      {cityList.length > 0 && (
        <div className="app-card p-5 space-y-3">
          <div>
            <label className="label-base text-theme-text-primary font-semibold">סדר הערים ברשימות</label>
            <p className="text-theme-text-muted text-theme-sm">קובע את סדר הערים בתפריטי הבחירה (לוח המצלמות, הגדרת מצלמה).</p>
          </div>
          <ul className="flex flex-col gap-2 max-w-sm">
            {cityList.map((c, i) => (
              <li key={c.key} className="flex items-center gap-2 rounded-lg border border-theme-card-border px-3 py-2">
                <span className="w-6 text-theme-text-muted text-theme-sm">{i + 1}.</span>
                <span className="flex-1 text-theme-text-primary">{c.label}</span>
                <button type="button" onClick={() => moveCity(i, -1)} disabled={i === 0}
                  className="btn-icon disabled:opacity-30" title="הזז למעלה"><ArrowUp className="w-4 h-4" /></button>
                <button type="button" onClick={() => moveCity(i, 1)} disabled={i === cityList.length - 1}
                  className="btn-icon disabled:opacity-30" title="הזז למטה"><ArrowDown className="w-4 h-4" /></button>
              </li>
            ))}
          </ul>
          <button type="button" onClick={saveCityOrder} disabled={savingCities} className="btn-primary">
            {savingCities ? t('saving') : t('save')}
          </button>
        </div>
      )}
    </div>
  )
}
