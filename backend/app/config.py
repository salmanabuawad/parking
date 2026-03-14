from typing import Optional
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    upload_dir: Path = Path("./uploads")
    videos_dir: Path = Path("./videos")  # Set VIDEOS_DIR env when API and worker run separately
    secret_key: str = "dev-secret-key-change-in-production"

    # Violation pipeline (red/white curb detection)
    use_violation_pipeline: bool = True  # Identify cars parked at red/white curb; blur moving cars
    use_fast_hsv_pipeline: bool = True  # Skip YOLO; use HSV for yellow plates + red/white curb only (faster)
    yolo_model_path: str = "yolov8n.pt"
    yolo_imgsz: int = 416  # Input size (416= faster, 640= default/better accuracy)
    vehicle_registry_file: str = "data/registry_sample.csv"
    vehicle_dimensions_file: str = "data/vehicle_dimensions_sample.csv"
    vehicle_registry_path: Path | None = None  # Resolved at runtime
    vehicle_dimensions_path: Path | None = None  # Resolved at runtime
    # Plate validation: only accept plates that exist in Ministry of Transport registry
    # https://data.gov.il/he/datasets/ministry_of_transport/private-and-commercial-vehicles/053cea08-09bc-40ec-8f7a-156f0677aff3
    validate_plate_in_registry: bool = True
    data_gov_il_resource_id: str = "053cea08-09bc-40ec-8f7a-156f0677aff3"  # MoT private/commercial vehicles; empty = local CSV only
    max_car_curb_distance_m: float = 0.50
    min_stationary_frames: int = 6  # ~0.25s at 25fps; used when no 10s-interval data
    parking_check_interval_sec: float = 10.0  # Sample at this interval; if car unchanged = parked
    yolo_inference_interval: int = 5  # Run YOLO every N frames; reuse detection for intermediates (1=every frame)
    debug_draw: bool = False
    save_evidence_frames: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
# Resolve paths relative to backend root
_backend_root = Path(__file__).resolve().parent.parent
if not settings.videos_dir.is_absolute():
    settings.videos_dir = (_backend_root / settings.videos_dir).resolve()
# Violation data files (registry, dimensions)
_settings_registry = getattr(settings, 'vehicle_registry_file', 'data/registry_sample.csv')
_settings_dims = getattr(settings, 'vehicle_dimensions_file', 'data/vehicle_dimensions_sample.csv')
settings.vehicle_registry_path = _backend_root / _settings_registry
settings.vehicle_dimensions_path = _backend_root / _settings_dims
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.videos_dir.mkdir(parents=True, exist_ok=True)
(settings.videos_dir / "raw").mkdir(parents=True, exist_ok=True)
(settings.videos_dir / "processed").mkdir(parents=True, exist_ok=True)
(settings.videos_dir / "frames").mkdir(parents=True, exist_ok=True)

