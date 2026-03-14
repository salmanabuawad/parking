"""
Reset jobs stuck in 'processing' back to queued.
Run when worker crashed mid-job and queue appears stuck.

Usage:
  python reset_stuck_jobs.py           # reset jobs stuck > 5 min (default)
  python reset_stuck_jobs.py --immediate   # reset ALL processing jobs immediately
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal
from app.repositories import UploadJobRepository


def main():
    parser = argparse.ArgumentParser(description="Reset stuck processing jobs to queued")
    parser.add_argument(
        "--immediate",
        action="store_true",
        help="Reset ALL processing jobs immediately (default: only those stuck > 5 min)",
    )
    args = parser.parse_args()
    stuck_minutes = 0 if args.immediate else 5

    db = SessionLocal()
    try:
        repo = UploadJobRepository(db)
        count = repo.reset_stuck_processing(stuck_minutes=stuck_minutes)
        print(f"Reset {count} job(s) from processing to queued.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
