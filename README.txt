Frontend-only patch grounded to the current repo structure of salmanabuawad/parking.

This patch replaces the current TicketReview page with:
- Hebrew RTL layout
- smaller video window
- processed/blurred video preference
- screenshot capture from the blurred player with timestamp overlay
- evidence sidebar
- screenshot strip

It also adds:
- Hebrew nav labels in App.tsx
- Hebrew Tickets page
- Hebrew Home page
- API helper for screenshot save
- Hebrew dictionary and RTL hook

Copy the files into the matching paths under frontend/src/.
