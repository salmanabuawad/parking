These are drop-in replacement files for the repo paths under:

backend/app/plate_pipeline/

Replaced files:
- config.py
- tracker.py
- plate_cropper.py
- ocr_reader.py
- ocr_vote.py
- vehicle_detector.py
- plate_detector.py
- pipeline.py

Main fixes:
- Real YOLO plate detector support when a dedicated plate model exists at `models/license_plate_detector.pt`
- Improved HSV fallback scoring using geometry + edge density + rectangularity
- Vehicle detection switched to persistent tracking path
- OCR throttled to every N frames and only on stable, high-quality plate crops
- OCR now tries multiple preprocessing variants
- Tracker now uses IOU gating and stability counting

Important:
- Put your trained plate model at `backend/models/license_plate_detector.pt` or adjust `PLATE_YOLO_MODEL_PATH`.
- If no dedicated plate model exists, the code still works with improved HSV fallback.
