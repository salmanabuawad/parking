# Masterpiece Package — Israeli Plate Detection, Validation, and Privacy Blur System

This package is the complete build brief for Cursor to implement a production-grade Israeli plate analysis app.

## Scope

The system must:

1. ingest video
2. detect Israeli plates
3. track the plate across frames
4. read OCR over time
5. validate OCR against the Gov.il private/commercial vehicle registry
6. classify plate format and infer physical dimensions
7. optionally detect red/white curb
8. estimate geometry and distance
9. blur everything except the validated target plate
10. export video, debug evidence, and structured JSON

## External source assumptions baked into this package

### Gov.il registry validation
The private/commercial vehicle registry is the truth source for validating extracted plate numbers. Use [data.gov.il](https://data.gov.il/he/datasets/ministry_of_transport/private-and-commercial-vehicles/053cea08-09bc-40ec-8f7a-156f0677aff3) (CKAN API) when local CSV does not contain the plate.

### Israeli plate dimensions
Use these standard reference sizes:
- private_long = 52 x 12 cm
- private_rect = 32 x 16 cm
- motorcycle = 17 x 16 cm
- scooter = 17 x 12 cm

## Recommended stack

Required now:
- Python
- OpenCV
- NumPy
- Pandas
- Tesseract OCR (pytesseract)

Optional next:
- Ultralytics YOLO (or use fast HSV pipeline to skip)
- FastAPI
- Uvicorn
- Shapely

## What to build first

1. stable HSV plate detector
2. temporal tracker
3. OCR voting
4. registry validation
5. plate format classification
6. selective blur output
7. debug evidence export

## Package contents

- docs/ARCHITECTURE.md
- docs/ALGORITHMS.md
- docs/DATA_INTEGRATION.md
- docs/API_SPEC.md
- docs/IMPLEMENTATION_ROADMAP.md
- docs/TEST_PLAN.md
- prompts/CURSOR_MASTER_PROMPT.txt
- prompts/CURSOR_TASK_BREAKDOWN.txt
- schemas/result_schema.json
- schemas/config_schema.json
- examples/sample_registry_lookup.py
- examples/sample_plate_format.py
- examples/sample_ocr_vote.py
