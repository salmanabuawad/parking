
export interface TicketReviewRecord {
  id: number
  status: string
  created_at?: string
  license_plate?: string
  location?: string
  violation_zone?: string
  description?: string
  admin_notes?: string
  fine_amount?: number | null
  video_id?: string | null
  video_path?: string | null
  plate_detection_reason?: string | null
  video_params?: Record<string, unknown> | null
}
