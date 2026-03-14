"""Delete old data from database: tickets, upload_jobs, camera_videos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal
from app.models import Ticket, UploadJob, CameraVideo


def main():
    db = SessionLocal()
    try:
        n_jobs = db.query(UploadJob).delete(synchronize_session=False)
        n_tickets = db.query(Ticket).delete(synchronize_session=False)
        n_videos = db.query(CameraVideo).delete(synchronize_session=False)
        db.commit()
        print(f"Deleted: {n_tickets} tickets, {n_jobs} upload jobs, {n_videos} camera videos.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
