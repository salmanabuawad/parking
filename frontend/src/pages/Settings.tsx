import { useState, useEffect, type ReactNode, type ChangeEvent } from 'react'
import { Settings as SettingsIcon, SlidersHorizontal, MapPin } from 'lucide-react'
import { settingsApi } from '../api'
import { t } from '../i18n'
import CityManager from './CityManager'

type Tab = 'system' | 'cities'

const TABS: { key: Tab; label: string; icon: ReactNode }[] = [
  { key: 'system', label: 'מערכת', icon: <SlidersHorizontal className="w-4 h-4" /> },
  { key: 'cities', label: 'ערים ומפות', icon: <MapPin className="w-4 h-4" /> },
]

/** Compact labelled field for the settings grid. `span` widens it across grid columns. */
function Field({ label, span, children }: { label: string; span?: string; children: ReactNode }) {
  return (
    <label className={`flex flex-col gap-1 ${span || ''}`}>
      <span className="text-theme-sm font-medium text-theme-text-primary leading-tight">{label}</span>
      {children}
    </label>
  )
}

function Toggle({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  return (
    <label className="flex items-center gap-2 text-theme-sm text-theme-text-primary cursor-pointer">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="shrink-0" />
      <span>{children}</span>
    </label>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="app-card p-4">
      <h2 className="text-theme-sm font-semibold text-theme-text-primary mb-3">{title}</h2>
      {children}
    </section>
  )
}

const GRID = 'grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-3'
const TOGGLE_ROW = 'col-span-2 md:col-span-3 lg:col-span-4 flex flex-wrap gap-x-6 gap-y-2 pt-1'

export default function Settings() {
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

  const numHandler = (setter: (v: number) => void, lo: number, hi?: number) =>
    (e: ChangeEvent<HTMLInputElement>) => {
      let v = parseInt(e.target.value, 10) || 0
      v = Math.max(lo, v)
      if (hi != null) v = Math.min(hi, v)
      setter(v)
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
        <div className="max-w-[1600px] mx-auto space-y-4">
          <p className="text-theme-text-muted text-theme-sm">{t('settingsIntro')}</p>

          {settings && (
            <>
              <Section title="הגדרות אכיפה ומערכת">
                <div className={GRID}>
                  <Field label="זמן שהייה שנחשב לעבירה (שניות)">
                    <input type="number" min={0} value={violationDwellSeconds} onChange={numHandler(setViolationDwellSeconds, 0)} className="input-base" />
                  </Field>
                  <Field label="אורך סרטון נדרש (שניות)">
                    <input type="number" min={0} value={requiredVideoSeconds} onChange={numHandler(setRequiredVideoSeconds, 0)} className="input-base" />
                  </Field>
                  <Field label="שניות הקלטה לפני העבירה">
                    <input type="number" min={0} max={120} value={evidencePreSeconds} onChange={numHandler(setEvidencePreSeconds, 0, 120)} className="input-base" />
                  </Field>
                  <Field label="שניות הקלטה אחרי העבירה">
                    <input type="number" min={0} max={120} value={evidencePostSeconds} onChange={numHandler(setEvidencePostSeconds, 0, 120)} className="input-base" />
                  </Field>
                  <Field label="שמירת סרטונים (ימים)">
                    <input type="number" min={0} value={videoRetentionDays} onChange={numHandler(setVideoRetentionDays, 0)} className="input-base" />
                  </Field>
                  <Field label="שמירת סרטון מקור (ימים)">
                    <input type="number" min={0} value={originalRetentionDays} onChange={numHandler(setOriginalRetentionDays, 0)} className="input-base" />
                  </Field>
                  <Field label="שמירת סרטון מעובד (ימים)">
                    <input type="number" min={0} value={processedRetentionDays} onChange={numHandler(setProcessedRetentionDays, 0)} className="input-base" />
                  </Field>
                  <Field label="שמירת מועמדים לדוח (ימים)">
                    <input type="number" min={0} value={candidateRetentionDays} onChange={numHandler(setCandidateRetentionDays, 0)} className="input-base" />
                  </Field>
                  <div className={TOGGLE_ROW}>
                    <Toggle checked={videoTimestampOverlay} onChange={setVideoTimestampOverlay}>הצג תאריך ושעה בסרטון</Toggle>
                  </div>
                </div>
              </Section>

              <Section title="וידאו, חותמת זמן וסימון רכב">
                <div className={GRID}>
                  <Field label="אורך וידאו מינימלי (שניות)">
                    <input type="number" min={0} value={minVideoSeconds} onChange={numHandler(setMinVideoSeconds, 0)} className="input-base" />
                  </Field>
                  <Field label="אורך וידאו מקסימלי (שניות)">
                    <input type="number" min={1} value={maxVideoSeconds} onChange={numHandler(setMaxVideoSeconds, 1)} className="input-base" />
                  </Field>
                  <Field label="חלון מניעת כפילויות (שניות)">
                    <input type="number" min={0} value={dupWindowSeconds} onChange={numHandler(setDupWindowSeconds, 0)} className="input-base" />
                  </Field>
                  <Field label="מיקום חותמת הזמן בוידאו">
                    <select className="input-base" value={tsPosition} onChange={(e) => setTsPosition(e.target.value)}>
                      <option value="top_right">למעלה מימין</option>
                      <option value="top_left">למעלה משמאל</option>
                      <option value="bottom_right">למטה מימין</option>
                      <option value="bottom_left">למטה משמאל</option>
                    </select>
                  </Field>
                  <Field label="צבע מסגרת רכב — ממתין">
                    <input type="color" value={pendingColor} onChange={(e) => setPendingColor(e.target.value)} className="input-base h-10 p-1 max-w-[140px]" />
                  </Field>
                  <Field label="צבע מסגרת רכב — מאושר">
                    <input type="color" value={approvedColor} onChange={(e) => setApprovedColor(e.target.value)} className="input-base h-10 p-1 max-w-[140px]" />
                  </Field>
                  <div className={TOGGLE_ROW}>
                    <Toggle checked={plateInset} onChange={setPlateInset}>הצג חלון מוגדל של הלוחית בוידאו</Toggle>
                  </div>
                </div>
              </Section>

              <Section title="טשטוש ומרשם הרכבים">
                <div className={GRID}>
                  <Field label={t('blurKernelLabel')}>
                    <input type="number" min={0} max={51} step={2} value={blurSize}
                      onChange={(e) => setBlurSize(Math.max(0, Math.min(99, parseInt(e.target.value, 10) || 0)))} className="input-base" />
                  </Field>
                  <Field label="יחס הרחבת אזור הטשטוש (0–1)">
                    <input type="number" min={0} max={1} step={0.01} value={blurExpandRatio}
                      onChange={(e) => setBlurExpandRatio(Math.max(0, Math.min(1, parseFloat(e.target.value) || 0)))} className="input-base" />
                  </Field>
                  <div className={TOGGLE_ROW}>
                    <Toggle checked={blurExceptPlate} onChange={setBlurExceptPlate}>טשטש את כל הסרטון חוץ ממספר הרכב הרלוונטי</Toggle>
                    <Toggle checked={usePipeline} onChange={setUsePipeline}>{t('useViolationPipeline')}</Toggle>
                  </div>
                </div>

                <div className="border-t border-theme-card-border pt-4 mt-4">
                  <div className="mb-3">
                    <Toggle checked={vehicleRegistryEnabled} onChange={setVehicleRegistryEnabled}>אפשר חיפוש במרשם הרכבים הישראלי</Toggle>
                  </div>
                  <div className={GRID}>
                    <Field label="כתובת API של data.gov.il" span="col-span-2">
                      <input type="url" dir="ltr" value={vehicleRegistryApiUrl} onChange={(e) => setVehicleRegistryApiUrl(e.target.value)} className="input-base" />
                    </Field>
                    <Field label="מזהה משאב (Resource ID)" span="col-span-2">
                      <input type="text" dir="ltr" value={vehicleRegistryResourceId} onChange={(e) => setVehicleRegistryResourceId(e.target.value)} className="input-base" />
                    </Field>
                    <Field label="שם שדה מספר הרכב">
                      <input type="text" dir="ltr" value={vehicleRegistryPlateField} onChange={(e) => setVehicleRegistryPlateField(e.target.value)} className="input-base" />
                    </Field>
                    <Field label="פסק זמן (שניות)">
                      <input type="number" min={1} max={60} value={vehicleRegistryTimeoutSeconds}
                        onChange={(e) => setVehicleRegistryTimeoutSeconds(Math.max(1, Math.min(60, parseInt(e.target.value, 10) || 10)))} className="input-base" />
                    </Field>
                    <Field label="תוקף מטמון (שעות)">
                      <input type="number" min={1} max={720} value={vehicleRegistryCacheTtlHours}
                        onChange={(e) => setVehicleRegistryCacheTtlHours(Math.max(1, Math.min(720, parseInt(e.target.value, 10) || 24)))} className="input-base" />
                    </Field>
                  </div>
                </div>
              </Section>

              <div className="flex pt-1">
                <button type="button" onClick={save} disabled={saving} className="btn-primary">
                  {saving ? t('saving') : t('save')}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
