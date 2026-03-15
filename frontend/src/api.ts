export const API_BASE =
  (import.meta as any).env?.VITE_API_BASE_URL ||
  (window as any).__API_BASE__ ||
  "";

export function getApiBase(): string {
  return API_BASE;
}

function buildUrl(path: string): string {
  const left = API_BASE.replace(/\/$/, "");
  const right = path.startsWith("/") ? path : `/${path}`;
  // Auto-prefix with /api unless already present
  const apiRight = right.startsWith("/api") ? right : `/api${right}`;
  return `${left}${apiRight}`;
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = localStorage.getItem("parking_token");
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

async function fetchBlob(path: string): Promise<Blob> {
  const res = await fetch(buildUrl(path), {
    credentials: "include",
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return await res.blob();
}

async function fetchJson(path: string, init?: RequestInit): Promise<any> {
  const isFormData = init?.body instanceof FormData;
  const res = await fetch(buildUrl(path), {
    credentials: "include",
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...authHeaders(init?.headers as Record<string, string>),
    },
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

// Default export: axios-style wrapper used by AuthContext, Upload, QueueMaintenance
const api = {
  async post<T = any>(
    path: string,
    body?: unknown,
    options?: { headers?: Record<string, string> }
  ): Promise<{ data: T }> {
    const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
    const res = await fetch(buildUrl(path), {
      method: "POST",
      credentials: "include",
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...authHeaders(options?.headers),
      },
      body: isFormData ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const d = await res.json();
        detail = d?.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }
    const data: T = await res.json();
    return { data };
  },
};

export default api;

export const ticketsApi = {
  list(status?: string): Promise<{ data: any[] }> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return fetchJson(`/tickets${qs}`).then((data) => ({ data }));
  },
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

export const camerasApi = {
  list(): Promise<{ data: any[] }> {
    return fetchJson("/cameras").then((data) => ({ data }));
  },
  create(payload: unknown): Promise<{ data: any }> {
    return fetchJson("/cameras", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((data) => ({ data }));
  },
  update(id: number, payload: unknown): Promise<{ data: any }> {
    return fetchJson(`/cameras/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }).then((data) => ({ data }));
  },
  delete(id: number): Promise<{ data: any }> {
    return fetchJson(`/cameras/${id}`, { method: "DELETE" }).then((data) => ({ data }));
  },
};

export const settingsApi = {
  get(): Promise<{ data: any }> {
    return fetchJson("/settings").then((data) => ({ data }));
  },
  update(payload: unknown): Promise<{ data: any }> {
    return fetchJson("/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }).then((data) => ({ data }));
  },
};

export const uploadApi = {
  listJobs(limit = 50): Promise<{ data: any[] }> {
    return fetchJson(`/upload/jobs?limit=${limit}`).then((data) => ({ data }));
  },
  resetStuckJobs(): Promise<{ data: any }> {
    return fetchJson("/upload/reset-stuck", { method: "POST" }).then((data) => ({ data }));
  },
  rerunJob(jobId: number): Promise<{ data: any }> {
    return fetchJson(`/upload/jobs/${jobId}/rerun`, { method: "POST" }).then((data) => ({ data }));
  },
};
