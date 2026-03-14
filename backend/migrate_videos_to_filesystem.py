"""
Migrate videos from database (camera_videos) to filesystem (videos/).

Run from backend/: python migrate_videos_to_filesystem.py

- Tickets with processed_video_id: save to videos/processed/ticket_{id}.mp4, set video_path
- Tickets with ticket_image_id: save to videos/frames/ticket_{id}.jpg, set ticket_image_path
- Tickets with video_id only (no processed): save raw to processed (or process on-the-fly - skip for now, just note)
- UploadJobs with raw_video_id: save to videos/raw/job_{id}_legacy.mp4, set raw_video_path
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.database import SessionLocal
from app.models import CameraVideo, Ticket, UploadJob
from sqlalchemy.orm import Session


def migrate_tickets(db: Session):
    """Move ticket videos and images from DB to filesystem."""
    tickets = db.query(Ticket).filter(
        (Ticket.processed_video_id.isnot(None)) | (Ticket.ticket_image_id.isnot(None))
    ).all()

    migrated = 0
    for t in tickets:
        updated = False

        # Processed video (blurred) - prefer this for playback
        vid_id = t.processed_video_id or t.video_id
        if vid_id and not t.video_path:
            vid = db.query(CameraVideo).filter(CameraVideo.id == vid_id).first()
            if vid and vid.data:
                fp = settings.videos_dir / "processed" / f"ticket_{t.id}.mp4"
                fp.write_bytes(bytes(vid.data))
                t.video_path = f"processed/ticket_{t.id}.mp4"
                updated = True

        # Ticket image (extracted frame)
        if t.ticket_image_id and not t.ticket_image_path:
            img = db.get(CameraVideo, t.ticket_image_id)
            if img and img.data:
                fp = settings.videos_dir / "frames" / f"ticket_{t.id}.jpg"
                fp.write_bytes(bytes(img.data))
                t.ticket_image_path = f"frames/ticket_{t.id}.jpg"
                updated = True

        if updated:
            migrated += 1
            print(f"  Ticket {t.id}: video_path={t.video_path}, ticket_image_path={t.ticket_image_path}")

    db.commit()
    return migrated


def migrate_upload_jobs(db: Session):
    """Move raw videos from upload jobs (DB) to filesystem."""
    jobs = db.query(UploadJob).filter(
        UploadJob.raw_video_id.isnot(None),
        UploadJob.raw_video_path.is_(None),
    ).all()

    migrated = 0
    for j in jobs:
        vid = db.get(CameraVideo, j.raw_video_id)
        if vid and vid.data:
            fp = settings.videos_dir / "raw" / f"job_{j.id}_legacy.mp4"
            fp.write_bytes(bytes(vid.data))
            j.raw_video_path = f"raw/job_{j.id}_legacy.mp4"
            migrated += 1
            print(f"  Job {j.id}: raw_video_path={j.raw_video_path}")

    db.commit()
    return migrated


def main():
    print("Migrating DB videos to filesystem...")
    db = SessionLocal()
    try:
        n_tickets = migrate_tickets(db)
        print(f"Migrated {n_tickets} tickets")
        n_jobs = migrate_upload_jobs(db)
        print(f"Migrated {n_jobs} upload jobs")
    finally:
        db.close()
    print("Done.")


if __name__ == "__main__":
    main()
