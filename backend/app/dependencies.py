"""Dependencies for repository injection."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import AdminRepository, CameraRepository, CameraVideoRepository, TicketRepository, UploadJobRepository
from app.repositories.inspector_repo import CameraSegmentRepository, InspectorRepository


def get_admin_repo(db: Session = Depends(get_db)) -> AdminRepository:
    return AdminRepository(db)


def get_camera_repo(db: Session = Depends(get_db)) -> CameraRepository:
    return CameraRepository(db)


def get_camera_video_repo(db: Session = Depends(get_db)) -> CameraVideoRepository:
    return CameraVideoRepository(db)


def get_ticket_repo(db: Session = Depends(get_db)) -> TicketRepository:
    return TicketRepository(db)


def get_upload_job_repo(db: Session = Depends(get_db)) -> UploadJobRepository:
    return UploadJobRepository(db)


def get_inspector_repo(db: Session = Depends(get_db)) -> InspectorRepository:
    return InspectorRepository(db)


def get_camera_segment_repo(db: Session = Depends(get_db)) -> CameraSegmentRepository:
    return CameraSegmentRepository(db)


