export const API_BASE =
  (import.meta as any).env?.VITE_API_BASE_URL ||
  (window as any).__API_BASE__ ||
  "";

function buildUrl(path: string): string {
  const left = API_BASE.replace(/\/$/, "");
  const right = path.startsWith("/") ? path : `/${path}`;
  return `${left}${right}`;
}

async function fetchBlob(path: string): Promise<Blob> {
  const res = await fetch(buildUrl(path), { credentials: "include" });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return await res.blob();
}

async function fetchJson(path: string, init?: RequestInit): Promise<any> {
  const res = await fetch(buildUrl(path), {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      detail = data?.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return await res.json();
}

export const ticketsApi = {
  getVideo(ticketId: number | string) {
    return fetchBlob(`/tickets/${ticketId}/video`);
  },

  getProcessedVideo(ticketId: number | string) {
    return fetchBlob(`/tickets/${ticketId}/processed-video`);
  },

  getRawVideo(ticketId: number | string) {
    return fetchBlob(`/tickets/${ticketId}/raw-video`);
  },

  reprocessVideo(ticketId: number | string) {
    return fetchJson(`/tickets/${ticketId}/reprocess-video`, { method: "POST" });
  },
};
