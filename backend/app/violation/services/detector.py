"""Vehicle detection and tracking with YOLO."""
from __future__ import annotations

from ultralytics import YOLO

from app.config import settings
from app.violation.schemas import Detection


class VehicleDetector:
    COCO_CLASSES = {
        2: 'car',
        3: 'motorcycle',
        5: 'bus',
        7: 'truck',
    }

    def __init__(self, model_path: str = 'yolov8n.pt'):
        self.model = YOLO(model_path)
        self.imgsz = getattr(settings, 'yolo_imgsz', 416)

    def detect(self, frame) -> list[Detection]:
        """Single-frame detection (no tracking). Use for 10s-interval sampling."""
        results = self.model.predict(frame, verbose=False, imgsz=self.imgsz)
        return self._results_to_detections(results)

    def detect_and_track(self, frame) -> list[Detection]:
        results = self.model.track(frame, persist=True, verbose=False, imgsz=self.imgsz)
        return self._results_to_detections(results)

    def _results_to_detections(self, results) -> list[Detection]:
        detections: list[Detection] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                if cls_id not in self.COCO_CLASSES:
                    continue
                track_id = None
                if box.id is not None:
                    track_id = int(box.id[0].item())
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                detections.append(
                    Detection(
                        bbox=(x1, y1, x2, y2),
                        confidence=float(box.conf[0].item()),
                        class_name=self.COCO_CLASSES[cls_id],
                        track_id=track_id,
                    )
                )
        return detections
