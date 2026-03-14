# Final Implementation Checklist

## Backend
- [ ] Replace largest-vehicle selection with target ranking
- [ ] Add video metadata extraction
- [ ] Add curb periodicity reasoning using 100cm / 15cm prior
- [ ] Add parking-vs-traffic-stop logic
- [ ] Add dedicated plate detector model path
- [ ] Add plate rectification and OCR crop quality gates
- [ ] Add multi-hypothesis OCR and digit-level voting
- [ ] Add registry client for data.gov.il
- [ ] Add make/model/color validation
- [ ] Add confidence engine with explicit reasons
- [ ] Add evidence writer and screenshot persistence

## Frontend
- [ ] Hebrew RTL conversion
- [ ] Smaller review video player
- [ ] Evidence sidebar with decision actions
- [ ] Screenshot capture from blurred player
- [ ] Timestamp overlay on screenshots
- [ ] Screenshot gallery
- [ ] Confidence badges
- [ ] Ticket review timeline
- [ ] Keyboard shortcuts for operators

## Decision policy
- [ ] Confirm only when OCR + registry + visual match agree
- [ ] Downgrade when traffic stop is plausible
- [ ] Mark not_100_percent_sure when any major conflict exists
