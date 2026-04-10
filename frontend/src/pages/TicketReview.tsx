import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
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
    <div style={{ marginBottom: 6 }}>
      <div style={{ fontSize: 10, color: "var(--app-text-muted)", marginBottom: 1, textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
      <div>{children}</div>
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  pending_review: "#d97706",
  approved: "#16a34a",
  rejected: "#dc2626",
  paid: "#2563eb",
};

const STATUS_LABELS: Record<string, string> = {
  pending_review: "ממתין לבדיקה",
  approved: "אושר",
  rejected: "נדחה",
  paid: "שולם",
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

  async function handleReprocess() {
    try {
      setState("loading");
      setError(null);
      await ticketsApi.reprocessVideo(ticketId);
      const blob = await ticketsApi.getProcessedVideo(ticketId);
      const url = URL.createObjectURL(blob);
      setVideoUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return url;
      });
      setState("ready");
    } catch (err: any) {
      setState("error");
      setError(err?.message || "Reprocessing failed");
    }
  }

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

  return (
    <div className="page-fill">
    <div className="page-body-scroll">
    <div dir="rtl" style={{ padding: 24, width: '100%', boxSizing: 'border-box', fontFamily: "Arial, sans-serif", color: "var(--app-text)" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <h1 style={{ margin: 0, fontSize: 22 }}>בדיקת דוח #{ticketId}</h1>
          <Link to="/queue" style={{ fontSize: 13, color: "var(--app-accent)" }}>← תור עיבוד</Link>
          <Link to="/tickets" style={{ fontSize: 13, color: "var(--app-accent)" }}>← כל הדוחות</Link>
        </div>
      </div>

      {state === "error" && (
        <div style={{ color: "var(--app-danger)", marginBottom: 12, padding: "8px 12px", background: "var(--app-warning-bg)", border: "1px solid var(--app-border)", borderRadius: 6 }}>
          שגיאה: {error}
        </div>
      )}

      {/* Side-by-side: video + details */}
      <div style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>

        {/* Left column: violation analysis + video */}
        <div style={{ flex: "1 1 340px", minWidth: 280, display: "flex", flexDirection: "column", gap: 16 }}>

        {/* Video panel */}
        <div>
          <div style={{ border: "1px solid var(--app-border)", borderRadius: 10, overflow: "hidden", background: "#000" }}>
            {videoUrl ? (
              <video
                ref={videoRef}
                key={videoUrl}
                src={videoUrl}
                controls
                playsInline
                style={{ width: "100%", maxHeight: 320, display: "block" }}
              />
            ) : (
              <div style={{ padding: 32, textAlign: "center", color: "var(--app-text-muted)", background: "#111" }}>
                {state === "loading" ? "טוען וידאו…" : "אין וידאו זמין"}
              </div>
            )}
          <canvas ref={canvasRef} style={{ display: "none" }} />
          {videoUrl && (
            <div style={{ padding: "10px 12px", background: "var(--app-header-start)", display: "flex", alignItems: "center", gap: 10 }}>
              <button
                onClick={captureScreenshot}
                disabled={capturing || state !== "ready"}
                style={{
                  padding: "7px 16px",
                  background: capturing ? "var(--app-text-muted)" : "var(--app-accent)",
                  color: "#fff",
                  border: "none",
                  borderRadius: 6,
                  cursor: capturing ? "not-allowed" : "pointer",
                  fontFamily: "inherit",
                  fontSize: "0.9rem",
                  fontWeight: 600,
                }}
              >
                {capturing ? "שומר…" : "📸 צלם תמונה"}
              </button>
              {captureMsg && (
                <span style={{ fontSize: "0.85rem", color: captureMsg.startsWith("✓") ? "#4ade80" : "#f87171" }}>
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
                  style={{
                    padding: "7px 16px",
                    background: "#374151",
                    color: "#fff",
                    border: "none",
                    borderRadius: 6,
                    cursor: "pointer",
                    fontFamily: "inherit",
                    fontSize: "0.9rem",
                    fontWeight: 600,
                    marginRight: "auto",
                  }}
                >
                  ⬇️ הורד מקורי
                </button>
              )}
            </div>
          )}
          </div>
        </div>

        {/* Screenshot gallery — under video */}
        {(screenshots.length > 0 || videoUrl) && (
          <div style={{ background: "var(--app-surface)", border: "1px solid var(--app-border)", borderRadius: 10, padding: "18px 22px" }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>
              צילומי מסך {screenshots.length > 0 ? `(${screenshots.length})` : ""}
            </h3>
            {screenshots.length === 0 ? (
              <p style={{ color: "var(--app-text-muted)", fontSize: 13, margin: 0 }}>עדיין אין צילומים — לחץ "📸 צלם תמונה" בעת השמעת הוידאו</p>
            ) : (
              <>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  {screenshots.map((s) => (
                    <div
                      key={s.id}
                      onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                      style={{ cursor: "pointer", borderRadius: 8, overflow: "hidden", border: expanded === s.id ? "2px solid var(--app-accent)" : "2px solid transparent", background: "var(--app-surface-muted)" }}
                    >
                      <img
                        src={ticketsApi.screenshotImageUrl(ticketId, s.id)}
                        alt={`Screenshot ${s.id}`}
                        style={{ width: 140, height: 80, objectFit: "cover", display: "block" }}
                        loading="lazy"
                      />
                      <div style={{ fontSize: 11, textAlign: "center", padding: "3px 4px", color: "var(--app-text-muted)", lineHeight: 1.3 }}>
                        {s.frame_time_seconds != null && ticket?.captured_at
                          ? new Date(new Date(ticket.captured_at).getTime() + s.frame_time_seconds * 1000)
                              .toLocaleString("he-IL", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" })
                          : s.frame_time_seconds != null ? `+${s.frame_time_seconds.toFixed(1)}s` : "—"}
                      </div>
                    </div>
                  ))}
                </div>
                {expanded !== null && (
                  <div style={{ marginTop: 12, borderRadius: 8, overflow: "hidden", border: "1px solid var(--app-border)" }}>
                    <img
                      src={ticketsApi.screenshotImageUrl(ticketId, expanded)}
                      alt="Expanded screenshot"
                      style={{ width: "100%", display: "block" }}
                    />
                  </div>
                )}
              </>
            )}
          </div>
        )}

        </div>{/* end left column */}

        {/* Right section: violation analysis + details side by side */}
        <div style={{ flex: "1 1 320px", display: "flex", flexDirection: "row", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>

        {ticket && (
          <div style={{ flex: "1 1 240px", background: "var(--app-surface)", border: "1px solid var(--app-border)", borderRadius: 10, padding: "12px 16px", position: "sticky", top: 88 }}>

            {/* Plate */}
            <Field label="מספר לוחית">
              {editMode ? (
                <input
                  value={editPlate}
                  onChange={e => setEditPlate(e.target.value)}
                  style={{ fontFamily: "monospace", fontSize: 18, padding: "4px 8px", border: "1px solid var(--app-border)", borderRadius: 4, width: "100%", background: "var(--app-surface)", color: "var(--app-text)" }}
                />
              ) : plateOk ? (
                <div>
                  <span style={{ fontWeight: 700, fontSize: 20, letterSpacing: 3, fontFamily: "monospace" }}>
                    {ticket.license_plate}
                  </span>
                  {ticket.plate_detection_reason && (
                    <div style={{ fontSize: 12, color: "var(--app-warning-text)", marginTop: 4, background: "var(--app-warning-bg)", padding: "4px 8px", borderRadius: 4 }}>
                      ⚠ {ticket.plate_detection_reason}
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <span style={{ fontWeight: 600, color: "#dc2626" }}>לא זוהה</span>
                  {ticket.plate_detection_reason && (
                    <div style={{ fontSize: 12, color: "var(--app-text-muted)", marginTop: 4 }}>{ticket.plate_detection_reason}</div>
                  )}
                </div>
              )}
            </Field>

            <div style={{ borderTop: "1px solid var(--app-border)", margin: "6px 0" }} />

            {/* Status */}
            <Field label="סטטוס">
              <span style={{
                fontWeight: 600,
                color: STATUS_COLORS[ticket.status] || "#374151",
                background: "var(--app-surface-muted)",
                padding: "2px 10px",
                borderRadius: 12,
                fontSize: 14,
              }}>
                {STATUS_LABELS[ticket.status] || ticket.status}
              </span>
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
                <input
                  type="number"
                  value={editFine}
                  onChange={e => setEditFine(e.target.value)}
                  placeholder="סכום ₪"
                  style={{ padding: "4px 8px", border: "1px solid var(--app-border)", borderRadius: 4, width: 120, background: "var(--app-surface)", color: "var(--app-text)" }}
                />
              ) : ticket.fine_amount != null ? (
                <span style={{ fontWeight: 600, color: "#dc2626" }}>₪{ticket.fine_amount}</span>
              ) : (
                <span style={{ color: "var(--app-text-muted)", fontSize: 13 }}>לא נקבע</span>
              )}
            </Field>

            <div style={{ borderTop: "1px solid var(--app-border)", margin: "6px 0" }} />

            {/* Location */}
            {ticket.location && (
              <Field label="מיקום">
                <span style={{ fontSize: 13, color: "var(--app-text)" }}>{ticket.location}</span>
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
                <span style={{ fontSize: 13, color: "var(--app-text)" }}>{ticket.description}</span>
              </Field>
            )}

            {/* Admin notes */}
            <div style={{ borderTop: "1px solid var(--app-border)", margin: "6px 0" }} />
            <Field label="הערות מנהל">
              {editMode ? (
                <textarea
                  value={editNotes}
                  onChange={e => setEditNotes(e.target.value)}
                  rows={3}
                  style={{ width: "100%", padding: "6px 8px", border: "1px solid var(--app-border)", borderRadius: 4, fontSize: 13, resize: "vertical", background: "var(--app-surface)", color: "var(--app-text)" }}
                />
              ) : ticket.admin_notes ? (
                <span style={{ fontSize: 13 }}>{ticket.admin_notes}</span>
              ) : (
                <span style={{ color: "var(--app-text-muted)", fontSize: 13 }}>אין הערות</span>
              )}
            </Field>

            {/* Admin action buttons */}
            <div style={{ borderTop: "1px solid var(--app-border)", marginTop: 8, paddingTop: 8 }}>
              {editMode ? (
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    onClick={handleSaveEdit}
                    disabled={saving}
                    style={{ flex: 1, padding: "8px 0", borderRadius: 6, border: "none", background: "var(--app-accent)", color: "#fff", fontWeight: 600, cursor: "pointer" }}
                  >
                    {saving ? "שומר…" : "שמור"}
                  </button>
                  <button
                    onClick={() => { setEditMode(false); setEditNotes(ticket.admin_notes || ""); setEditFine(ticket.fine_amount != null ? String(ticket.fine_amount) : ""); setEditPlate(ticket.license_plate || ""); }}
                    disabled={saving}
                    style={{ flex: 1, padding: "8px 0", borderRadius: 6, border: "1px solid var(--app-border)", background: "var(--app-surface-muted)", color: "var(--app-text)", cursor: "pointer" }}
                  >
                    ביטול
                  </button>
                </div>
              ) : (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {ticket.status !== "approved" && (
                    <button
                      onClick={() => handleStatusChange("approved")}
                      disabled={saving}
                      style={{ flex: 1, minWidth: 90, padding: "8px 0", borderRadius: 6, border: "none", background: "var(--app-success)", color: "#fff", fontWeight: 600, cursor: "pointer" }}
                    >
                      ✓ אשר
                    </button>
                  )}
                  {ticket.status !== "rejected" && (
                    <button
                      onClick={() => handleStatusChange("rejected")}
                      disabled={saving}
                      style={{ flex: 1, minWidth: 90, padding: "8px 0", borderRadius: 6, border: "none", background: "var(--app-danger)", color: "#fff", fontWeight: 600, cursor: "pointer" }}
                    >
                      ✗ דחה
                    </button>
                  )}
                  <button
                    onClick={() => setEditMode(true)}
                    disabled={saving}
                    style={{ flex: 1, minWidth: 90, padding: "8px 0", borderRadius: 6, border: "1px solid var(--app-border)", background: "var(--app-surface-muted)", color: "var(--app-text)", cursor: "pointer" }}
                  >
                    ✎ ערוך
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Violation analysis */}
        {ticket && ticket.violation_decision && (
          <div style={{ flex: "1 1 240px", background: "var(--app-surface)", border: "1px solid var(--app-border)", borderRadius: 10, padding: "18px 22px" }}>
            <h3 style={{ margin: "0 0 14px", fontSize: 16 }}>ניתוח הפרה אוטומטי</h3>
            {(() => {
              const dec = ticket.violation_decision!;
              const conf = ticket.violation_confidence ?? 0;
              const color = dec === "confirmed_violation" ? "var(--app-danger)"
                : dec === "suspected_violation" ? "#d97706"
                : dec === "no_violation" ? "var(--app-success)"
                : "var(--app-text-muted)";
              const badgeBg = dec === "confirmed_violation"
                ? "rgba(185, 28, 28, 0.15)"
                : dec === "suspected_violation"
                  ? "rgba(217, 119, 6, 0.15)"
                  : dec === "no_violation"
                    ? "rgba(21, 128, 61, 0.15)"
                    : "var(--app-surface-muted)";
              const labelHe = dec === "confirmed_violation" ? "הפרה מאושרת"
                : dec === "suspected_violation" ? "הפרה חשודה"
                : dec === "no_violation" ? "ללא הפרה"
                : "עדויות לא מספיקות";
              return (
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10, flexWrap: "wrap" }}>
                    <span style={{ fontWeight: 700, fontSize: 15, color, background: badgeBg, padding: "3px 12px", borderRadius: 12 }}>
                      {labelHe}
                    </span>
                    {ticket.violation_rule_id && (
                      <span style={{ fontSize: 12, color: "var(--app-text-muted)", fontFamily: "monospace" }}>{ticket.violation_rule_id}</span>
                    )}
                    <span style={{ fontSize: 12, color: "var(--app-text-muted)" }}>ביטחון: {Math.round(conf * 100)}%</span>
                  </div>
                  <div style={{ height: 6, background: "var(--app-surface-muted)", borderRadius: 3, marginBottom: 10 }}>
                    <div style={{ height: "100%", width: `${Math.round(conf * 100)}%`, background: color, borderRadius: 3 }} />
                  </div>
                  {ticket.violation_description_he && (
                    <div style={{ fontSize: 13, color: "var(--app-text)", marginBottom: 6, lineHeight: 1.5 }}>
                      {ticket.violation_description_he}
                    </div>
                  )}
                  {ticket.violation_description_en && (
                    <div style={{ fontSize: 12, color: "var(--app-text-muted)", fontStyle: "italic" }}>
                      {ticket.violation_description_en}
                    </div>
                  )}
                  <div style={{ marginTop: 10, fontSize: 11, color: "var(--app-text-muted)" }}>
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
