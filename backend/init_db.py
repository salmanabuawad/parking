"""Initialize database tables."""
from app.database import engine, Base
from app.models import Admin, Camera, CameraVideo, Ticket, UploadJob

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")
