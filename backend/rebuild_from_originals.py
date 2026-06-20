"""
Wipe existing tickets + queue, then recreate fresh QUEUED jobs from the preserved
ORIGINAL videos (videos/original/job_<id>.mp4), reusing each original job's metadata
(lat/lng / zone / camera / captured_at / description). The running upload worker then
processes them with the CURRENT engine into brand-new tickets.

  - Old data removed: tickets, ticket_screenshots, anpr_track_results, upload_jobs.
  - Kept: cameras, parking zones, violation rules, app config, admins, and the
    original video files on disk.
  - Plate is reset to "11111" on each new job so the engine re-detects from scratch.

Run from the backend dir with the venv + .env pointing at the target DB:
  python rebuild_from_originals.py --dry-run   # show what would be deleted/recreated
  python rebuild_from_originals.py             # do it
"""
import argparse
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from app.config import settings
from app.database import SessionLocal
from app.models import Ticket, UploadJob
from app.repositories import UploadJobRepository


def main():
    ap = argparse.ArgumentParser(description="Wipe tickets/queue and rebuild from original videos")
    ap.add_argument("--dry-run", action="store_true", help="show plan; make no changes")
    args = ap.parse_args()

    videos_dir = Path(settings.videos_dir).resolve()
    orig_dir = videos_dir / "original"
    raw_dir = videos_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    print(f"Videos dir: {videos_dir}", flush=True)

    db = SessionLocal()
    try:
        # 1) Snapshot job metadata + locate each original video (BEFORE deleting anything)
        jobs = db.query(UploadJob).order_by(UploadJob.id).all()
        snaps = []
        missing = []
        for j in jobs:
            ov = orig_dir / f"job_{j.id}.mp4"
            # processed jobs keep their source at original/job_<id>.mp4; still-queued jobs
            # have it at their raw_video_path (raw/<uuid>.mp4)
            if not (ov.exists() and ov.stat().st_size > 1024) and j.raw_video_path:
                alt = videos_dir / j.raw_video_path
                if alt.exists() and alt.stat().st_size > 1024:
                    ov = alt
            if ov.exists() and ov.stat().st_size > 1024:
                snaps.append({
                    "src": ov,
                    "latitude": j.latitude,
                    "longitude": j.longitude,
                    "violation_zone": j.violation_zone or "red_white",
                    "camera_id": j.camera_id,
                    "captured_at": j.captured_at,
                    "description": j.description,
                    "submitted_by": j.submitted_by,
                })
            else:
                missing.append(j.id)

        n_tickets = db.query(Ticket).count()
        n_jobs = len(jobs)
        print(f"Tickets: {n_tickets}   Jobs: {n_jobs}   Originals found: {len(snaps)}   Missing originals: {len(missing)}", flush=True)
        if missing:
            shown = ", ".join(str(x) for x in missing[:20])
            print(f"  jobs with NO original video (cannot recreate): {shown}{' ...' if len(missing) > 20 else ''}", flush=True)

        if args.dry_run:
            for s in snaps[:6]:
                print(f"  would recreate from {s['src'].name}  zone={s['violation_zone']}  cam={s['camera_id']}  gps=({s['latitude']},{s['longitude']})  at={s['captured_at']}", flush=True)
            print("(dry-run: no changes made)", flush=True)
            return

        if not snaps:
            print("No original videos found — aborting (nothing to rebuild from).", flush=True)
            return

        # 2) Remove old data (children first; anpr_track_results also cascades on ticket delete)
        n_ss = db.execute(text("DELETE FROM ticket_screenshots")).rowcount or 0
        try:
            n_anpr = db.execute(text("DELETE FROM anpr_track_results")).rowcount or 0
        except Exception:
            n_anpr = 0
        n_jobs_del = db.query(UploadJob).delete(synchronize_session=False)
        n_tickets_del = db.query(Ticket).delete(synchronize_session=False)
        db.commit()
        print(f"Deleted: {n_tickets_del} tickets, {n_ss} screenshots, {n_anpr} anpr rows, {n_jobs_del} jobs.", flush=True)

        # 3) Recreate fresh queued jobs from the originals (copy original -> raw/, preserve metadata)
        job_repo = UploadJobRepository(db)
        created = 0
        for s in snaps:
            fname = f"{uuid.uuid4().hex}.mp4"
            shutil.copyfile(s["src"], raw_dir / fname)
            job_repo.create(
                raw_video_path=f"raw/{fname}",
                status="queued",
                latitude=s["latitude"] if s["latitude"] is not None else 0.0,
                longitude=s["longitude"] if s["longitude"] is not None else 0.0,
                license_plate="11111",  # reset so the engine re-detects from scratch
                violation_zone=s["violation_zone"],
                camera_id=s["camera_id"],
                captured_at=s["captured_at"],
                description=s["description"],
                submitted_by=s["submitted_by"],
            )
            created += 1

        print(f"Recreated {created} queued jobs from originals. The upload worker will now process them.", flush=True)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
