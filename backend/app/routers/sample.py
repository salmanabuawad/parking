"""Sample video API - served under /api/sample. Always serves blurred for privacy."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.services.video_processor import process_video

SAMPLE_VIDEO = Path(__file__).resolve().parents[2] / "sample_camera" / "sample_parking_red_curb.mp4"

router = APIRouter(prefix="/sample", tags=["sample"])

# Cache blurred sample in memory (processed once on first request)
_cached_blurred: bytes | None = None


@router.get("/video")
def sample_video(refresh: bool = False):
    """Serve the sample parking video, blurred for privacy. Use ?refresh=1 to force reprocess."""
    global _cached_blurred
    if not SAMPLE_VIDEO.exists():
        raise HTTPException(404, "Sample video not found. Run: python sample_camera/download_sample.py")
    if refresh:
        _cached_blurred = None
    if _cached_blurred is None:
        raw = SAMPLE_VIDEO.read_bytes()
        _cached_blurred, _ = process_video(raw)
    return Response(
        content=_cached_blurred,
        media_type="video/mp4",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )
