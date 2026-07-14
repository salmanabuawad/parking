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

/** Label-above field — for wide text/URL inputs that need the full column width. */
function Field({ label, span, children }: { label: string; span?: string; children: ReactNode }) {
  return (
    <label className={`flex flex-col gap-1 ${span || ''}`}>
      <span className="text-theme-sm font-medium text-theme-text-primary leading-tight">{label}</span>
      {children}
    </label>
  )
}

/** Inline setting row — label (right, RTL) + a compact fixed-width control (left) + optional unit.
 *  The control sits in a fixed-width slot so tiny numeric values don't fill a huge empty input.
 *  (A wrapper width is used because .input-base bakes in w-full, which a bare w-20 can't override.) */
function Row({ label, unit, w = 'w-20', children }: { label: string; unit?: string; w?: string; children: ReactNode }) {
  return (
    <label className="flex items-center justify-between gap-3 min-h-[2.5rem]">
      <span className="text-theme-sm text-theme-text-primary leading-tight min-w-0">{label}</span>
      <span className="flex items-center gap-1.5 shrink-0">
        <span className={`block ${w}`}>{children}</span>
        {unit && <span className="text-theme-xs text-theme-text-muted w-9">{unit}</span>}
      </span>
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

const GRID = 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-x-10 gap-y-0.5'
const TEXTGRID = 'grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3'
const TOGGLE_ROW = 'flex flex-wrap gap-x-6 gap-y-2 pt-3 mt-3 border-t border-theme-card-border'
const NUM = 'input-base text-center'

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
  const [saveMsg, setSaveMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)

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
    setSaveMsg(null)
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
      setSaveMsg({ kind: 'ok', text: 'ההגדרות נשמרו' })
    } catch (err) {
      setSaveMsg({ kind: 'err', text: (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t('failedToSave') })
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
        <div className="flex-1 min-h-0 overflow-y-auto">
          <CityManager />
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="max-w-[1600px] mx-auto space-y-4 pb-2">
          <p className="text-theme-text-muted text-theme-sm">{t('settingsIntro')}</p>

          {settings && (
            <>
              <Section title="הגדרות אכיפה ומערכת">
                <div className={GRID}>
                  <Row label="זמן שהייה שנחשב לעבירה" unit="שניות">
                    <input type="number" min={0} value={violationDwellSeconds} onChange={numHandler(setViolationDwellSeconds, 0)} className={NUM} />
                  </Row>
                  <Row label="אורך סרטון נדרש" unit="שניות">
                    <input type="number" min={0} value={requiredVideoSeconds} onChange={numHandler(setRequiredVideoSeconds, 0)} className={NUM} />
                  </Row>
                  <Row label="שניות הקלטה לפני העבירה" unit="שניות">
                    <input type="number" min={0} max={120} value={evidencePreSeconds} onChange={numHandler(setEvidencePreSeconds, 0, 120)} className={NUM} />
                  </Row>
                  <Row label="שניות הקלטה אחרי העבירה" unit="שניות">
                    <input type="number" min={0} max={120} value={evidencePostSeconds} onChange={numHandler(setEvidencePostSeconds, 0, 120)} className={NUM} />
                  </Row>
                  <Row label="שמירת סרטונים" unit="ימים">
                    <input type="number" min={0} value={videoRetentionDays} onChange={numHandler(setVideoRetentionDays, 0)} className={NUM} />
                  </Row>
                  <Row label="שמירת סרטון מקור" unit="ימים">
                    <input type="number" min={0} value={originalRetentionDays} onChange={numHandler(setOriginalRetentionDays, 0)} className={NUM} />
                  </Row>
                  <Row label="שמירת סרטון מעובד" unit="ימים">
                    <input type="number" min={0} value={processedRetentionDays} onChange={numHandler(setProcessedRetentionDays, 0)} className={NUM} />
                  </Row>
                  <Row label="שמירת מועמדים לדוח" unit="ימים">
                    <input type="number" min={0} value={candidateRetentionDays} onChange={numHandler(setCandidateRetentionDays, 0)} className={NUM} />
                  </Row>
                </div>
                <div className={TOGGLE_ROW}>
                  <Toggle checked={videoTimestampOverlay} onChange={setVideoTimestampOverlay}>הצג תאריך ושעה בסרטון</Toggle>
                </div>
              </Section>

              <Section title="וידאו, חותמת זמן וסימון רכב">
                <div className={GRID}>
                  <Row label="אורך וידאו מינימלי" unit="שניות">
                    <input type="number" min={0} value={minVideoSeconds} onChange={numHandler(setMinVideoSeconds, 0)} className={NUM} />
                  </Row>
                  <Row label="אורך וידאו מקסימלי" unit="שניות">
                    <input type="number" min={1} value={maxVideoSeconds} onChange={numHandler(setMaxVideoSeconds, 1)} className={NUM} />
                  </Row>
                  <Row label="חלון מניעת כפילויות" unit="שניות">
                    <input type="number" min={0} value={dupWindowSeconds} onChange={numHandler(setDupWindowSeconds, 0)} className={NUM} />
                  </Row>
                  <Row label="מיקום חותמת הזמן בוידאו" w="w-36">
                    <select className="input-base" value={tsPosition} onChange={(e) => setTsPosition(e.target.value)}>
                      <option value="top_right">למעלה מימין</option>
                      <option value="top_left">למעלה משמאל</option>
                      <option value="bottom_right">למטה מימין</option>
                      <option value="bottom_left">למטה משמאל</option>
                    </select>
                  </Row>
                  <Row label="צבע מסגרת רכב — ממתין" w="w-16">
                    <input type="color" value={pendingColor} onChange={(e) => setPendingColor(e.target.value)} className="input-base h-8 p-0.5" />
                  </Row>
                  <Row label="צבע מסגרת רכב — מאושר" w="w-16">
                    <input type="color" value={approvedColor} onChange={(e) => setApprovedColor(e.target.value)} className="input-base h-8 p-0.5" />
                  </Row>
                </div>
                <div className={TOGGLE_ROW}>
                  <Toggle checked={plateInset} onChange={setPlateInset}>הצג חלון מוגדל של הלוחית בוידאו</Toggle>
                </div>
              </Section>

              <Section title="טשטוש ומרשם הרכבים">
                <div className={GRID}>
                  <Row label={t('blurKernelLabel')}>
                    <input type="number" min={0} max={51} step={2} value={blurSize}
                      onChange={(e) => setBlurSize(Math.max(0, Math.min(99, parseInt(e.target.value, 10) || 0)))} className={NUM} />
                  </Row>
                  <Row label="יחס הרחבת אזור הטשטוש (0–1)">
                    <input type="number" min={0} max={1} step={0.01} value={blurExpandRatio}
                      onChange={(e) => setBlurExpandRatio(Math.max(0, Math.min(1, parseFloat(e.target.value) || 0)))} className={NUM} />
                  </Row>
                </div>
                <div className={TOGGLE_ROW}>
                  <Toggle checked={blurExceptPlate} onChange={setBlurExceptPlate}>טשטש את כל הסרטון חוץ ממספר הרכב הרלוונטי</Toggle>
                  <Toggle checked={usePipeline} onChange={setUsePipeline}>{t('useViolationPipeline')}</Toggle>
                </div>

                <div className="border-t border-theme-card-border pt-4 mt-4">
                  <div className="mb-3">
                    <Toggle checked={vehicleRegistryEnabled} onChange={setVehicleRegistryEnabled}>אפשר חיפוש במרשם הרכבים הישראלי</Toggle>
                  </div>
                  <div className={TEXTGRID}>
                    <Field label="כתובת API של data.gov.il" span="md:col-span-2">
                      <input type="url" dir="ltr" value={vehicleRegistryApiUrl} onChange={(e) => setVehicleRegistryApiUrl(e.target.value)} className="input-base" />
                    </Field>
                    <Field label="מזהה משאב (Resource ID)">
                      <input type="text" dir="ltr" value={vehicleRegistryResourceId} onChange={(e) => setVehicleRegistryResourceId(e.target.value)} className="input-base" />
                    </Field>
                    <Field label="שם שדה מספר הרכב">
                      <input type="text" dir="ltr" value={vehicleRegistryPlateField} onChange={(e) => setVehicleRegistryPlateField(e.target.value)} className="input-base" />
                    </Field>
                  </div>
                  <div className={`${GRID} mt-2`}>
                    <Row label="פסק זמן" unit="שניות">
                      <input type="number" min={1} max={60} value={vehicleRegistryTimeoutSeconds}
                        onChange={(e) => setVehicleRegistryTimeoutSeconds(Math.max(1, Math.min(60, parseInt(e.target.value, 10) || 10)))} className={NUM} />
                    </Row>
                    <Row label="תוקף מטמון" unit="שעות">
                      <input type="number" min={1} max={720} value={vehicleRegistryCacheTtlHours}
                        onChange={(e) => setVehicleRegistryCacheTtlHours(Math.max(1, Math.min(720, parseInt(e.target.value, 10) || 24)))} className={NUM} />
                    </Row>
                  </div>
                </div>
              </Section>

              <div className="flex items-center gap-3 pt-1">
                <button type="button" onClick={save} disabled={saving} className="btn-primary">
                  {saving ? t('saving') : t('save')}
                </button>
                {saveMsg && (
                  <span className={`text-theme-sm ${saveMsg.kind === 'ok' ? 'text-emerald-600' : 'text-red-600'}`}>
                    {saveMsg.kind === 'ok' ? '✓ ' : '✗ '}{saveMsg.text}
                  </span>
                )}
              </div>
            </>
          )}
          </div>
        </div>
      )}
    </div>
  )
}
