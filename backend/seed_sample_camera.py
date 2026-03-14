"""Seed a Sample Camera with the sample video stored in DB."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal
from app.models import Camera, CameraVideo

SAMPLE_DIR = Path(__file__).parent / "sample_camera"
SAMPLE_VIDEO = SAMPLE_DIR / "sample_parking_red_curb.mp4"


def seed():
    db = SessionLocal()
    try:
        # Read video into DB
        video_id = None
        if SAMPLE_VIDEO.exists():
            data = SAMPLE_VIDEO.read_bytes()
            existing_vid = db.query(CameraVideo).filter(
                CameraVideo.name == "sample_parking_red_curb"
            ).first()
            if existing_vid:
                existing_vid.data = data
                existing_vid.content_type = "video/mp4"
                db.commit()
                video_id = existing_vid.id
                print(f"Updated video in DB (id={video_id})")
            else:
                vid = CameraVideo(
                    camera_id=None,
                    name="sample_parking_red_curb",
                    data=data,
                    content_type="video/mp4",
                )
                db.add(vid)
                db.commit()
                db.refresh(vid)
                video_id = vid.id
                print(f"Inserted video into DB (id={video_id})")

        conn = {"video_id": video_id} if video_id else {}

        existing = db.query(Camera).filter(Camera.name == "Sample Camera").first()
        if existing:
            existing.connection_config = {**(existing.connection_config or {}), **conn}
            existing.location = "Sample: Car on Red/White Curb"
            db.commit()
            print("Updated Sample Camera")
        else:
            db.add(Camera(
                name="Sample Camera",
                location="Sample: Car on Red/White Curb",
                connection_type="other",
                connection_config=conn,
                param_source="manual",
                params={"moving": False, "night_light": False, "resolution": "720p", "fps": 24},
                manufacturer="Sample",
                model="Test",
                is_active=True,
            ))
            db.commit()
            print("Created Sample Camera")
    finally:
        db.close()


if __name__ == "__main__":
    if not SAMPLE_VIDEO.exists():
        from sample_camera.download_sample import download
        download()
    seed()
