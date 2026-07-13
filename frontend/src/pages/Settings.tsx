import { useState, useEffect, type ReactNode } from 'react'
import { Settings as SettingsIcon, SlidersHorizontal, MapPin } from 'lucide-react'
import { settingsApi } from '../api'
import { t } from '../i18n'
import { useTheme } from '../context/ThemeContext'
import CityManager from './CityManager'

type Tab = 'system' | 'cities'

const TABS: { key: Tab; label: string; icon: ReactNode }[] = [
  { key: 'system', label: 'מערכת', icon: <SlidersHorizontal className="w-4 h-4" /> },
  { key: 'cities', label: 'ערים ומפות', icon: <MapPin className="w-4 h-4" /> },
]

export default function Settings() {
  const { brightness, setBrightness, fontSize, setFontSize } = useTheme()
  const [tab, setTab] = useState<Tab>('system')
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
  const [blurExceptPlate, setBlurExceptPlate] = useState(true)
  const [evidencePreSeconds, setEvidencePreSeconds] = useState(5)
  const [evidencePostSeconds, setEvidencePostSeconds] = useState(5)
  const [originalRetentionDays, setOriginalRetentionDays] = useState(180)
  const [processedRetentionDays, setProcessedRetentionDays] = useState(90)
  const [candidateRetentionDays, setCandidateRetentionDays] = useState(365)
  const [minVideoSeconds, setMinVideoSeconds] = useState(3)
  const [maxVideoSeconds, setMaxVideoSeconds] = useState(120)
  const [dupWindowSeconds, setDupWindowSeconds] = useState(300)
  const [tsPosition, setTsPosition] = useState('top_right')
  const [plateInset, setPlateInset] = useState(true)
  const [pendingColor, setPendingColor] = useState('#00FF00')
  const [approvedColor, setApprovedColor] = useState('#FF0000')
  const [saving, setSaving] = useState(false)

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
      setBlurExceptPlate(data.blur_except_plate ?? true)
      setEvidencePreSeconds(data.evidence_video_pre_seconds ?? 5)
      setEvidencePostSeconds(data.evidence_video_post_seconds ?? 5)
      setOriginalRetentionDays(data.original_video_retention_days ?? 180)
      setProcessedRetentionDays(data.processed_video_retention_days ?? 90)
      setCandidateRetentionDays(data.ticket_candidate_retention_days ?? 365)
      setMinVideoSeconds(data.min_video_seconds ?? 3)
      setMaxVideoSeconds(data.max_video_seconds ?? 120)
      setDupWindowSeconds(data.duplicate_ticket_window_seconds ?? 300)
      setTsPosition(data.timestamp_overlay_position ?? 'top_right')
      setPlateInset(data.plate_inset_enabled ?? true)
      setPendingColor(data.pending_frame_color ?? '#00FF00')
      setApprovedColor(data.approved_frame_color ?? '#FF0000')
    }).catch(() => {})
  }, [])

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
        blur_except_plate: blurExceptPlate,
        evidence_video_pre_seconds: evidencePreSeconds,
        evidence_video_post_seconds: evidencePostSeconds,
        original_video_retention_days: originalRetentionDays,
        processed_video_retention_days: processedRetentionDays,
        ticket_candidate_retention_days: candidateRetentionDays,
        min_video_seconds: minVideoSeconds,
        max_video_seconds: maxVideoSeconds,
        duplicate_ticket_window_seconds: dupWindowSeconds,
        timestamp_overlay_position: tsPosition,
        plate_inset_enabled: plateInset,
        pending_frame_color: pendingColor,
        approved_frame_color: approvedColor,
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

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-theme-card-border">
        {TABS.map((tb) => (
          <button
            key={tb.key}
            type="button"
            onClick={() => setTab(tb.key)}
            className={`flex items-center gap-1.5 px-4 py-2 text-theme-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === tb.key
                ? 'border-theme-accent text-theme-accent'
                : 'border-transparent text-theme-text-muted hover:text-theme-text-primary'
            }`}
          >
            {tb.icon}
            {tb.label}
          </button>
        ))}
      </div>

      {tab === 'cities' ? (
        <CityManager />
      ) : (
        <>
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
            <div className="app-card p-5 space-y-4">
              <label className="label-base text-theme-text-primary font-semibold">וידאו, חותמת זמן וסימון רכב</label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="label-base text-theme-text-primary">אורך וידאו מינימלי (שניות)</label>
                  <input type="number" min={0} value={minVideoSeconds}
                    onChange={(e) => setMinVideoSeconds(Math.max(0, parseInt(e.target.value, 10) || 0))} className="input-base" />
                </div>
                <div>
                  <label className="label-base text-theme-text-primary">אורך וידאו מקסימלי (שניות)</label>
                  <input type="number" min={1} value={maxVideoSeconds}
                    onChange={(e) => setMaxVideoSeconds(Math.max(1, parseInt(e.target.value, 10) || 1))} className="input-base" />
                </div>
                <div>
                  <label className="label-base text-theme-text-primary">חלון מניעת כפילויות (שניות)</label>
                  <input type="number" min={0} value={dupWindowSeconds}
                    onChange={(e) => setDupWindowSeconds(Math.max(0, parseInt(e.target.value, 10) || 0))} className="input-base" />
                </div>
                <div>
                  <label className="label-base text-theme-text-primary">מיקום חותמת הזמן בוידאו</label>
                  <select className="input-base" value={tsPosition} onChange={(e) => setTsPosition(e.target.value)}>
                    <option value="top_right">למעלה מימין</option>
                    <option value="top_left">למעלה משמאל</option>
                    <option value="bottom_right">למטה מימין</option>
                    <option value="bottom_left">למטה משמאל</option>
                  </select>
                </div>
                <div>
                  <label className="label-base text-theme-text-primary">צבע מסגרת רכב — ממתין</label>
                  <input type="color" value={pendingColor} onChange={(e) => setPendingColor(e.target.value)} className="input-base h-10 p-1" />
                </div>
                <div>
                  <label className="label-base text-theme-text-primary">צבע מסגרת רכב — מאושר</label>
                  <input type="color" value={approvedColor} onChange={(e) => setApprovedColor(e.target.value)} className="input-base h-10 p-1" />
                </div>
                <label className="flex items-center gap-2 text-theme-text-primary self-end pb-2">
                  <input type="checkbox" checked={plateInset} onChange={(e) => setPlateInset(e.target.checked)} />
                  הצג חלון מוגדל של הלוחית בוידאו
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
                  checked={blurExceptPlate}
                  onChange={(e) => setBlurExceptPlate(e.target.checked)}
                />
                טשטש את כל הסרטון חוץ ממספר הרכב הרלוונטי
              </label>
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
        </>
      )}
    </div>
  )
}
