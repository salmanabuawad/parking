"""Re-render a ticket's per-car privacy video — used to recolor the subject-car box by status
(#10: green while pending → red once the report is approved). Reuses the vehicle-first pipeline;
the overlay plate label is forced to the ticket's recorded plate so the video stays consistent.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from app.config import settings


def rerender_ticket_video(db, ticket, *, box_color, plate_override: str | None = None) -> bool:
    """Re-render `ticket`'s video with the given subject-box BGR color. Returns True on success."""
    from app.models import AppConfig
    from app.plate_pipeline.config import PipelineConfig
    from app.plate_pipeline.pipeline import _run_pipeline_vehicle_multi

    if not ticket or not ticket.video_path:
        return False
    videos_dir = Path(settings.videos_dir).resolve()

    jid = None
    m = re.search(r"job_(\d+)", ticket.video_path)
    if m:
        jid = m.group(1)
    src = (videos_dir / "original" / f"job_{jid}.mp4") if jid else None
    if (not src or not src.exists()) and ticket.original_video_path:
        src = videos_dir / ticket.original_video_path
    if not src or not src.exists():
        return False

    cfg = db.query(AppConfig).first()
    blur = max(3, int(getattr(cfg, "blur_kernel_size", 3) or 3))
    if blur % 2 == 0:
        blur += 1
    clk = ticket.captured_at or ticket.created_at
    pc = PipelineConfig(
        input_path=src,
        output_path=Path(tempfile.mktemp(suffix=".mp4")),
        blur_kernel_size=blur,
        max_frames=150,
        output_json=False,
        detector_backend="enterprise",
        disable_ocr=False,
        ocr_every_n_frames=5,
        box_color_bgr=tuple(box_color),
        clock_start_epoch=(clk.timestamp() if clk else None),
        video_timestamp_overlay=bool(getattr(cfg, "video_timestamp_overlay", True)) if cfg else True,
    )
    result = _run_pipeline_vehicle_multi(pc, overlay_plate_override=plate_override or ticket.license_plate)
    tracks = result.get("tracks_render") or []
    if not tracks:
        return False
    pick = max(tracks, key=lambda x: x.get("vote_count", 0))
    vb = pick.get("video_bytes")
    if not vb:
        return False
    (videos_dir / ticket.video_path).write_bytes(vb)
    return True
