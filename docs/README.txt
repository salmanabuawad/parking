ALL NEEDED FIXES

Included files:
- backend/app/services/video_processor.py
- backend/app/routers/tickets.py
- frontend/src/pages/TicketReview.tsx
- frontend/src/api.ts

What this package fixes:
1. Review video blurs everything except the detected/tracked plate.
2. Blur happens only after plate detection.
3. If there is no plate detection, frame stays unchanged instead of blurring the plate by mistake.
4. Blur strength comes from AppConfig.blur_kernel_size via tickets router.
5. Review screen no longer falls back automatically to raw video.
6. Tickets router no longer silently returns raw/file bytes when processed build fails.
