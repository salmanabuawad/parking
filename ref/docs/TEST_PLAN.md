# Test Plan

## Unit tests

### plate_detector
- yellow mask contains obvious plate sample
- non-yellow object rejected
- aspect ratio filter works
- min area filter works

### tracker
- smooths new detection
- reuses last box when one frame is missing
- clears after too many misses

### ocr_vote
- chooses most frequent valid candidate
- rejects candidates not present in registry
- handles mixed 7-digit / 8-digit noise

### registry_lookup
- normalized lookup works
- non-digit formatting still resolves
- missing plate returns None
- data.gov.il API fallback when plate not in local CSV (fail open if API unavailable)

### plate_format
- 52x12-like ratio → private_long
- 32x16-like ratio → private_rect
- 17x16-like ratio → motorcycle
- 17x12-like ratio → scooter

### curb_detector
- elongated red/white region preferred over small noise

## Integration tests
- process short video and produce output mp4
- debug images created when enabled
- OCR + registry validation returns stable plate on repeated frames

## Manual QA
- inspect final output frame-by-frame
- ensure only target plate remains sharp
- verify validated plate exists in Gov registry
