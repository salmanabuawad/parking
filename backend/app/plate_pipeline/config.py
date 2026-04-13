"""Configuration and thresholds for plate processing pipeline."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# --- Plate detection ---
HSV_LOWER_YELLOW = (15, 80, 100)   # tighter: avoids faded yellow/beige/road markings
HSV_UPPER_YELLOW = (38, 255, 255)  # matches Israeli plate yellow exactly
HSV_LOWER_LIGHT = (0, 0, 150)
HSV_UPPER_LIGHT = (180, 70, 255)
# Width/height; must include motorcycle (~17/16) and scooter (~17/12) per PLATE_FORMAT_PRESETS.
PLATE_MIN_RATIO = 1.0
PLATE_MAX_RATIO = 7.0
MIN_PLATE_AREA = 400
MAX_PLATE_AREA_RATIO = 0.08
PLATE_YOLO_MODEL_PATH = "models/license_plate_detector.pt"
PLATE_DETECT_TOP_K = 3
ROI_HORIZONTAL_EXPAND = 0.08
ROI_VERTICAL_EXPAND = 0.10
MULTI_PLATE_MAX_PER_FRAME = 2

# --- OCR ---
OCR_CROP_MARGIN_PX = 6
OCR_RESIZE_FACTOR = 3
OCR_DENOISE_ENABLED = True
OCR_SHARPEN_ENABLED = True
OCR_PSM = 7
OCR_PSM_FALLBACKS = (8, 6, 13)
OCR_EVERY_N_FRAMES = 2  # ANPR: Tesseract every N frames (1=every frame; 2–3 typical)

# --- Multi-track ANPR ---
ANPR_IOU_MATCH_THRESHOLD = 0.25
ANPR_OCR_EXTRA_MARGIN_PX = 8
ANPR_MIN_VOTES_STABLE = 2
ANPR_PREVIEW_MAX_TRACKS = 4
YOLO_EVERY_N_FRAMES = 3      # run YOLO vehicle detection every N frames
MAX_FRAMES = 60               # cap video at ~2 s @ 30 fps; enough for plate read
OCR_MIN_PLATE_WIDTH = 20
OCR_MIN_PLATE_HEIGHT = 6
OCR_MIN_SHARPNESS = 2.0
OCR_MIN_BRIGHTNESS = 10.0
OCR_MAX_BRIGHTNESS = 250.0

# --- Tracking ---
TRACK_MAX_MISSES = 8
TRACK_SMOOTHING_ALPHA = 0.65
TRACK_IOU_MIN = 0.10
TRACK_STABLE_AFTER = 2

# --- Blur / render ---
BLUR_KERNEL_SIZE = 3  # Gaussian kernel (odd); 3 = very light background blur
BLUR_EXPAND_RATIO = 0.18
TEMPORAL_BLUR_ENABLED = True
TEMPORAL_BLUR_MAX_MISSES = 6
PREVIEW_ENABLED = False  # corner inset duplicates the in-scene sharp plate (looks like "2 frames")
PREVIEW_MAX_W_RATIO = 0.28
PREVIEW_MAX_H_RATIO = 0.20
PREVIEW_MARGIN_PX = 10
PREVIEW_ZOOM = 4.0

# --- Enterprise engine: zoom ROI for HSV detection (plates appear larger in pixels) ---
ENTERPRISE_DETECTION_ZOOM = 1.75
ENTERPRISE_DETECTION_ROI_Y_START = 0.26  # zoom pass uses rows [y_start:height]; skips upper scene/sky

# --- Israeli plate formats ---
PLATE_FORMAT_PRESETS = [
    {"name": "private_long", "ratio": 52 / 12, "width_cm": 52.0, "height_cm": 12.0},
    {"name": "private_rect", "ratio": 32 / 16, "width_cm": 32.0, "height_cm": 16.0},
    {"name": "motorcycle", "ratio": 17 / 16, "width_cm": 17.0, "height_cm": 16.0},
    {"name": "scooter", "ratio": 17 / 12, "width_cm": 17.0, "height_cm": 12.0},
]

# --- OCR vote ---
PLATE_MIN_DIGITS = 7
PLATE_MAX_DIGITS = 8

# --- Vehicle detection ---
VEHICLE_MIN_CONFIDENCE = 0.4
VEHICLE_MODEL_PATH = "yolov8n.pt"
VEHICLE_IMGSZ = 416

# --- Curb (scaffold) ---
CURB_MIN_AREA = 800


@dataclass
class PipelineConfig:
    """Runtime config for the pipeline."""

    input_path: Path = Path(".")
    output_path: Path = Path(".")
    debug: bool = False
    max_frames: int | None = MAX_FRAMES
    registry_csv: Path | None = None
    detector_backend: Literal["hsv", "yolo", "enterprise"] = "yolo"
    disable_ocr: bool = False
    output_json: bool = True

    # Models
    plate_yolo_model_path: str = PLATE_YOLO_MODEL_PATH
    vehicle_model_path: str = VEHICLE_MODEL_PATH
    vehicle_imgsz: int = VEHICLE_IMGSZ
    yolo_every_n_frames: int = YOLO_EVERY_N_FRAMES

    # Thresholds / tuning
    plate_crop_margin_px: int = OCR_CROP_MARGIN_PX
    ocr_resize_factor: int = OCR_RESIZE_FACTOR
    ocr_denoise: bool = OCR_DENOISE_ENABLED
    ocr_sharpen: bool = OCR_SHARPEN_ENABLED
    ocr_every_n_frames: int = OCR_EVERY_N_FRAMES
    ocr_min_plate_width: int = OCR_MIN_PLATE_WIDTH
    ocr_min_plate_height: int = OCR_MIN_PLATE_HEIGHT
    ocr_min_sharpness: float = OCR_MIN_SHARPNESS
    ocr_min_brightness: float = OCR_MIN_BRIGHTNESS
    ocr_max_brightness: float = OCR_MAX_BRIGHTNESS
    track_max_misses: int = TRACK_MAX_MISSES
    track_smoothing_alpha: float = TRACK_SMOOTHING_ALPHA
    blur_kernel_size: int = BLUR_KERNEL_SIZE
    blur_expand_ratio: float = BLUR_EXPAND_RATIO
    temporal_blur_enabled: bool = TEMPORAL_BLUR_ENABLED
    temporal_blur_max_misses: int = TEMPORAL_BLUR_MAX_MISSES
    multi_plate_max_per_frame: int = MULTI_PLATE_MAX_PER_FRAME
    preview_enabled: bool = PREVIEW_ENABLED
    preview_max_w_ratio: float = PREVIEW_MAX_W_RATIO
    preview_max_h_ratio: float = PREVIEW_MAX_H_RATIO
    preview_margin_px: int = PREVIEW_MARGIN_PX
    preview_zoom: float = PREVIEW_ZOOM
    anpr_iou_match_threshold: float = ANPR_IOU_MATCH_THRESHOLD
    anpr_ocr_extra_margin_px: int = ANPR_OCR_EXTRA_MARGIN_PX
    anpr_min_votes_stable: int = ANPR_MIN_VOTES_STABLE
    anpr_preview_max_tracks: int = ANPR_PREVIEW_MAX_TRACKS
    enterprise_detection_zoom: float = ENTERPRISE_DETECTION_ZOOM
    enterprise_detection_roi_y_start: float = ENTERPRISE_DETECTION_ROI_Y_START
