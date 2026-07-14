import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardCheck, Camera, Download, Check, X, Pencil, Send, ShieldCheck, History } from "lucide-react";
import { ticketsApi, violationRulesApi, inspectorsApi } from "../api";
import { useAuth } from "../context/AuthContext";
import { ticketStatusBadge } from "../lib/ticketStatus";

type LoadState = "idle" | "loading" | "ready" | "error";

interface TicketDetail {
  id: number;
  license_plate: string;
  plate_detection_reason?: string;
  status: string;
  violation_zone?: string;
  location?: string;
  captured_at?: string;
  created_at?: string;
  description?: string;
  admin_notes?: string;
  fine_amount?: number;
  violation_rule_id?: string;
  violation_decision?: string;
  violation_confidence?: number;
  violation_description_he?: string;
  violation_description_en?: string;
  has_original_video?: boolean;
  violation_start_at?: string;
  violation_end_at?: string;
  inspector_violation_rule_id?: string;
  inspector_plate?: string;
  vehicle_color?: string;
  vehicle_type?: string;
  assigned_inspector_id?: number | null;
  require_evidence_images?: boolean;
}

interface Screenshot {
  id: number;
  storage_path: string;
  frame_time_seconds: number | null;
  created_at: string | null;
  role?: string | null;
}

const PLATE_UNKNOWN = "11111";

const ROLES = [
  { key: "violation_start", label: "תחילת עבירה" },
  { key: "violation_end", label: "סיום עבירה" },
  { key: "plate_clear", label: "מספר רכב ברור" },
  { key: "violation_evidence", label: "תמונת העבירה" },
];

