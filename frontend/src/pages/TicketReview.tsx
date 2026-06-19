import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardCheck, Camera, Download, Check, X, Pencil } from "lucide-react";
import { ticketsApi } from "../api";

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
}

interface Screenshot {
  id: number;
  storage_path: string;
  frame_time_seconds: number | null;
  created_at: string | null;
}

const PLATE_UNKNOWN = "11111";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-2">
      <div className="text-[11px] text-theme-text-muted mb-0.5">{label}</div>
      <div>{children}</div>
    </div>
  );
}

const STATUS_BADGE: Record<string, { cls: string; label: string }> = {
  pending_review: { cls: "badge-warning", label: "ממתין לבדיקה" },
  approved:       { cls: "badge-success", label: "אושר" },
  rejected:       { cls: "badge-danger",  label: "נדחה" },
  paid:           { cls: "badge-info",    label: "שולם" },
};

const DECISION_STYLE: Record<string, { badge: string; bar: string; label: string }> = {
  confirmed_violation: { badge: "badge-danger",  bar: "bg-red-600",   label: "הפרה מאושרת" },
  suspected_violation: { badge: "badge-warning", bar: "bg-amber-500", label: "הפרה חשודה" },
  no_violation:        { badge: "badge-success", bar: "bg-green-600", label: "ללא הפרה" },
};

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
        }
        const url = URL.createObjectURL(blob);
        currentUrl = url;
        setVideoUrl(url);
        setState("ready");
        // Load screenshots (non-blocking)
        ticketsApi.listScreenshots(ticketId).then(setScreenshots).catch(() => {});
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

  const plateOk = ticket && ticket.license_plate && ticket.license_plate !== PLATE_UNKNOWN && ticket.license_plate !== "";
  const statusBadge = ticket ? (STATUS_BADGE[ticket.status] ?? { cls: "badge-neutral", label: ticket.status }) : null;

  return (
    <div className="page-fill">
    <div className="page-body-scroll">
    <div dir="rtl" className="p-4 sm:p-6 text-theme-text-primary">

      {/* Header */}
      <div className="page-header rounded-lg px-3 py-2 mb-4 flex items-center gap-3 flex-wrap">
        <span className="page-header-icon">
          <ClipboardCheck className="w-5 h-5" strokeWidth={1.5} />
        </span>
        <h1 className="page-header-title">בדיקת דוח #{ticketId}</h1>
        <div className="flex-1" />
        <Link to="/queue" className="text-white/90 hover:text-white text-theme-sm">← תור עיבוד</Link>
        <Link to="/tickets" className="text-white/90 hover:text-white text-theme-sm">← כל הדוחות</Link>
      </div>

      {state === "error" && (
        <div className="mb-3 rounded-lg border border-red-200 bg-red-50 text-red-700 px-3 py-2 text-theme-sm">
          שגיאה: {error}
        </div>
      )}

      {/* Side-by-side: video + details */}
      <div className="flex gap-5 items-start flex-wrap">

        {/* Left column: video + screenshots */}
        <div className="grow basis-[340px] min-w-[280px] flex flex-col gap-4">

          {/* Video panel */}
          <div>
            <div className="rounded-xl overflow-hidden border border-theme-card-border bg-black">
              {videoUrl ? (
                <video
                  ref={videoRef}
                  key={videoUrl}
                  src={videoUrl}
                  controls
                  playsInline
                  className="w-full block max-h-80"
                />
              ) : (
                <div className="p-8 text-center text-slate-400 bg-neutral-900">
                  {state === "loading" ? "טוען וידאו…" : "אין וידאו זמין"}
                </div>
              )}
              <canvas ref={canvasRef} className="hidden" />
              {videoUrl && (
                <div className="px-3 py-2.5 bg-slate-800 flex items-center gap-2.5">
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
            <div className="app-card p-4">
              <h3 className="text-base font-semibold mb-3">
                צילומי מסך {screenshots.length > 0 ? `(${screenshots.length})` : ""}
              </h3>
              {screenshots.length === 0 ? (
                <p className="text-theme-text-muted text-theme-sm m-0">עדיין אין צילומים — לחץ "📸 צלם תמונה" בעת השמעת הוידאו</p>
              ) : (
                <>
                  <div className="flex gap-2.5 flex-wrap">
                    {screenshots.map((s) => (
                      <div
                        key={s.id}
                        onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                        className={`cursor-pointer rounded-lg overflow-hidden bg-slate-100 border-2 ${expanded === s.id ? "border-theme-accent" : "border-transparent"}`}
                      >
                        <img
                          src={ticketsApi.screenshotImageUrl(ticketId, s.id)}
                          alt={`Screenshot ${s.id}`}
                          className="w-[140px] h-20 object-cover block"
                          loading="lazy"
                        />
                        <div className="text-[11px] text-center px-1 py-0.5 text-theme-text-muted leading-tight">
                          {s.frame_time_seconds != null && ticket?.captured_at
                            ? new Date(new Date(ticket.captured_at).getTime() + s.frame_time_seconds * 1000)
                                .toLocaleString("he-IL", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" })
                            : s.frame_time_seconds != null ? `+${s.frame_time_seconds.toFixed(1)}s` : "—"}
                        </div>
                      </div>
                    ))}
                  </div>
                  {expanded !== null && (
                    <div className="mt-3 rounded-lg overflow-hidden border border-theme-card-border">
                      <img
                        src={ticketsApi.screenshotImageUrl(ticketId, expanded)}
                        alt="Expanded screenshot"
                        className="w-full block"
                      />
                    </div>
                  )}
                </>
              )}
            </div>
          )}

        </div>{/* end left column */}

        {/* Right section: details + violation analysis */}
        <div className="grow basis-[320px] flex flex-row gap-4 flex-wrap items-start">

          {ticket && (
            <div className="app-card grow basis-[240px] p-4 sticky top-[88px]">

              {/* Plate */}
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
                      <div className="text-theme-xs mt-1 rounded px-2 py-1 bg-amber-50 text-amber-700">
                        ⚠ {ticket.plate_detection_reason}
                      </div>
                    )}
                  </div>
                ) : (
                  <div>
                    <span className="font-semibold text-red-600">לא זוהה</span>
                    {ticket.plate_detection_reason && (
                      <div className="text-theme-xs text-theme-text-muted mt-1">{ticket.plate_detection_reason}</div>
                    )}
                  </div>
                )}
              </Field>

              <div className="border-t border-theme-card-border my-1.5" />

              {/* Status */}
              <Field label="סטטוס">
                {statusBadge && <span className={`badge ${statusBadge.cls}`}>{statusBadge.label}</span>}
              </Field>

              {/* Violation zone */}
              {ticket.violation_zone && (
                <Field label="אזור עצירה">
                  <span>{ticket.violation_zone}</span>
                </Field>
              )}

              {/* Fine */}
              <Field label="קנס">
                {editMode ? (
                  <div className="w-32">
                    <input
                      type="number"
                      value={editFine}
                      onChange={e => setEditFine(e.target.value)}
                      placeholder="סכום ₪"
                      className="input-base"
                    />
                  </div>
                ) : ticket.fine_amount != null ? (
                  <span className="font-semibold text-red-600">₪{ticket.fine_amount}</span>
                ) : (
                  <span className="text-theme-text-muted text-theme-sm">לא נקבע</span>
                )}
              </Field>

              <div className="border-t border-theme-card-border my-1.5" />

              {/* Location */}
              {ticket.location && (
                <Field label="מיקום">
                  <span className="text-theme-sm">{ticket.location}</span>
                </Field>
              )}

              {/* Capture time */}
              {ticket.captured_at && (
                <Field label="זמן צילום">
                  {new Date(ticket.captured_at).toLocaleString("he-IL")}
                </Field>
              )}

              {/* Submission time */}
              {ticket.created_at && (
                <Field label="זמן הגשה">
                  {new Date(ticket.created_at).toLocaleString("he-IL")}
                </Field>
              )}

              {/* Description */}
              {ticket.description && (
                <Field label="תיאור">
                  <span className="text-theme-sm">{ticket.description}</span>
                </Field>
              )}

              {/* Admin notes */}
              <div className="border-t border-theme-card-border my-1.5" />
              <Field label="הערות מנהל">
                {editMode ? (
                  <textarea
                    value={editNotes}
                    onChange={e => setEditNotes(e.target.value)}
                    rows={3}
                    className="input-base min-h-[72px] resize-y"
                  />
                ) : ticket.admin_notes ? (
                  <span className="text-theme-sm">{ticket.admin_notes}</span>
                ) : (
                  <span className="text-theme-text-muted text-theme-sm">אין הערות</span>
                )}
              </Field>

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
                  <div className="flex gap-2 flex-wrap">
                    {ticket.status !== "approved" && (
                      <button onClick={() => handleStatusChange("approved")} disabled={saving} className="btn-success grow min-w-[90px]">
                        <Check className="w-4 h-4" />
                        <span>אשר</span>
                      </button>
                    )}
                    {ticket.status !== "rejected" && (
                      <button onClick={() => handleStatusChange("rejected")} disabled={saving} className="btn-danger grow min-w-[90px]">
                        <X className="w-4 h-4" />
                        <span>דחה</span>
                      </button>
                    )}
                    <button onClick={() => setEditMode(true)} disabled={saving} className="btn-cancel grow min-w-[90px]">
                      <Pencil className="w-4 h-4" />
                      <span>ערוך</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Violation analysis */}
          {ticket && ticket.violation_decision && (
            <div className="app-card grow basis-[240px] p-4">
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
                    {ticket.violation_description_en && (
                      <div className="text-theme-xs text-theme-text-muted italic">
                        {ticket.violation_description_en}
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

        </div>{/* end right column */}
      </div>
    </div>
    </div>
    </div>
  );
}
