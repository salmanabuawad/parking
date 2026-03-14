"""
Re-queue a video file to the upload job queue.

Usage:
  python requeue_video.py path/to/video.mp4
  python requeue_video.py path/to/video.mp4 --lat 34.05 --lng -118.25

The worker will pick it up and process (blur, create ticket).
"""
import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.database import SessionLocal
from app.repositories import UploadJobRepository


def main():
    parser = argparse.ArgumentParser(description="Re-queue a video to the upload job queue")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--lat", type=float, default=0.0, help="Latitude")
    parser.add_argument("--lng", type=float, default=0.0, help="Longitude")
    parser.add_argument("--plate", default="11111", help="License plate")
    parser.add_argument("--zone", default="red_white", help="Violation zone")
    args = parser.parse_args()

    p = Path(args.video)
    if not p.exists():
        print(f"Error: file not found: {p}")
        sys.exit(1)

    data = p.read_bytes()
    if not data:
        print("Error: video file is empty")
        sys.exit(1)

    ext = ".mp4" if p.suffix.lower() in (".mp4", ".mov", "") else p.suffix or ".mp4"
    fname = f"{uuid.uuid4().hex}{ext}"
    raw_path = settings.videos_dir / "raw" / fname
    raw_path.write_bytes(data)
    rel_path = f"raw/{fname}"

    db = SessionLocal()
    try:
        job_repo = UploadJobRepository(db)
        job = job_repo.create(
            raw_video_path=rel_path,
            status="queued",
            latitude=args.lat,
            longitude=args.lng,
            license_plate=args.plate,
            violation_zone=args.zone,
            description=f"Re-queued from {p.name}",
        )
        print(f"Job {job.id} queued. Raw video: {rel_path}")
        print("Run the worker to process: python run_upload_worker.py")
    finally:
        db.close()


if __name__ == "__main__":
    main()
