"""
Israeli plate-processing pipeline.

Modular architecture for:
- Vehicle-first detection
- Plate detection (YOLO primary, HSV fallback)
- Tight plate crops only for OCR
- OCR voting across frames
- Gov.il registry validation

Use via CLI: python -m app.plate_pipeline.app --input video.mp4 --output out.mp4
"""
