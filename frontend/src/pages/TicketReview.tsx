import React, { useEffect, useMemo, useState } from "react";
import { ticketsApi } from "../api";

type LoadState = "idle" | "loading" | "ready" | "error";

export default function TicketReview() {
  const ticketId = useMemo(() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    return parts[parts.length - 1];
  }, []);

  const [videoUrl, setVideoUrl] = useState<string>("");
  const [state, setState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let currentUrl = "";
    let cancelled = false;

    async function load() {
      setState("loading");
      setError(null);

      try {
        const blob = await ticketsApi.getProcessedVideo(ticketId);
        if (cancelled) return;
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

  return (
    <div dir="rtl" style={{ padding: 24, maxWidth: 1100, margin: "0 auto", fontFamily: "Arial, sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h1 style={{ margin: 0 }}>בדיקת דוח</h1>
        <button onClick={handleReprocess} style={{ padding: "10px 14px", cursor: "pointer" }}>
          עבד מחדש
        </button>
      </div>

      {state === "loading" && <div>טוען וידאו מעובד…</div>}
      {state === "error" && <div style={{ color: "crimson" }}>שגיאה: {error}</div>}

      <div
        style={{
          marginTop: 16,
          border: "1px solid #ddd",
          borderRadius: 12,
          padding: 16,
          background: "#fff",
          boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
        }}
      >
        <div style={{ marginBottom: 12, color: "#555" }}>
          במסך זה מוצג רק וידאו מעובד. אין fallback אוטומטי לוידאו המקורי.
        </div>

        {videoUrl ? (
          <video
            key={videoUrl}
            src={videoUrl}
            controls
            playsInline
            style={{
              width: "100%",
              maxHeight: 560,
              borderRadius: 8,
              background: "#000",
            }}
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
