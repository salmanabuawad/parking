"""Simulation sources — bundled sample clips that stand in for a live camera feed, so cameras can be
configured (enforcement sections drawn on the image) without real RTSP hardware. Clips live under
``videos/simulation/*.mp4``; a simulation camera stores its clip name in
``connection_config.simulation_source`` and grabs frames from it on demand.
"""
from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.services import camera_snapshot as cs


def sim_dir() -> Path:
    d = Path(settings.videos_dir) / "simulation"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_sources() -> list[dict]:
    """Available simulation clips (videos/simulation/*.mp4), sorted by name."""
    out = []
    for p in sorted(sim_dir().glob("*.mp4")):
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        out.append({"name": p.stem, "file": p.name, "size_bytes": size})
    return out


def resolve_path(name: str) -> Path | None:
    """Path to a named clip, guarding against path traversal (strips any directory/extension).
    Returns None if the clip does not exist."""
    if not name:
        return None
    safe = Path(Path(str(name)).name).stem  # drop any directory part and extension
    if not safe:
        return None
    p = sim_dir() / f"{safe}.mp4"
    return p if p.exists() else None


def frame_for_source(name: str, seek_frac: float | None = None) -> tuple[bytes, int, int] | None:
    """Grab one JPEG frame (+ its pixel resolution) from a named simulation clip. ``seek_frac`` None
    → a random position, so repeated grabs simulate a live feed."""
    p = resolve_path(name)
    if not p:
        return None
    return cs.frame_from_video_path(p, seek_frac=seek_frac)
