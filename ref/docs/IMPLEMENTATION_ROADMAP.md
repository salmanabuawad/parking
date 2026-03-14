# Implementation Roadmap

## Phase 1 — working masterpiece core ✓
Implemented:
- HSV detector (HSV 12–45, ratio 1.8–6.5, min_area 300, max_plate_area_ratio 0.12)
- tracker
- OCR reader (Tesseract, black-on-yellow preprocessing)
- OCR voting
- Gov registry validation (local CSV + data.gov.il API fallback)
- plate format classification
- blur pipeline
- debug writer
- **Fast HSV pipeline** (optional): skip YOLO, HSV-only plates

## Phase 2 — stronger detection
Add:
- YOLO detector backend
- confidence-weighted OCR vote
- fallback detector scoring
- better contour heuristics

## Phase 3 — curb logic ✓
Implemented:
- red/white HSV masks (hue 0–12 & 165–180 for red; sat ≤70, val ≥170 for white)
- morphology open/close
- elongated candidate filter (aspect ≥2.5, area ≥800)
- red+white pixel balance scoring

Future:
- curb polyline fit
- pixel distance
- optional cm conversion

## Phase 4 — productization
Add:
- FastAPI ✓
- queue / worker ✓
- upload flow ✓
- download flow ✓
- evidence package ✓
- review UI ✓

## Phase 5 — enforcement-grade measurement
Add:
- plate-size metric conversion
- tyre-size conversion
- homography calibration
- stable curb distance threshold logic
