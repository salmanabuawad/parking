# Final Architecture

## High-level system

```text
video input
   ↓
video_io
   ↓
plate_detector
   ↓
tracker
   ↓
ocr_reader
   ↓
ocr_vote
   ↓
registry_lookup
   ↓
plate_format
   ↓
curb_detector
   ↓
distance_estimator
   ↓
privacy_blur
   ↓
output video + debug evidence + JSON result
```

## Module list

### app.py
CLI entrypoint and orchestration.

### config.py
Runtime settings, thresholds, file paths, backend selection.

### video_io.py
Open input, read metadata, write output video.

### plate_detector.py
Detector interface with two backends:
- HSVPlateDetector
- YOLOPlateDetector

**Fast HSV pipeline** (`use_fast_hsv_pipeline`): Skip YOLO; use HSV yellow detection only. Faster for curb-side filming.

### tracker.py
Single-target temporal smoothing and miss recovery.

### ocr_reader.py
Reads text from cropped plate region. Use Tesseract with black-on-yellow preprocessing (adaptive threshold + invert) for Israeli plates.

### ocr_vote.py
Aggregates OCR across frames and selects best stable candidate.

### registry_lookup.py
Loads Gov.il registry CSV and validates OCR candidate. Optional data.gov.il API fallback when plate not in local CSV.

### plate_format.py
Maps detected bbox ratio to Israeli standard plate format and dimensions.

### curb_detector.py
Detects red/white curb candidates.

### distance.py
Distance scaffold now, metric estimator later.

### blur_pipeline.py
Blur everything, restore only validated target.

### debug.py
Save overlays, masks, snapshots, and metadata.

## Design rules

1. OCR is never trusted without validation.
2. Registry match is the acceptance gate for private/commercial vehicles.
3. Plate dimensions are a geometry aid, not a legal identifier.
4. Detection logic stays independent from app entrypoint.
5. Debug output stays independent from core logic.
6. Every major layer must expose clean interfaces for replacement.
