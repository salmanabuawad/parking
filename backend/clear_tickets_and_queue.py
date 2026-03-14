"""Delete all tickets, ticket_screenshots, and upload_jobs (queue). Keeps cameras, admins, app_config."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from app.database import SessionLocal
from app.models import Ticket, UploadJob


def main():
    db = SessionLocal()
    try:
        # ticket_screenshots has FK to tickets (ondelete=CASCADE would auto-delete, but we delete explicitly for count)
        r = db.execute(text("DELETE FROM ticket_screenshots"))
        n_screenshots = r.rowcount or 0

        n_jobs = db.query(UploadJob).delete(synchronize_session=False)
        n_tickets = db.query(Ticket).delete(synchronize_session=False)

        db.commit()
        print(f"Deleted: {n_tickets} tickets, {n_screenshots} ticket_screenshots, {n_jobs} upload jobs (queue).")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
