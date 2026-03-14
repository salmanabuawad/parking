"""Delete all data from database (all tables)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from app.database import SessionLocal
from app.models import (
    Ticket,
    UploadJob,
    CameraVideo,
    Camera,
    Admin,
    AppConfig,
)


def main():
    db = SessionLocal()
    try:
        # FK order: ticket_screenshots, upload_jobs -> tickets; camera_videos -> cameras
        n_screenshots = 0
        try:
            r = db.execute(text("DELETE FROM ticket_screenshots"))
            n_screenshots = r.rowcount or 0
        except Exception:
            db.rollback()
            n_screenshots = 0

        n_jobs = db.query(UploadJob).delete(synchronize_session=False)
        n_tickets = db.query(Ticket).delete(synchronize_session=False)
        n_videos = db.query(CameraVideo).delete(synchronize_session=False)
        n_cameras = db.query(Camera).delete(synchronize_session=False)
        n_admins = db.query(Admin).delete(synchronize_session=False)
        n_config = db.query(AppConfig).delete(synchronize_session=False)

        db.commit()
        print(
            f"Deleted all: {n_tickets} tickets, {n_screenshots} ticket_screenshots, "
            f"{n_jobs} upload jobs, {n_videos} camera videos, {n_cameras} cameras, "
            f"{n_admins} admins, {n_config} app_config rows."
        )
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
