"""
Result output: processed MP4, JSON result, debug frames when enabled.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2


def write_result_json(
    path: Path,
    validated_plate: str | None,
    registry_match: dict | None,
    ocr_candidates: list[tuple[str, int]],
    selected_ocr: str | None,
    plate_format: dict | None,
    frames_processed: int,
    detector_backend: str,
    debug_path: str | None = None,
) -> None:
    out: dict[str, Any] = {
        "validated_plate": validated_plate,
        "registry_match": registry_match,
        "ocr_candidates": [{"plate": p, "count": c} for p, c in ocr_candidates],
        "selected_ocr_candidate": selected_ocr,
        "plate_format": plate_format,
        "frames_processed": frames_processed,
        "detector_backend": detector_backend,
    }
    if debug_path:
        out["debug_output_path"] = debug_path
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")


def write_video(frames: list, output_path: Path, fps: float = 25, fourcc: str = "mp4v") -> None:
    if not frames:
        return
    h, w = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*fourcc), fps, (w, h))
    for f in frames:
        writer.write(f)
    writer.release()
