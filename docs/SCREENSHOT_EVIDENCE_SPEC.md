# Screenshot Evidence Spec

Screenshots must be captured from the blurred player shown to the admin, not from the raw source frame.

## Save with each screenshot
- ticket_id
- frame_timestamp
- display_timestamp_text
- source_video_hash
- capture_user_id
- saved_at
- source_video_id
- player_time_seconds

## UI rules
- render visible timestamp on the screenshot before save
- use source metadata time when available
- otherwise use video-relative timecode
- screenshots become immutable evidence after save
