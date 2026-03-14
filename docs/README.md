# Backend blur fix patch

This patch fixes the main reasons the UI can still show the original video:

- `GET /tickets/{id}/video` now prefers a true processed source in this order:
  1. `processed_video_id`
  2. filesystem path only when it is clearly under `processed/`
  3. otherwise rebuild from raw DB video
- `reprocess-ticket-video` always writes to `processed/ticket_<id>.mp4`
- `reprocess-ticket-video` now uses the DB blur value from `AppConfig.blur_kernel_size`
- `video_processor.py` is cleaned up so it is explicitly a plate-redaction processor, not an old whole-frame privacy flow
- fallback encoding paths normalize the blur kernel instead of hardcoding old values

## Files
- `backend/app/routers/tickets.py`
- `backend/app/services/video_processor.py`

## Apply
Copy the files into the repo, restart the backend, and then reprocess one ticket.

## Expected result
- Ticket review should load the blurred processed video instead of the raw original
- Larger `blur_kernel_size` values in DB should visibly increase blur strength
- Reprocessing should consistently store output under `videos/processed/...`