function toLocalInput(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function fromLocalInput(v: string): string | undefined {
  if (!v) return undefined;
  const d = new Date(v);
  return isNaN(d.getTime()) ? undefined : d.toISOString();
}

// Compact date+time (no seconds) so details fields stay one line in the tight 3-col grid.
function fmtDateTime(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "—" : d.toLocaleString("he-IL", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 mb-1">
      <div className="text-[11px] text-theme-text-muted leading-tight">{label}</div>
      <div className="leading-tight">{children}</div>
    </div>
  );
}

const DECISION_STYLE: Record<string, { badge: string; bar: string; label: string }> = {
  confirmed_violation: { badge: "badge-danger",  bar: "bg-red-600",   label: "הפרה מאושרת" },
  suspected_violation: { badge: "badge-warning", bar: "bg-amber-500", label: "הפרה חשודה" },
  no_violation:        { badge: "badge-success", bar: "bg-green-600", label: "ללא הפרה" },
};

const AUDIT_ACTION: Record<string, string> = {
  inspector_approve: "אישור",
  inspector_reject: "דחייה",
  inspector_update: "עדכון",
  inspector_transfer: "העברה",
};

// Curb/zone code → short Hebrew label (+ full description as tooltip)
const ZONE_LABEL: Record<string, string> = {
  red_white: "אדום-לבן",
  blue_white: "כחול-לבן",
  red_yellow: "אדום-צהוב",
};
const ZONE_DESC: Record<string, string> = {
  red_white: "אדום-לבן — איסור עצירה/חנייה",
  blue_white: "כחול-לבן — חנייה בתשלום",
  red_yellow: "אדום-צהוב — תחנת אוטובוס",
};

// 0,0 (or empty) = no GPS — a mobile upload without a location fix.
const isBlankCoords = (s?: string | null) => !s || /^\s*0\.?0*\s*,\s*0\.?0*\s*$/.test(s);

function displayDescription(desc?: string | null): string | null {
  if (!desc) return null;
  const m = desc.match(/^\s*mobile upload at\s*(.*)$/i);
  if (m) return isBlankCoords(m[1]) ? "העלאה מהנייד" : `העלאה מהנייד — ${m[1].trim()}`;
  return desc;
}

// The registry note is backend-generated English — render it in Hebrew.
function displayPlateReason(reason?: string | null): string | null {
  if (!reason) return null;
  return reason
    .replace(/Auto-corrected (.+?) -> (.+?) \(OCR alternative confirmed in gov registry\)/i, "תוקן אוטומטית: $1 ← $2 (חלופת OCR אומתה במרשם)")
    .replace(/not in gov registry — possible matches:/i, "לא נמצא במרשם הרכבים — התאמות אפשריות:")
    .replace(/not in gov registry — manual verification needed/i, "לא נמצא במרשם — נדרשת בדיקה ידנית")
    .replace(/not in gov registry/i, "לא נמצא במרשם הרכבים");
}

export default function TicketReview() {
  const ticketId = useMemo(() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    return parts[parts.length - 1];
  }, []);

  const [videoUrl, setVideoUrl] = useState<string>("");
  const [state, setState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [screenshots, setScreenshots] = useState<Screenshot[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [captureMsg, setCaptureMsg] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Admin edit state
  const [editMode, setEditMode] = useState(false);
  const [editNotes, setEditNotes] = useState("");
  const [editFine, setEditFine] = useState<string>("");
  const [editPlate, setEditPlate] = useState("");
  const [saving, setSaving] = useState(false);

  // Inspector approval state
  const { user } = useAuth();
  const isInspector = user?.user_type === "inspector";
  const isAdmin = user?.user_type === "admin";   // admin = "super inspector": full review+approve
  const [rules, setRules] = useState<{ rule_id: string; title_he: string }[]>([]);
  const [inspectors, setInspectors] = useState<{ id: number; full_name: string }[]>([]);
  const [aRule, setARule] = useState("");
  const [aPlate, setAPlate] = useState("");
  const [aColor, setAColor] = useState("");
  const [aType, setAType] = useState("");
  const [aStart, setAStart] = useState("");
  const [aEnd, setAEnd] = useState("");
  const [transferTo, setTransferTo] = useState("");
  const [approveMsg, setApproveMsg] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [rejectionNotes, setRejectionNotes] = useState("");

  useEffect(() => {
    violationRulesApi.list().then(({ data }) => setRules(data.filter((r: any) => r.is_active !== false))).catch(() => {});
    inspectorsApi.list(true).then(setInspectors).catch(() => {});
  }, []);

  useEffect(() => {
    let currentUrl = "";
    let cancelled = false;

    async function load() {
      setState("loading");
      setError(null);
      try {
        const [detail, blob] = await Promise.all([
          ticketsApi.getDetail(ticketId).catch(() => null),
          ticketsApi.getProcessedVideo(ticketId),
        ]);
        if (cancelled) return;
        if (detail) {
          setTicket(detail);
          setEditNotes(detail.admin_notes || "");
          setEditFine(detail.fine_amount != null ? String(detail.fine_amount) : "");
          setEditPlate(detail.license_plate || "");
          setARule(detail.inspector_violation_rule_id || detail.violation_rule_id || "");
          setAPlate(detail.license_plate && detail.license_plate !== PLATE_UNKNOWN ? detail.license_plate : "");
          setAColor(detail.vehicle_color || "");
          setAType(detail.vehicle_type || "");
          setAStart(toLocalInput(detail.violation_start_at));
          setAEnd(toLocalInput(detail.violation_end_at));
        }
        const url = URL.createObjectURL(blob);
        currentUrl = url;
        setVideoUrl(url);
        setState("ready");
        // Load screenshots + audit trail (non-blocking)
        ticketsApi.listScreenshots(ticketId).then(setScreenshots).catch(() => {});
        ticketsApi.audit(ticketId).then(setAudit).catch(() => {});
      } catch (err: any) {
        if (!cancelled) {
          setState("error");
          setError(err?.message || "Failed to load processed video");
        }
      }
    }

    load();
    return () => {
      cancelled = true;
      if (currentUrl) URL.revokeObjectURL(currentUrl);
    };
  }, [ticketId]);

  async function handleStatusChange(status: "approved" | "rejected") {
    if (!ticket) return;
    setSaving(true);
    try {
      const updated = await ticketsApi.updateTicket(ticketId, { status });
      setTicket(updated);
    } catch (err: any) {
      alert(err?.message || "שגיאה בשמירה");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveEdit() {
    if (!ticket) return;
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        admin_notes: editNotes || null,
        license_plate: editPlate || ticket.license_plate,
      };
      const fineVal = parseInt(editFine, 10);
      payload.fine_amount = isNaN(fineVal) ? null : fineVal;
      const updated = await ticketsApi.updateTicket(ticketId, payload);
      setTicket(updated);
      setEditMode(false);
    } catch (err: any) {
      alert(err?.message || "שגיאה בשמירה");
    } finally {
      setSaving(false);
    }
  }

  async function captureScreenshot() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    setCapturing(true);
    setCaptureMsg(null);
    try {
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 360;
      canvas.getContext("2d")?.drawImage(video, 0, 0);
      const frameTime = video.currentTime;
      const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
      await ticketsApi.saveScreenshot(ticketId, dataUrl, frameTime);
      const updated = await ticketsApi.listScreenshots(ticketId);
      setScreenshots(updated);
      setCaptureMsg(`✓ נשמר בשניה ${frameTime.toFixed(1)}`);
    } catch (err: any) {
      setCaptureMsg(`✗ ${err?.message || "שגיאה"}`);
    } finally {
      setCapturing(false);
    }
  }

  async function captureScreenshotRole(role: string) {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    setCapturing(true);
    setCaptureMsg(null);
    try {
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 360;
      canvas.getContext("2d")?.drawImage(video, 0, 0);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
      await ticketsApi.saveScreenshot(ticketId, dataUrl, video.currentTime, role);
      setScreenshots(await ticketsApi.listScreenshots(ticketId));
      setCaptureMsg("✓ נשמר");
    } catch (err: any) {
      setCaptureMsg(`✗ ${err?.message || "שגיאה"}`);
    } finally {
      setCapturing(false);
    }
  }

  async function reloadVideo() {
    try {
      const blob = await ticketsApi.getProcessedVideo(ticketId);
      setVideoUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return URL.createObjectURL(blob);
      });
    } catch { /* ignore */ }
  }

  async function handleApprove() {
    if (!ticket) return;
    if (!aRule) { setApproveMsg("✗ יש לבחור סוג עבירה"); return; }
    if (!aPlate.trim()) { setApproveMsg("✗ יש להזין מספר רכב"); return; }
    if (!/^\d{7,8}$/.test(aPlate.replace(/\D/g, ""))) { setApproveMsg("✗ מספר רכב חייב להכיל 7 או 8 ספרות"); return; }
    if (!aColor.trim()) { setApproveMsg("✗ יש להזין צבע רכב"); return; }
    if (!aType.trim()) { setApproveMsg("✗ יש להזין סוג רכב"); return; }
    if (!aStart || !aEnd) { setApproveMsg("✗ יש להזין תחילת עבירה וסיום עבירה"); return; }
    if (new Date(aEnd) <= new Date(aStart)) { setApproveMsg("✗ שעת הסיום חייבת להיות מאוחרת משעת ההתחלה"); return; }
    if (ticket.require_evidence_images) {
      const missing = ROLES.filter((r) => !screenshots.some((s) => s.role === r.key));
      if (missing.length > 0) {
        setApproveMsg(`✗ חסרות תמונות ראיה: ${missing.map((m) => m.label).join(", ")}`);
        return;
      }
    }
    setSaving(true);
    setApproveMsg(null);
    try {
      const payload: Record<string, unknown> = {
        inspector_plate: aPlate.trim(),
        inspector_violation_rule_id: aRule || null,
        vehicle_color: aColor || null,
        vehicle_type: aType || null,
      };
      const s = fromLocalInput(aStart); if (s) payload.violation_start_at = s;
      const e = fromLocalInput(aEnd); if (e) payload.violation_end_at = e;
      const updated = await ticketsApi.approve(ticketId, payload);
      setTicket(updated);
      setApproveMsg("✓ הדוח אושר");
      reloadVideo();
      ticketsApi.audit(ticketId).then(setAudit).catch(() => {});
    } catch (err: any) {
      setApproveMsg(`✗ ${err?.message || "שגיאה באישור"}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleReject() {
    if (!rejectionReason) { setApproveMsg("✗ יש לבחור סיבת דחייה"); return; }
    if (rejectionReason === "other" && !rejectionNotes.trim()) { setApproveMsg("✗ יש להזין הערה כאשר הסיבה היא אחר"); return; }
    setSaving(true);
    setApproveMsg(null);
    try {
      const updated = await ticketsApi.reject(ticketId, rejectionReason, rejectionNotes.trim() || undefined);
      setTicket(updated);
      setApproveMsg("✓ הדוח נדחה");
      ticketsApi.audit(ticketId).then(setAudit).catch(() => {});
    } catch (err: any) {
      setApproveMsg(`✗ ${err?.message || "שגיאה בדחייה"}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleTransfer() {
    if (!transferTo) return;
    setSaving(true);
    setApproveMsg(null);
    try {
      const updated = await ticketsApi.transfer(ticketId, parseInt(transferTo, 10));
      setTicket(updated);
      setTransferTo("");
      setApproveMsg("✓ הדוח הועבר");
      ticketsApi.audit(ticketId).then(setAudit).catch(() => {});
    } catch (err: any) {
      setApproveMsg(`✗ ${err?.message || "שגיאה בהעברה"}`);
    } finally {
      setSaving(false);
    }
  }

  const plateOk = ticket && ticket.license_plate && ticket.license_plate !== PLATE_UNKNOWN && ticket.license_plate !== "";
  const statusBadge = ticket ? ticketStatusBadge(ticket.status) : null;

  return (
    <div className="page-fill">
    <div dir="rtl" className="h-full flex flex-col min-h-0 gap-2 p-2 sm:p-3 text-theme-text-primary">

      {/* Header — slim */}
      <div className="page-header rounded-lg px-3 py-1 shrink-0 flex items-center gap-2 flex-wrap">
        <ClipboardCheck className="w-4 h-4 text-white/90 shrink-0" strokeWidth={1.75} />
        <h1 className="page-header-title text-theme-sm">בדיקת דוח #{ticketId}</h1>
        <div className="flex-1" />
        <Link to="/queue" className="text-white/90 hover:text-white text-theme-sm">← תור עיבוד</Link>
        <Link to="/tickets" className="text-white/90 hover:text-white text-theme-sm">← כל הדוחות</Link>
      </div>

      {state === "error" && (
        <div className="shrink-0 rounded-lg border border-red-200 bg-red-50 text-red-700 px-3 py-2 text-theme-sm">
          שגיאה: {error}
        </div>
      )}

      {/* Side-by-side: video + details — fills remaining height so the page never scrolls */}
      <div className="flex-1 min-h-0 flex gap-3 items-stretch">

        {/* Left column: video + screenshots — fills column height; the video scales to fit so a
            tall clip doesn't push the page past one viewport. */}
        <div className="grow-0 basis-[42%] max-w-[540px] min-w-[300px] flex flex-col gap-2 min-h-0">

          {/* Video panel — grows to fill the remaining height */}
          <div className="flex-1 min-h-0 flex flex-col">
            <div className="flex-1 min-h-0 flex flex-col rounded-xl overflow-hidden border border-theme-card-border bg-black">
              {videoUrl ? (
                <div className="flex-1 min-h-0 relative">
                  <video
                    ref={videoRef}
                    key={videoUrl}
                    src={videoUrl}
                    controls
                    playsInline
                    preload="auto"
                    className="absolute inset-0 w-full h-full object-contain"
                  />
                </div>
              ) : (
                <div className="flex-1 min-h-0 flex items-center justify-center text-center text-slate-400 bg-neutral-900">
                  {state === "loading" ? "טוען וידאו…" : "אין וידאו זמין"}
                </div>
              )}
              <canvas ref={canvasRef} className="hidden" />
              {videoUrl && (
                <div className="shrink-0 px-3 py-2 bg-slate-800 flex items-center gap-2.5">
                  <button onClick={captureScreenshot} disabled={capturing || state !== "ready"} className="btn-primary">
                    <Camera className="w-4 h-4" />
                    <span>{capturing ? "שומר…" : "צלם תמונה"}</span>
                  </button>
                  {captureMsg && (
                    <span className={`text-theme-sm ${captureMsg.startsWith("✓") ? "text-green-300" : "text-red-300"}`}>
                      {captureMsg}
                    </span>
                  )}
                  {ticket?.has_original_video && (
                    <button
                      onClick={async () => {
                        try {
                          const blob = await ticketsApi.getOriginalVideo(ticketId);
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `original_ticket_${ticketId}.mp4`;
                          a.click();
                          URL.revokeObjectURL(url);
                        } catch (e: any) {
                          alert("שגיאה בהורדת הוידאו המקורי: " + (e?.message || e));
                        }
                      }}
                      className="btn-cancel mr-auto"
                    >
                      <Download className="w-4 h-4" />
                      <span>הורד מקורי</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Screenshot gallery — under video */}
          {(screenshots.length > 0 || videoUrl) && (
            <div className="app-card p-2 shrink-0">
              <h3 className="text-sm font-semibold mb-1">
                צילומי מסך {screenshots.length > 0 ? `(${screenshots.length})` : ""}
              </h3>
              {screenshots.length === 0 ? (
                <p className="text-theme-text-muted text-theme-xs m-0">עדיין אין צילומים — לחץ "📸 צלם תמונה" בעת השמעת הוידאו</p>
              ) : (
                <>
                  <div className="flex gap-2 overflow-x-auto pb-1">
                    {screenshots.map((s) => (
                      <div
                        key={s.id}
                        onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                        className={`shrink-0 cursor-pointer rounded-lg overflow-hidden bg-slate-100 border-2 ${expanded === s.id ? "border-theme-accent" : "border-transparent"}`}
                      >
                        <img
                          src={ticketsApi.screenshotImageUrl(ticketId, s.id)}
                          alt={`Screenshot ${s.id}`}
                          className="w-[104px] h-14 object-cover block"
                          loading="lazy"
                        />
                        <div className="text-[10px] text-center px-1 py-0.5 text-theme-text-muted leading-tight truncate w-[104px]">
                          {s.frame_time_seconds != null && ticket?.captured_at
                            ? new Date(new Date(ticket.captured_at).getTime() + s.frame_time_seconds * 1000)
                                .toLocaleString("he-IL", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" })
                            : s.frame_time_seconds != null ? `+${s.frame_time_seconds.toFixed(1)}s` : "—"}
                        </div>
                      </div>
                    ))}
                  </div>
                  {expanded !== null && (
                    <div className="mt-2 rounded-lg overflow-hidden border border-theme-card-border">
                      <img
                        src={ticketsApi.screenshotImageUrl(ticketId, expanded)}
                        alt="Expanded screenshot"
                        className="w-full block max-h-28 object-contain bg-black"
                      />
                    </div>
                  )}
                </>
              )}
            </div>
          )}

        </div>{/* end left column */}

        {/* Right section: details (wide, 3-col field grid → short) beside analysis/audit. Scrolls
            internally only if a heavy ticket overflows, so the page itself never scrolls. */}
        <div className="flex-1 min-h-0 flex flex-row gap-3 flex-wrap items-start content-start overflow-y-auto">

          {ticket && (
            <div className="app-card grow basis-[400px] p-2.5">

              {/* Plate — full width (carries the registry note) */}
              <Field label="מספר לוחית">
                {editMode ? (
                  <input
                    value={editPlate}
                    onChange={e => setEditPlate(e.target.value)}
                    className="input-base font-mono text-lg tracking-widest"
                  />
                ) : plateOk ? (
                  <div>
                    <span className="font-bold text-xl tracking-[3px] font-mono">
                      {ticket.license_plate}
                    </span>
                    {ticket.plate_detection_reason && (
                      <div className="text-theme-xs mt-1 rounded px-2 py-1 bg-amber-50 text-amber-700 line-clamp-2" title={displayPlateReason(ticket.plate_detection_reason) || undefined}>
                        ⚠ {displayPlateReason(ticket.plate_detection_reason)}
                      </div>
                    )}
                  </div>
                ) : (
                  <div>
                    <span className="font-semibold text-red-600">לא זוהה</span>
                    {ticket.plate_detection_reason && (
                      <div className="text-theme-xs text-theme-text-muted mt-1 line-clamp-2" title={displayPlateReason(ticket.plate_detection_reason) || undefined}>{displayPlateReason(ticket.plate_detection_reason)}</div>
                    )}
                  </div>
                )}
              </Field>

              {/* Compact multi-column grid for the remaining fields — wide + short so it fits one screen */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-3 gap-y-0 border-t border-theme-card-border pt-2 mt-2">

                {/* Status */}
                <Field label="סטטוס">
                  {statusBadge && <span className={`badge ${statusBadge.cls}`}>{statusBadge.label}</span>}
                </Field>

                {/* Violation zone */}
                {ticket.violation_zone && (
                  <Field label="אזור עצירה">
                    <span className="text-theme-sm" title={ZONE_DESC[ticket.violation_zone] ?? ""}>{ZONE_LABEL[ticket.violation_zone] ?? ticket.violation_zone}</span>
                  </Field>
                )}

                {/* Fine */}
                <Field label="קנס">
                  {editMode ? (
                    <input
                      type="number"
                      value={editFine}
                      onChange={e => setEditFine(e.target.value)}
                      placeholder="סכום ₪"
                      className="input-base"
                    />
                  ) : ticket.fine_amount != null ? (
                    <span className="font-semibold text-red-600">₪{ticket.fine_amount}</span>
                  ) : (
                    <span className="text-theme-text-muted text-theme-sm">לא נקבע</span>
                  )}
                </Field>

                {/* Location */}
                <Field label="מיקום">
                  {isBlankCoords(ticket.location)
                    ? <span className="text-theme-text-muted text-theme-sm">אין מיקום זמין</span>
                    : <span className="text-theme-sm">{ticket.location}</span>}
                </Field>

                {/* Capture time */}
                {ticket.captured_at && (
                  <Field label="זמן צילום">
                    <span className="text-theme-sm">{fmtDateTime(ticket.captured_at)}</span>
                  </Field>
                )}

                {/* Violation window — start / end (#5) */}
                {ticket.violation_start_at && (
                  <Field label="תחילת עבירה">
                    <span className="text-theme-sm">{fmtDateTime(ticket.violation_start_at)}</span>
                  </Field>
                )}
                {ticket.violation_end_at && (
                  <Field label="סיום עבירה">
                    <span className="text-theme-sm">{fmtDateTime(ticket.violation_end_at)}</span>
                  </Field>
                )}

                {/* Submission time */}
                {ticket.created_at && (
                  <Field label="זמן הגשה">
                    <span className="text-theme-sm">{fmtDateTime(ticket.created_at)}</span>
                  </Field>
                )}

                {/* Description — full width */}
                {displayDescription(ticket.description) && (
                  <div className="col-span-2">
                    <Field label="תיאור">
                      <span className="text-theme-sm">{displayDescription(ticket.description)}</span>
                    </Field>
                  </div>
                )}
              </div>

              {/* Admin notes — full width */}
              <div className="border-t border-theme-card-border pt-2 mt-2">
                <Field label="הערות מנהל">
                  {editMode ? (
                    <textarea
                      value={editNotes}
                      onChange={e => setEditNotes(e.target.value)}
                      rows={2}
                      className="input-base min-h-[52px] resize-y"
                    />
                  ) : ticket.admin_notes ? (
                    <span className="text-theme-sm">{ticket.admin_notes}</span>
                  ) : (
                    <span className="text-theme-text-muted text-theme-sm">אין הערות</span>
                  )}
                </Field>
              </div>

              {/* Admin action buttons */}
              <div className="border-t border-theme-card-border mt-2 pt-2">
                {editMode ? (
                  <div className="flex gap-2">
                    <button onClick={handleSaveEdit} disabled={saving} className="btn-primary flex-1">
                      {saving ? "שומר…" : "שמור"}
                    </button>
                    <button
                      onClick={() => { setEditMode(false); setEditNotes(ticket.admin_notes || ""); setEditFine(ticket.fine_amount != null ? String(ticket.fine_amount) : ""); setEditPlate(ticket.license_plate || ""); }}
                      disabled={saving}
                      className="btn-cancel flex-1"
                    >
                      ביטול
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    {ticket.status !== "approved" && (
                      <button onClick={() => handleStatusChange("approved")} disabled={saving} className="btn-success grow min-w-0">
                        <Check className="w-4 h-4" />
                        <span>אשר</span>
                      </button>
                    )}
                    {ticket.status !== "rejected" && (
                      <button onClick={() => handleStatusChange("rejected")} disabled={saving} className="btn-danger grow min-w-0">
                        <X className="w-4 h-4" />
                        <span>דחה</span>
                      </button>
                    )}
                    <button onClick={() => setEditMode(true)} disabled={saving} className="btn-cancel grow min-w-0">
                      <Pencil className="w-4 h-4" />
                      <span>ערוך</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Review + approval panel — inspectors and admins (super inspectors) */}
          {ticket && (isInspector || isAdmin) && (
            <div className="app-card grow basis-[280px] p-3">
              <h3 className="text-base font-semibold mb-2 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-green-600" /> בדיקה ואישור
              </h3>

              <Field label="סוג עבירה">
                <select className="input-base" value={aRule} onChange={(e) => setARule(e.target.value)}>
                  <option value="">— בחר —</option>
                  {rules.map((r) => (
                    <option key={r.rule_id} value={r.rule_id}>{r.title_he} ({r.rule_id})</option>
                  ))}
                </select>
              </Field>

              <Field label="מספר רכב (לאימות)">
                <input
                  className="input-base font-mono tracking-widest"
                  value={aPlate}
                  onChange={(e) => setAPlate(e.target.value)}
                  placeholder="הקלד מספר רכב"
                />
                {(() => {
                  const detected = (ticket.license_plate || "").replace(/\D/g, "");
                  const typed = aPlate.replace(/\D/g, "");
                  if (!typed)
                    return <div className="text-[11px] text-theme-text-muted mt-0.5">חייב להתאים למספר שזוהה אוטומטית{detected && detected !== PLATE_UNKNOWN ? ` (${detected})` : ""}</div>;
                  if (!detected || detected === PLATE_UNKNOWN)
                    return <div className="text-[11px] text-theme-text-muted mt-0.5">אין מספר מזוהה אוטומטית להשוואה</div>;
                  return typed === detected
                    ? <div className="text-[11px] text-green-600 font-semibold mt-0.5">✓ תואם למספר שזוהה אוטומטית</div>
                    : <div className="text-[11px] text-red-600 font-semibold mt-0.5">⚠ שגיאה: אינו תואם למספר שזוהה אוטומטית ({detected})</div>;
                })()}
              </Field>

              <div className="flex gap-2">
                <div className="flex-1"><Field label="צבע רכב"><input className="input-base" value={aColor} onChange={(e) => setAColor(e.target.value)} /></Field></div>
                <div className="flex-1"><Field label="סוג רכב"><input className="input-base" value={aType} onChange={(e) => setAType(e.target.value)} /></Field></div>
              </div>

              <div className="flex gap-2">
                <div className="flex-1"><Field label="תחילת עבירה"><input type="datetime-local" className="input-base" value={aStart} onChange={(e) => setAStart(e.target.value)} /></Field></div>
                <div className="flex-1"><Field label="סיום עבירה"><input type="datetime-local" className="input-base" value={aEnd} onChange={(e) => setAEnd(e.target.value)} /></Field></div>
              </div>

              {/* 4 tagged images */}
              <div className="border-t border-theme-card-border my-2 pt-2">
                <div className="text-[11px] text-theme-text-muted mb-1">
                  4 תמונות לדוח (עצור את הוידאו ולחץ){ticket.require_evidence_images ? <span className="text-red-500"> — חובה לאישור</span> : null}:
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  {ROLES.map((role) => {
                    const has = screenshots.some((s) => s.role === role.key);
                    return (
                      <button
                        key={role.key}
                        type="button"
                        onClick={() => captureScreenshotRole(role.key)}
                        disabled={capturing || state !== "ready"}
                        className={`text-xs px-2 py-1.5 rounded-md border flex items-center justify-center gap-1 ${has ? "bg-green-50 border-green-300 text-green-700" : "bg-white border-theme-card-border text-theme-text-primary hover:bg-black/5"}`}
                      >
                        {has ? <Check className="w-3 h-3" /> : <Camera className="w-3 h-3" />}
                        {role.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {approveMsg && (
                <div className={`text-theme-sm mt-2 ${approveMsg.startsWith("✓") ? "text-green-600" : "text-red-600"}`}>{approveMsg}</div>
              )}

              <button onClick={handleApprove} disabled={saving} className="btn-success w-full justify-center mt-2">
                <Check className="w-4 h-4" /> <span>{saving ? "מאשר…" : "אשר דוח"}</span>
              </button>

              <div className="border-t border-theme-card-border mt-2 pt-2 space-y-2">
                <Field label="סיבת דחייה">
                  <select className="input-base" value={rejectionReason} onChange={(e) => setRejectionReason(e.target.value)}>
                    <option value="">— בחר סיבה —</option>
                    <option value="unclear_plate">מספר רכב לא ברור</option>
                    <option value="vehicle_not_in_violation_zone">הרכב אינו באזור עבירה</option>
                    <option value="wrong_violation_type">סוג עבירה שגוי</option>
                    <option value="missing_evidence">חסר תיעוד</option>
                    <option value="multiple_vehicles_uncertain">מספר רכבים / אי ודאות</option>
                    <option value="technical_video_issue">תקלה טכנית בסרטון</option>
                    <option value="duplicate_ticket">דוח כפול</option>
                    <option value="other">אחר</option>
                  </select>
                </Field>
                {rejectionReason === "other" && (
                  <Field label="הערת דחייה">
                    <textarea className="input-base min-h-20" value={rejectionNotes} onChange={(e) => setRejectionNotes(e.target.value)} />
                  </Field>
                )}
                <button onClick={handleReject} disabled={saving} className="btn-danger w-full justify-center">
                  <X className="w-4 h-4" /> <span>דחה דוח</span>
                </button>
              </div>

              {/* Transfer */}
              <div className="border-t border-theme-card-border mt-2 pt-2">
                <Field label="העבר לפקח אחר">
                  <div className="flex gap-2">
                    <select className="input-base flex-1" value={transferTo} onChange={(e) => setTransferTo(e.target.value)}>
                      <option value="">— בחר פקח —</option>
                      {inspectors.map((i) => (<option key={i.id} value={i.id}>{i.full_name}</option>))}
                    </select>
                    <button onClick={handleTransfer} disabled={saving || !transferTo} className="btn-secondary" title="העבר"><Send className="w-4 h-4" /></button>
                  </div>
                </Field>
              </div>
            </div>
          )}

          {/* Violation analysis */}
          {ticket && ticket.violation_decision && (
            <div className="app-card grow basis-[240px] p-3">
              <h3 className="text-base font-semibold mb-3.5">ניתוח הפרה אוטומטי</h3>
              {(() => {
                const dec = ticket.violation_decision!;
                const conf = ticket.violation_confidence ?? 0;
                const pct = Math.round(conf * 100);
                const m = DECISION_STYLE[dec] ?? { badge: "badge-neutral", bar: "bg-slate-400", label: "עדויות לא מספיקות" };
                return (
                  <div>
                    <div className="flex items-center gap-3 mb-2.5 flex-wrap">
                      <span className={`badge ${m.badge}`}>{m.label}</span>
                      {ticket.violation_rule_id && (
                        <span className="text-theme-xs text-theme-text-muted font-mono">{ticket.violation_rule_id}</span>
                      )}
                      <span className="text-theme-xs text-theme-text-muted">ביטחון: {pct}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-200 rounded mb-2.5">
                      <div className={`h-full rounded ${m.bar}`} style={{ width: `${pct}%` }} />
                    </div>
                    {ticket.violation_description_he && (
                      <div className="text-theme-sm mb-1.5 leading-relaxed">
                        {ticket.violation_description_he}
                      </div>
                    )}
                    <div className="mt-2.5 text-[11px] text-theme-text-muted">
                      * ניתוח אוטומטי — נדרש אישור אנושי לפני הוצאת דוח
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {/* Audit trail */}
          {ticket && audit.length > 0 && (
            <div className="app-card grow basis-[240px] p-3">
              <h3 className="text-base font-semibold mb-3 flex items-center gap-2">
                <History className="w-4 h-4 text-theme-text-muted" /> יומן פעולות
              </h3>
              <ul className="space-y-2 m-0 p-0 list-none">
                {audit.map((a) => (
                  <li key={a.id} className="text-theme-sm border-r-2 border-theme-accent pr-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold">{AUDIT_ACTION[a.action_type] ?? a.action_type}</span>
                      <span className="text-theme-xs text-theme-text-muted">
                        {a.inspector_id ? (inspectors.find((i) => i.id === a.inspector_id)?.full_name ?? `פקח #${a.inspector_id}`) : "—"}
                      </span>
                      <span className="text-theme-xs text-theme-text-muted mr-auto">
                        {a.created_at ? new Date(a.created_at).toLocaleString("he-IL") : ""}
                      </span>
                    </div>
                    {a.notes && <div className="text-theme-xs text-theme-text-muted mt-0.5">{a.notes}</div>}
                  </li>
                ))}
              </ul>
            </div>
          )}

        </div>{/* end right column */}
      </div>
    </div>
    </div>
  );
}
