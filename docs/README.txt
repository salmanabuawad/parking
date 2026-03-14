MASTERPIECE SOLUTION PACKAGE

Grounded against the current repo structure:
- backend tickets router already uses app.dependencies + app.repositories
- review page still falls back to raw in the current repo
- current router still serves processed bytes synchronously

This package replaces:
- backend/app/services/video_processor.py
- backend/app/routers/tickets.py
- frontend/src/pages/TicketReview.tsx
- frontend/src/api.ts

What it changes:
1. The processed review video keeps the plate sharp and blurs everything else.
2. Blur is applied only after plate detection / temporal tracking.
3. If plate detection is missing, frame is left unchanged rather than blurring the plate.
4. Blur size comes from AppConfig.blur_kernel_size through tickets.py.
5. Review screen no longer auto-falls back to raw video.
6. Router no longer silently returns raw/file bytes when processed build fails.

Apply, restart backend/frontend, then call reprocess-video for at least one ticket.
