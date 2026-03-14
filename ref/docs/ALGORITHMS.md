# Algorithms

## 1. HSV yellow plate detection

### Goal
Detect Israeli yellow plates without heavy AI in the first version.

### Steps
1. convert BGR frame to HSV
2. threshold yellow using (widened for dimmer/less saturated plates):
   - lower = [12, 50, 50]
   - upper = [45, 255, 255]
3. apply morphology open + close
4. find contours
5. compute bounding box for each contour
6. filter by: `min_area >= 300`, `1.8 < aspect_ratio < 6.5`, `plate_area <= 0.12 × frame_area`
7. choose highest-scoring candidate

### Fast HSV pipeline
When `use_fast_hsv_pipeline=True`, skip YOLO entirely: detect plates via HSV only, blur all except plate. Faster and suitable when filming curb-side with yellow plates in view.

### Scoring suggestion
score = area × aspect_ratio_fit × compactness_fit

## 2. Plate tracking

### Goal
Reduce frame-to-frame flicker.

### Steps
- if detection exists:
  - smooth current box with previous box
  - reset miss counter
- else:
  - reuse previous box for up to N frames
- if misses exceed threshold:
  - clear tracked box

### Suggested parameters
- MAX_TRACK_MISSES = 8
- SMOOTHING_ALPHA = 0.65

## 3. OCR reading

### Goal
Extract candidate numeric text from the cropped plate box.

### Israeli plates: black digits on yellow background
- **Preprocessing**: adaptive threshold to separate dark digits from bright yellow, then invert (black-on-white preferred by Tesseract)
- Use Tesseract with `--psm 7`, `tessedit_char_whitelist=0123456789`
- Enlarge crop if min dimension < 80px for better OCR

### Rules
- normalize to digits only
- accept only 7-digit or 8-digit strings (Israeli civilian plates)
- reject low confidence
- return best candidate per frame

## 4. OCR voting

### Goal
Choose the most stable candidate across time.

### Rules
- count candidate appearances
- optionally weight by OCR confidence
- validate candidates against registry
- choose the most frequent valid candidate

### Acceptance priority
1. most frequent candidate that exists in registry
2. if none exist, return no valid plate

## 5. Registry validation

### Goal
Filter OCR by reality.

### Gov data fields to use
- MISPAR_RECHEV
- TOZERET_NM or equivalent manufacturer field
- KINUY_MISHARI or equivalent model field
- SHNAT_YITZUR or equivalent year field

### Rules
- normalize plate to digits only
- exact match only
- if multiple rows are returned, choose first stable record
- return manufacturer/model/year for evidence

## 6. Plate format classification

### Goal
Estimate physical plate dimensions from box ratio.

### Standard plate presets
- private_long = 52 x 12 cm
- private_rect = 32 x 16 cm
- motorcycle = 17 x 16 cm
- scooter = 17 x 12 cm

### Rule
Compute bbox ratio and choose nearest known preset.

## 7. Curb detection

### Goal
Find red/white curb candidates.

### Steps
- detect red mask with two HSV ranges (hue 0–12 and 165–180; sat ≥80, val ≥60)
- detect white mask (sat ≤70, val ≥170)
- combine masks
- morphology open (5×5) + close (11×11)
- contour detection
- keep elongated candidates (aspect ≥2.5, area ≥800)
- require both red and white pixels in candidate ROI (min 50 each)
- score by red/white balance, aspect, vertical position

## 8. Distance estimation

### Current version
Rectangle-based pixel distance between plate and curb candidate.

### Future version
- fit curb line or polyline
- project plate or car contact point to ground plane
- convert pixels to centimeters using:
  - plate dimensions
  - tyre size
  - homography
- compute perpendicular metric distance

## 9. Privacy blur

### Rule
- blur full frame first
- restore only validated target plate box
- later optionally restore whole target car box or segmentation mask

## 10. Evidence generation

Save:
- final processed frame/video
- detection overlay
- mask image
- OCR candidate list
- validated registry match
- selected plate format
- optional curb and distance metadata
