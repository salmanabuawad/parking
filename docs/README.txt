MASTERPIECE SOLUTION V2

Grounded against the current git code:
- current tickets.py already uses app.dependencies + app.repositories
- current tickets.py still builds processed bytes synchronously
- current review screen still needs to avoid raw fallback
- current video_processor.py is compressed and hard to maintain

This package replaces:
- backend/app/services/video_processor.py
- backend/app/routers/tickets.py
- frontend/src/pages/TicketReview.tsx
- frontend/src/api.ts

What it fixes:
1. Keeps the plate sharp and blurs everything else.
2. Blur happens only after plate detection / tracking.
3. If no plate is detected, the frame is left unchanged instead of risking a wrong blur.
4. Blur size comes from AppConfig.blur_kernel_size through tickets.py.
5. Review screen does not auto-fall back to raw video.
6. Router no longer silently returns raw/file bytes when processed build fails.
