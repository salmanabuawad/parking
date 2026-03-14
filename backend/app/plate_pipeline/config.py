"""Configuration and thresholds for plate processing pipeline."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# --- Plate detection ---
HSV_LOWER_YELLOW = (10, 40, 40)
HSV_UPPER_YELLOW = (50, 255, 255)
HSV_LOWER_LIGHT = (15, 20, 140)
HSV_UPPER_LIGHT = (50, 120, 255)
PLATE_MIN_RATIO = 1.5
PLATE_MAX_RATIO = 7.0
MIN_PLATE_AREA = 180
MAX_PLATE_AREA_RATIO = 0.12
PLATE_YOLO_MODEL_PATH = "models/license_plate_detector.pt"
PLATE_DETECT_TOP_K = 8
ROI_HORIZONTAL_EXPAND = 0.08
ROI_VERTICAL_EXPAND = 0.10

# --- OCR ---
OCR_CROP_MARGIN_PX = 4
OCR_RESIZE_FACTOR = 2
OCR_DENOISE_ENABLED = True
OCR_SHARPEN_ENABLED = True
OCR_PSM = 7
OCR_PSM_FALLBACKS = (6, 8)
OCR_EVERY_N_FRAMES = 3
OCR_MIN_PLATE_WIDTH = 60
OCR_MIN_PLATE_HEIGHT = 16
OCR_MIN_SHARPNESS = 45.0
OCR_MIN_BRIGHTNESS = 45.0
OCR_MAX_BRIGHTNESS = 235.0

# --- Tracking ---
TRACK_MAX_MISSES = 8
TRACK_SMOOTHING_ALPHA = 0.65
TRACK_IOU_MIN = 0.10
TRACK_STABLE_AFTER = 2

# --- Blur ---
BLUR_KERNEL_SIZE = 51

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
    max_frames: int | None = None
    registry_csv: Path | None = None
    detector_backend: Literal["hsv", "yolo"] = "yolo"
    disable_ocr: bool = False
    output_json: bool = True

    # Models
    plate_yolo_model_path: str = PLATE_YOLO_MODEL_PATH
    vehicle_model_path: str = VEHICLE_MODEL_PATH
    vehicle_imgsz: int = VEHICLE_IMGSZ

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
