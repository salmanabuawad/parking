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
    <div dir="rtl" style={{ padding: 24, maxWidth: 1100, margin: "0 auto", fontFamily: "Arial, sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h1 style={{ margin: 0 }}>בדיקת דוח #{ticketId}</h1>
        <button onClick={handleReprocess} style={{ padding: "10px 14px", cursor: "pointer" }}>
          עבד מחדש
        </button>
      </div>

      {/* Ticket details panel */}
      {ticket && (
        <div style={{ background: "#fff", border: "1px solid #d7dfeb", borderRadius: 12, padding: "14px 18px", marginBottom: 16, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "8px 24px" }}>
          <div>
            <div style={{ fontSize: 11, color: "#888", marginBottom: 2 }}>מספר לוחית</div>
            {plateOk ? (
              <div style={{ fontWeight: 700, fontSize: 20, letterSpacing: 2 }}>{ticket.license_plate}</div>
            ) : (
              <div>
                <span style={{ fontWeight: 600, color: "#dc2626" }}>לא זוהה</span>
                {ticket.plate_detection_reason && (
                  <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>{ticket.plate_detection_reason}</div>
                )}
              </div>
            )}
          </div>
          <div>
            <div style={{ fontSize: 11, color: "#888", marginBottom: 2 }}>סטטוס</div>
            <div style={{ fontWeight: 600 }}>{ticket.status}</div>
          </div>
          {ticket.violation_zone && (
            <div>
              <div style={{ fontSize: 11, color: "#888", marginBottom: 2 }}>אזור עצירה</div>
              <div>{ticket.violation_zone}</div>
            </div>
          )}
          {ticket.location && (
            <div>
              <div style={{ fontSize: 11, color: "#888", marginBottom: 2 }}>מיקום</div>
              <div>{ticket.location}</div>
            </div>
          )}
          {ticket.captured_at && (
            <div>
              <div style={{ fontSize: 11, color: "#888", marginBottom: 2 }}>זמן צילום</div>
              <div>{new Date(ticket.captured_at).toLocaleString("he-IL")}</div>
            </div>
          )}
          {ticket.fine_amount != null && (
            <div>
              <div style={{ fontSize: 11, color: "#888", marginBottom: 2 }}>קנס</div>
              <div>₪{ticket.fine_amount}</div>
            </div>
          )}
          {ticket.admin_notes && (
            <div style={{ gridColumn: "1 / -1" }}>
              <div style={{ fontSize: 11, color: "#888", marginBottom: 2 }}>הערות</div>
              <div>{ticket.admin_notes}</div>
            </div>
          )}
        </div>
      )}

      {state === "loading" && <div>טוען…</div>}
      {state === "error" && <div style={{ color: "crimson", marginBottom: 8 }}>שגיאה: {error}</div>}

      <div
        style={{
          border: "1px solid #ddd",
          borderRadius: 12,
          padding: 16,
          background: "#fff",
          boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
        }}
      >
        {videoUrl ? (
          <video
            key={videoUrl}
            src={videoUrl}
            controls
            playsInline
            style={{ width: "100%", maxHeight: 560, borderRadius: 8, background: "#000" }}
          />
        ) : (
          <div style={{ padding: 24, background: "#fafafa", borderRadius: 8 }}>
            אין וידאו זמין להצגה.
          </div>
        )}
      </div>
    </div>
  );
}
