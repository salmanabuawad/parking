import React, { useEffect, useMemo, useState } from "react";
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
}

const PLATE_UNKNOWN = "11111";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 11, color: "#888", marginBottom: 3, textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
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

export default function TicketReview() {
  const ticketId = useMemo(() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    return parts[parts.length - 1];
  }, []);

  const [videoUrl, setVideoUrl] = useState<string>("");
  const [state, setState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [ticket, setTicket] = useState<TicketDetail | null>(null);

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
        if (detail) setTicket(detail);
        const url = URL.createObjectURL(blob);
        currentUrl = url;
        setVideoUrl(url);
        setState("ready");
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

  const plateOk = ticket && ticket.license_plate && ticket.license_plate !== PLATE_UNKNOWN;

  return (
    <div dir="rtl" style={{ padding: 24, maxWidth: 1200, margin: "0 auto", fontFamily: "Arial, sans-serif" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>בדיקת דוח #{ticketId}</h1>
        <button
          onClick={handleReprocess}
          disabled={state === "loading"}
          style={{ padding: "8px 16px", cursor: "pointer", borderRadius: 6, border: "1px solid #d1d5db", background: "#f9fafb" }}
        >
          {state === "loading" ? "טוען…" : "עבד מחדש"}
        </button>
      </div>

      {state === "error" && (
        <div style={{ color: "crimson", marginBottom: 12, padding: "8px 12px", background: "#fef2f2", borderRadius: 6 }}>
          שגיאה: {error}
        </div>
      )}

      {/* Side-by-side: video + details */}
      <div style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>

        {/* Video panel */}
        <div style={{ flex: "1 1 340px", minWidth: 280 }}>
          <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, overflow: "hidden", background: "#000" }}>
            {videoUrl ? (
              <video
                key={videoUrl}
                src={videoUrl}
                controls
                playsInline
                style={{ width: "100%", maxHeight: 320, display: "block" }}
              />
            ) : (
              <div style={{ padding: 32, textAlign: "center", color: "#9ca3af", background: "#111" }}>
                {state === "loading" ? "טוען וידאו…" : "אין וידאו זמין"}
              </div>
            )}
          </div>
        </div>

        {/* Details panel */}
        {ticket && (
          <div style={{ flex: "1 1 320px", background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: "18px 22px" }}>

            {/* Plate */}
            <Field label="מספר לוחית">
              {plateOk ? (
                <div>
                  <span style={{ fontWeight: 700, fontSize: 24, letterSpacing: 3, fontFamily: "monospace" }}>
                    {ticket.license_plate}
                  </span>
                  {ticket.plate_detection_reason && (
                    <div style={{ fontSize: 12, color: "#b45309", marginTop: 4, background: "#fffbeb", padding: "4px 8px", borderRadius: 4 }}>
                      ⚠ {ticket.plate_detection_reason}
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <span style={{ fontWeight: 600, color: "#dc2626" }}>לא זוהה</span>
                  {ticket.plate_detection_reason && (
                    <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>{ticket.plate_detection_reason}</div>
                  )}
                </div>
              )}
            </Field>

            <div style={{ borderTop: "1px solid #f1f5f9", margin: "12px 0" }} />

            {/* Status */}
            <Field label="סטטוס">
              <span style={{
                fontWeight: 600,
                color: STATUS_COLORS[ticket.status] || "#374151",
                background: "#f8fafc",
                padding: "2px 10px",
                borderRadius: 12,
                fontSize: 14,
              }}>
                {ticket.status}
              </span>
            </Field>

            {/* Violation zone */}
            {ticket.violation_zone && (
              <Field label="אזור עצירה">
                <span>{ticket.violation_zone}</span>
              </Field>
            )}

            {/* Fine */}
            {ticket.fine_amount != null && (
              <Field label="קנס">
                <span style={{ fontWeight: 600, color: "#dc2626" }}>₪{ticket.fine_amount}</span>
              </Field>
            )}

            <div style={{ borderTop: "1px solid #f1f5f9", margin: "12px 0" }} />

            {/* Location */}
            {ticket.location && (
              <Field label="מיקום">
                <span style={{ fontSize: 13, color: "#374151" }}>{ticket.location}</span>
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
                <span style={{ fontSize: 13, color: "#4b5563" }}>{ticket.description}</span>
              </Field>
            )}

            {/* Admin notes */}
            {ticket.admin_notes && (
              <>
                <div style={{ borderTop: "1px solid #f1f5f9", margin: "12px 0" }} />
                <Field label="הערות מנהל">
                  <span style={{ fontSize: 13 }}>{ticket.admin_notes}</span>
                </Field>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
