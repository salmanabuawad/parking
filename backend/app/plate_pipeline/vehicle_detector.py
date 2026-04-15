"""Vehicle detection - first step in vehicle-first pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

COCO_VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


@dataclass
class VehicleDetection:
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    class_name: str
    track_id: int | None = None


class VehicleDetector:
    """Detect vehicles in frame with YOLO and persistent tracking."""

    def __init__(self, model_path: str = "yolov8n.pt", imgsz: int = 416):
        self.model_path = model_path
        self.imgsz = imgsz
        self._model = None
        self._model_failed = False

    def _get_model(self):
        if self._model_failed:
            return None
        if self._model is None:
            try:
                from ultralytics import YOLO
                self._model = YOLO(self.model_path)
            except Exception:
                self._model_failed = True
                return None
        return self._model

    def detect(self, frame: np.ndarray) -> List[VehicleDetection]:
        model = self._get_model()
        if model is None:
            return []
        results = model.predict(frame, verbose=False, imgsz=self.imgsz)
        return self._to_detections(results)

    def detect_and_track(self, frame: np.ndarray) -> List[VehicleDetection]:
        model = self._get_model()
        if model is None:
            return []
        results = model.track(frame, persist=True, verbose=False, imgsz=self.imgsz)
        return self._to_detections(results)

    def _to_detections(self, results) -> List[VehicleDetection]:
        out: List[VehicleDetection] = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0].item())
                if cls_id not in COCO_VEHICLE_CLASSES:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0].item())
                track_id = None
                if box.id is not None:
                    track_id = int(box.id[0].item())
                out.append(
                    VehicleDetection(
                        bbox=(x1, y1, x2, y2),
                        confidence=conf,
                        class_name=COCO_VEHICLE_CLASSES[cls_id],
                        track_id=track_id,
                    )
                )
        out.sort(key=lambda d: (d.confidence, _box_area(d.bbox)), reverse=True)
        return out


def _box_area(box: Tuple[int, int, int, int]) -> int:
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)
