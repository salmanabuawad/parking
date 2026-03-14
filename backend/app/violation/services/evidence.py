"""Evidence frame saving for violation events."""
from __future__ import annotations

from pathlib import Path
import cv2


class EvidenceService:
    def __init__(self, output_dir: str | Path | None, save_frames: bool = True):
        self.output_dir = Path(output_dir) if output_dir else None
        self.frames_dir = self.output_dir / 'evidence_frames' if self.output_dir else None
        self.save_frames = save_frames and self.output_dir is not None
        if self.save_frames and self.frames_dir:
            self.frames_dir.mkdir(parents=True, exist_ok=True)

    def save_frame(self, frame_index: int, frame) -> str | None:
        if not self.save_frames or not self.frames_dir:
            return None
        path = self.frames_dir / f'frame_{frame_index:06d}.jpg'
        cv2.imwrite(str(path), frame)
        return str(path)
