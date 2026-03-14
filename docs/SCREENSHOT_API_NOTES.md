# Ticket screenshot backend patch

This patch adds storage-backed screenshot attachments for tickets.

## What it adds
- `POST /api/tickets/{ticket_id}/screenshots`
- `GET /api/tickets/{ticket_id}/screenshots`
- `GET /api/tickets/{ticket_id}/screenshots/{screenshot_id}/image`
- `DELETE /api/tickets/{ticket_id}/screenshots/{screenshot_id}`
- `ticket_screenshots` table
- filesystem storage under `VIDEOS_DIR/screenshots/ticket_{id}/`

## Expected frontend payload

```json
{
  "image_base64": "data:image/png;base64,...",
  "frame_time_seconds": 12.48,
  "video_timestamp": "2026-03-14T10:22:31+02:00",
  "source_video_id": "ticket-123-processed"
}
```

## Important behavior
- screenshots are saved exactly as received from the UI
- the UI should send the **blurred** rendered image, not a raw frame
- the timestamp should already be burned into the screenshot image on the frontend
- the backend stores metadata so the screenshot is attached to the ticket

## Migration
Run:

```bash
python migrate_ticket_screenshots.py
```

## Frontend wiring
Use the created endpoint after the operator presses the screenshot button.
Then refresh the screenshot list with:

```text
GET /api/tickets/{ticket_id}/screenshots
```
