# Parking ALPR Masterpiece Architecture

## Goal
Build a production-grade parking-enforcement video pipeline that:
- identifies the correct target vehicle near red/white curb or on sidewalk
- reads the plate with high reliability
- validates the plate against the Israeli vehicle registry
- cross-checks vehicle make/model/color
- extracts video metadata such as GPS and capture time when available
- produces a court-friendly evidence package
- runs fast enough for practical use

## Final Decision Rule
A result is **confirmed** only when all of the following hold:
1. plate OCR is stable across frames
2. the plate exists in the Israeli registry dataset
3. registry make/model is consistent with the vehicle seen in the video
4. color is consistent when color data is available
5. the target vehicle score indicates curb/sidewalk violation confidence

Otherwise output **not_100_percent_sure** with the exact reason.

## End-to-End Pipeline
### 1. Video ingest and metadata extraction
Extract:
- GPS coordinates if present
- capture timestamp
- device make/model
- orientation and rotation
- codec, FPS, duration, resolution
- container metadata

### 2. Scene understanding
Detect:
- red/white curb segments
- sidewalk region
- road region
- curb line orientation

### 3. Vehicle detection and tracking
Use detector once, tracker continuously.
Recommended:
- YOLO vehicle detector
- ByteTrack or DeepSORT tracking

### 4. Target vehicle ranking
Do not choose the largest vehicle.
Rank by:
- overlap with sidewalk mask
- distance to curb
- stationary duration
- bottom-of-frame proximity
- plate visibility quality
- time persistence

### 5. Plate detection
Use a dedicated plate detector.
Fallback to color/geometry heuristics only when detector confidence is low.

### 6. Plate rectification
Before OCR:
- crop tightly with margin
- estimate quadrilateral or main rectangle
- perspective warp to canonical frontal view
- resize to fixed OCR dimensions
- reject low-quality crops

### 7. OCR stack
Tier 1:
- Tesseract on multiple preprocessed variants
- EasyOCR or CRNN candidate pass

Tier 2:
- keep top candidates per frame
- digit-level voting across frames

Tier 3:
- digit segmentation fallback for unstable positions

### 8. Vehicle attributes
Classify:
- make
- model
- color
- body type if possible

### 9. Registry validation
Query the Israeli Ministry of Transport private/commercial vehicles dataset.

### 10. Final confidence engine
Statuses:
- confirmed
- very_likely
- possible
- not_100_percent_sure

### 11. Evidence package
Generate:
- annotated MP4
- plate crops gallery
- target vehicle crops gallery
- JSON summary
- metadata JSON
- registry match JSON
- optional PDF report

## Additional Product Requirements

### Red/White curb physical prior
Use the Israeli curb paint prior as a geometric cue:
- each painted segment is typically about **100 cm** long
- curb paint band width is typically about **15 cm**

### Parking vs temporary traffic stop
The system should distinguish **parking** from **temporary stopping due to traffic**.

Recommended logic:
- a vehicle is only considered a likely violation candidate if it is near-zero motion for a sustained duration
- sustained duration must be measured while surrounding traffic context is also considered
- if neighboring traffic is also stationary or moving slowly in a queue, downgrade violation confidence
- if the target vehicle remains stationary while adjacent traffic continues moving, upgrade parking confidence

### Ticket screenshots from blurred UI video
The admin UI should allow screenshots to be captured from the **blurred evidence video** and saved into the ticket package.
Each screenshot must embed a visible timestamp derived from source video metadata or frame timecode.

### UI layout requirement
The video window in the UI should be **smaller** and should not dominate almost the full screen.

### UI/UX improvements
- Hebrew-first right-to-left layout
- confidence badges with exact reason text
- thumbnail gallery for best evidence frames
- timeline markers for key events
- reduced clutter by hiding debug overlays unless enabled

### Hebrew conversion
Convert the product to **Hebrew** as the main language with full RTL support.
