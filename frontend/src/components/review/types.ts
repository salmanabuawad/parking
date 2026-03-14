export interface TicketReviewRecord {
  id: number
  license_plate: string
  plate_detection_reason?: string | null
  location?: string | null
  violation_zone?: string | null
  description?: string | null
  admin_notes?: string | null
  fine_amount?: number | null
  status: string
  video_id?: number | null
  processed_video_id?: number | null
  video_path?: string | null
  ticket_image_path?: string | null
  created_at?: string | null
  reviewed_at?: string | null
  captured_at?: string | null
  video_params?: Record<string, unknown> | null
}

export interface ScreenshotRecord {
  id: number | string
  ticket_id?: number
  image_url?: string
  taken_at_iso?: string | null
  frame_time_sec?: number | null
  persisted?: boolean
}
