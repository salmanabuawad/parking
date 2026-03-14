"""Delete sample ticket(s) and recreate with current video from Sample Camera.
   Processes video (face blur) and stores both raw and processed in DB."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal
from app.models import Ticket, Camera, CameraVideo
from app.repositories import TicketRepository, CameraVideoRepository
from app.services.video_processor import process_video


def reseed():
    db = SessionLocal()
    try:
        # Delete ALL sample tickets (by license_plate, any camera_id)
        deleted = db.query(Ticket).filter(Ticket.license_plate == "ABC1234").delete(synchronize_session=False)
        db.commit()
        print(f"Deleted {deleted} sample ticket(s)")

        sample_cam = db.query(Camera).filter(Camera.name == "Sample Camera").first()
        if not sample_cam:
            print("Sample Camera not found. Run seed_sample_camera.py first.")
            return
        video_id = (sample_cam.connection_config or {}).get("video_id")
        if not video_id:
            print("Sample Camera has no video_id. Run seed_sample_camera.py first.")
            return

        # Get raw video from DB
        raw_vid = db.query(CameraVideo).filter(CameraVideo.id == video_id).first()
        if not raw_vid or not raw_vid.data:
            print("Video not found in DB. Run seed_sample_camera.py first.")
            return

        # Process video (face blur)
        print("Processing video (face blur)...")
        processed_bytes, ticket_jpeg = process_video(raw_vid.data)
        print("Done processing.")

        # Store processed video and ticket image in camera_videos
        video_repo = CameraVideoRepository(db)
        blurred_vid = video_repo.create(
            camera_id=None,
            name="sample_ticket_processed",
            data=processed_bytes,
            content_type="video/mp4",
        )
        img_record = video_repo.create(
            camera_id=None,
            name="sample_ticket_image",
            data=ticket_jpeg,
            content_type="image/jpeg",
        )

        # Create new sample ticket with processed_video_id so face-blurred video is served
        ticket_repo = TicketRepository(db)
        t = ticket_repo.create(
            license_plate="ABC1234",
            camera_id=str(sample_cam.id),
            location="Larkin & Union St, San Francisco (Sample)",
            violation_zone="red_white",
            description="Vehicle parked in red zone. Curb repainted while car was parked.",
            status="pending_review",
            video_id=video_id,
            processed_video_id=blurred_vid.id,
            ticket_image_id=img_record.id,
        )
        db.commit()
        print(f"Created new sample ticket (id={t.id}) with processed_video_id={blurred_vid.id}")
    finally:
        db.close()


if __name__ == "__main__":
    reseed()
