import axios, { AxiosInstance } from 'axios'

// Backend at http://localhost:8000; all routes under /api.
export function getApiBase(): string {
  const env = import.meta.env.VITE_API_URL
  const origin = env || 'http://localhost:8000'
  const base = origin.replace(/\/$/, '')
  return base.endsWith('/api') ? base : `${base}/api`
}

const api: AxiosInstance = axios.create({
  baseURL: getApiBase(),
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('parking_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export const ticketsApi = {
  list: (statusFilter?: string) => api.get('tickets', { params: statusFilter ? { status_filter: statusFilter } : {} }),
  get: (id: string) => api.get(`tickets/${id}`),
  update: (id: string, data: Record<string, unknown>) => api.patch(`tickets/${id}`, data),
  ticketVideoUrl: (id: string, token: string | null, useProcessed?: boolean, cacheBust?: number) => {
    const base = getApiBase().replace(/\/$/, '')
    const path = useProcessed ? `tickets/${id}/processed-video` : `tickets/${id}/video`
    const params = new URLSearchParams({ token: token || '' })
    if (cacheBust) params.set('t', String(cacheBust))
    return `${base}/${path}?${params}`
  },
  imageUrl: (id: string) => `${getApiBase().replace(/\/$/, '')}/tickets/${id}/image`,
  getVideo: (id: string, cacheBust?: number) => api.get(`tickets/${id}/video`, { responseType: 'blob', params: { ...(cacheBust ? { t: cacheBust } : {}) } }),
  getProcessedVideo: (id: string, cacheBust?: number) => api.get(`tickets/${id}/processed-video`, { responseType: 'blob', params: { ...(cacheBust ? { t: cacheBust } : {}) } }),
  getRawVideo: (id: string, cacheBust?: number) => api.get(`tickets/${id}/raw-video`, { responseType: 'blob', params: { ...(cacheBust ? { t: cacheBust } : {}) } }),
  reprocessVideo: (id: string) => api.post(`tickets/${id}/reprocess-video`),
  getImage: (id: string) => api.get(`tickets/${id}/image`, { responseType: 'blob' }),
  saveScreenshot: (id: string, data: { image_base64: string; frame_time_sec: number; captured_at: string }) =>
    api.post(`tickets/${id}/screenshots`, data),
  listScreenshots: (id: string) => api.get(`tickets/${id}/screenshots`),
  deleteScreenshot: (ticketId: string, screenshotId: string | number) => api.delete(`tickets/${ticketId}/screenshots/${screenshotId}`),
  /** Fetch screenshot image with auth (Bearer). Use responseType blob and createObjectURL for <img>. */
  getScreenshotImage: (ticketId: string, screenshotId: number | string) =>
    api.get(`tickets/${ticketId}/screenshots/${screenshotId}/image`, { responseType: 'blob' }),
}

export const uploadApi = {
  getJobStatus: (jobId: string) => api.get(`upload/job/${jobId}`),
  listJobs: (limit = 50) => api.get('upload/jobs', { params: { limit } }),
  rerunJob: (jobId: number) => api.post(`upload/job/${jobId}/rerun`),
  resetStuckJobs: () => api.post('upload/reset-stuck-jobs'),
}

export const settingsApi = {
  get: () => api.get('settings'),
  update: (data: Record<string, unknown>) => api.patch('settings', data),
}

export const camerasApi = {
  list: (activeOnly = false) => api.get('cameras', { params: activeOnly ? { active_only: true } : {} }),
  get: (id: number) => api.get(`cameras/${id}`),
  create: (data: Record<string, unknown>) => api.post('cameras', data),
  update: (id: number, data: Record<string, unknown>) => api.patch(`cameras/${id}`, data),
  delete: (id: number) => api.delete(`cameras/${id}`),
}

export default api
