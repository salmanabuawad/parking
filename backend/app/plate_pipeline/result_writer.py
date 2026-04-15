"""
Result output: processed MP4, JSON result, debug frames when enabled.
Video: OpenCV intermediate + ffmpeg libx264 (browser-safe); plain mp4v often won't play or looks empty.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _get_ffmpeg_exe() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _ensure_even_bgr(frame: np.ndarray) -> np.ndarray:
    """H.264 encoders expect even width/height."""
    h, w = frame.shape[:2]
    pad_h, pad_w = h % 2, w % 2
    if pad_h == 0 and pad_w == 0:
        return frame
    return cv2.copyMakeBorder(frame, 0, pad_h, 0, pad_w, cv2.BORDER_REPLICATE)


def write_result_json(
    path: Path,
    validated_plate: str | None,
    registry_match: dict | None,
    ocr_candidates: list[tuple[str, int]],
    selected_ocr: str | None,
    plate_format: dict | None,
    frames_processed: int,
    detector_backend: str,
    temporal_blur_enabled: bool | None = None,
    temporal_blur_max_misses: int | None = None,
    blur_expand_ratio: float | None = None,
    blur_kernel_size: int | None = None,
    debug_path: str | None = None,
    engine_version: str = "enterprise_v2",
    multi_plate_support: bool = True,
    anpr_tracks: list[dict] | None = None,
    detections_per_frame: list[list[dict]] | None = None,
) -> None:
    out: dict[str, Any] = {
        "validated_plate": validated_plate,
        "registry_match": registry_match,
        "ocr_candidates": [{"plate": p, "count": c} for p, c in ocr_candidates],
        "selected_ocr_candidate": selected_ocr,
        "plate_format": plate_format,
        "frames_processed": frames_processed,
        "detector_backend": detector_backend,
        "engine_version": engine_version,
        "multi_plate_support": multi_plate_support,
    }
    if temporal_blur_enabled is not None:
        out["temporal_blur_enabled"] = temporal_blur_enabled
    if temporal_blur_max_misses is not None:
        out["temporal_blur_max_misses"] = temporal_blur_max_misses
    if blur_expand_ratio is not None:
        out["blur_expand_ratio"] = blur_expand_ratio
    if blur_kernel_size is not None:
        out["blur_kernel_size"] = blur_kernel_size
    if debug_path:
        out["debug_output_path"] = debug_path
    if anpr_tracks is not None:
        out["anpr_tracks"] = anpr_tracks
    if detections_per_frame is not None:
        out["detections_per_frame"] = detections_per_frame
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")


def write_video(frames: list, output_path: Path, fps: float = 25, fourcc: str = "mp4v") -> None:
    """
    Write BGR frames to MP4. Re-encodes with ffmpeg (libx264 + yuv420p + faststart) when available
    so players and browsers show video reliably.
    """
    if not frames:
        print("[write_video] ERROR: no frames — output skipped", flush=True)
        return

    prepared: list[np.ndarray] = []
    for f in frames:
        if f is None or f.size == 0:
            continue
        x = f.astype(np.uint8) if f.dtype != np.uint8 else f
        if x.ndim == 2:
            x = cv2.cvtColor(x, cv2.COLOR_GRAY2BGR)
        prepared.append(_ensure_even_bgr(x))

    if not prepared:
        print("[write_video] ERROR: no valid frames after prepare", flush=True)
        return

    h, w = prepared[0].shape[:2]
    fps = float(fps) if fps and fps > 0.1 else 25.0

    tmp_cv = Path(tempfile.mktemp(suffix=".mp4"))
    writer = cv2.VideoWriter(str(tmp_cv), cv2.VideoWriter_fourcc(*fourcc), fps, (w, h))
    if not writer.isOpened():
        tmp_cv = Path(tempfile.mktemp(suffix=".avi"))
        writer = cv2.VideoWriter(str(tmp_cv), cv2.VideoWriter_fourcc(*"XVID"), fps, (w, h))

    if not writer.isOpened():
        print("[write_video] ERROR: cv2.VideoWriter failed (mp4v and XVID)", flush=True)
        tmp_cv.unlink(missing_ok=True)
        return

    for f in prepared:
        if f.shape[1] != w or f.shape[0] != h:
            f = cv2.resize(f, (w, h), interpolation=cv2.INTER_LINEAR)
        writer.write(f)
    writer.release()

    raw_size = tmp_cv.stat().st_size if tmp_cv.exists() else 0
    if raw_size < 256:
        print(f"[write_video] ERROR: OpenCV output too small ({raw_size} B)", flush=True)
        tmp_cv.unlink(missing_ok=True)
        return

    ffmpeg = _get_ffmpeg_exe()
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if ffmpeg:
        tmp_h264 = Path(tempfile.mktemp(suffix=".mp4"))
        try:
            result = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(tmp_cv),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "26",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    "-an",
                    str(tmp_h264),
                ],
                capture_output=True,
                timeout=600,
            )
            if result.returncode == 0 and tmp_h264.exists() and tmp_h264.stat().st_size > 256:
                if out_path.exists():
                    out_path.unlink()
                shutil.move(str(tmp_h264), str(out_path))
                tmp_cv.unlink(missing_ok=True)
                print(
                    f"[write_video] OK: {len(prepared)} frames → {out_path.name} "
                    f"({out_path.stat().st_size} B, h264)",
                    flush=True,
                )
                return
            err = (result.stderr or b"").decode(errors="replace")[-400:]
            print(f"[write_video] ffmpeg failed rc={result.returncode}: {err}", flush=True)
        finally:
            tmp_h264.unlink(missing_ok=True)

    # Fallback: copy OpenCV output (may not play in all browsers)
    shutil.copyfile(tmp_cv, out_path)
    tmp_cv.unlink(missing_ok=True)
    print(
        f"[write_video] OK (no ffmpeg): {len(prepared)} frames → {out_path.name} "
        f"({out_path.stat().st_size} B, raw OpenCV)",
        flush=True,
    )
