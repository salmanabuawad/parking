"""Seed admin (admin/admin123) and sample ticket for admin review."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal
from app.models import Admin, Ticket, Camera
from app.auth import hash_password

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


def seed():
    db = SessionLocal()
    try:
        # Admin
        admin = db.query(Admin).filter(Admin.username == ADMIN_USER).first()
        if not admin:
            db.add(Admin(
                username=ADMIN_USER,
                hashed_password=hash_password(ADMIN_PASS),
            ))
            db.commit()
            print(f"Created admin user: {ADMIN_USER}")
        else:
            admin.hashed_password = hash_password(ADMIN_PASS)
            db.commit()
            print(f"Updated admin password: {ADMIN_USER}")

        # Sample Camera (for ticket)
        sample_cam = db.query(Camera).filter(Camera.name == "Sample Camera").first()
        cam_id = str(sample_cam.id) if sample_cam else "1"
        video_id = (sample_cam.connection_config or {}).get("video_id") if sample_cam else 1

        # Sample ticket (pending_review)
        existing = db.query(Ticket).filter(
            Ticket.license_plate == "ABC1234",
            Ticket.status == "pending_review",
        ).first()
        if not existing:
            db.add(Ticket(
                license_plate="ABC1234",
                camera_id=cam_id,
                location="Larkin & Union St, San Francisco (Sample)",
                violation_zone="red_white",
                description="Vehicle parked in red zone. Curb repainted while car was parked.",
                status="pending_review",
                video_id=video_id,
            ))
            db.commit()
            print("Created sample ticket (pending_review)")
        else:
            print("Sample ticket already exists")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
