"""
Background worker: processes upload_jobs queue.
Run with: python run_upload_worker.py (or python -m run_upload_worker)

Flow:
  1. Poll for queued jobs (with raw_video_path)
  2. Set status=processing, run video processor (blur, extract frame)
  3. Save processed video and frame to videos/ folder
  4. Create ticket with file paths, update job
  5. On error: status=failed, error_message
"""
import logging
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Enable INFO logging so plate OCR debug output (method/PSM per frame) is visible
logging.basicConfig(level=logging.INFO, format="%(message)s")

from app.config import settings
from app.database import SessionLocal
from app.models import AppConfig
from app.repositories import TicketRepository, UploadJobRepository
from app.services.video_processor import (
    process_video,
    process_video_fast_hsv,
    process_video_with_violation_pipeline,
    extract_license_plate,
)

# Use same videos_dir as API (from config) so uploads from UI resolve correctly
_VIDEOS_DIR = settings.videos_dir


def _fmt_queue(status: dict) -> str:
    """Format queue status for logging: q=queued p=processing c=completed f=failed, plus next job IDs."""
    q, p, c, f = status.get("queued", 0), status.get("processing", 0), status.get("completed", 0), status.get("failed", 0)
    extra = ""
    ids = status.get("next_ids") or []
    if ids:
        extra = f" | next: {ids}"
    return f"q:{q} p:{p} c:{c} f:{f}{extra}"


def process_one_job() -> bool:
    """Process a single queued job. Returns True if a job was processed."""
    db = SessionLocal()
    job = None
    job_repo = None
    try:
        job_repo = UploadJobRepository(db)
        ticket_repo = TicketRepository(db)

        job = job_repo.get_next_queued()
        if not job:
            s = job_repo.get_queue_status()
            print(f"[{datetime.now().isoformat()}] Queue: {_fmt_queue(s)}", flush=True)
            # No queued jobs: reset any stuck in "processing" (worker crashed)
            reset = job_repo.reset_stuck_processing()
            if reset > 0:
                print(f"[{datetime.now().isoformat()}] Reset {reset} stuck job(s) to queued", flush=True)
            return False
        if not job.raw_video_path:
            job_repo.update(job.id, status="failed", error_message="No raw video path (legacy job?)")
            return True

        from datetime import timezone as tz
        job_repo.update(job.id, status="processing", processing_started_at=datetime.now(tz.utc))
        s = job_repo.get_queue_status()
        print(f"[{datetime.now().isoformat()}] Job {job.id} picked up | {_fmt_queue(s)}", flush=True)

        # Use same videos_dir as API (settings.videos_dir) so paths match
        videos_dir = Path(settings.videos_dir)
        path_str = (job.raw_video_path or "").strip().replace("\\", "/")
        raw_path = (videos_dir / path_str).resolve()
        if not raw_path.exists():
            job_repo.update(job.id, status="failed", error_message=f"Raw video not found at {raw_path}")
            return True

        video_bytes = raw_path.read_bytes()
        if not video_bytes:
            job_repo.update(job.id, status="failed", error_message="Raw video file is empty")
            return True

        cfg = db.query(AppConfig).first()
        use_violation = cfg.use_violation_pipeline if cfg is not None else getattr(settings, 'use_violation_pipeline', True)
        use_fast = getattr(settings, 'use_fast_hsv_pipeline', True)
        plate_reason = None
        if use_fast:
            # Fast path: HSV yellow plates only, no YOLO. Black-on-yellow OCR.
            blurred_bytes, ticket_jpeg = process_video_fast_hsv(video_bytes)
            license_plate = job.license_plate or "11111"
            if license_plate == "11111":
                license_plate, plate_reason = extract_license_plate(
                    frame_jpeg=ticket_jpeg, video_bytes=video_bytes, use_fast_hsv=True
                )
                if license_plate != "11111":
                    print(f"[Job {job.id}] Fast HSV OCR detected plate: {license_plate}", flush=True)
                else:
                    print(f"[Job {job.id}] Plate not extracted: {plate_reason or 'Unknown'}", flush=True)
        elif use_violation:
            try:
                blurred_bytes, ticket_jpeg, license_plate = process_video_with_violation_pipeline(
                    video_bytes,
                    output_dir=str(videos_dir / "evidence"),
                    extract_frame_at=0.5,
                )
                if license_plate and license_plate != "11111":
                    print(f"[Job {job.id}] Violation pipeline detected plate: {license_plate}", flush=True)
                elif license_plate == "11111":
                    detected_plate, plate_reason = extract_license_plate(frame_jpeg=ticket_jpeg)
                    if detected_plate != "11111":
                        license_plate = detected_plate
                        print(f"[Job {job.id}] OCR detected plate: {license_plate}", flush=True)
                    else:
                        plate_reason = plate_reason or "Violation pipeline did not detect plate in any frame."
                        print(f"[Job {job.id}] Plate not extracted: {plate_reason}", flush=True)
            except Exception as e:
                print(f"[Job {job.id}] Violation pipeline failed, falling back: {e}", flush=True)
                blurred_bytes, ticket_jpeg = process_video(video_bytes)
                license_plate = job.license_plate or "11111"
                plate_reason = None
                if license_plate == "11111":
                    from app.violation.services.registry import VehicleRegistryService
                    _registry = VehicleRegistryService()
                    detected_plate, plate_reason = extract_license_plate(
                        video_bytes=video_bytes, registry_lookup=_registry
                    )
                    if detected_plate != "11111":
                        license_plate = detected_plate
                        print(f"[Job {job.id}] OCR (fallback) detected plate: {license_plate}", flush=True)
                    else:
                        print(f"[Job {job.id}] Plate not extracted: {plate_reason or 'Unknown'}", flush=True)
        else:
            # Ref algorithm: HSV plate detection + blur pipeline. OCR plate from processed frame.
            blurred_bytes, ticket_jpeg = process_video(video_bytes)
            license_plate = job.license_plate or "11111"
            plate_reason = None
            if license_plate == "11111":
                license_plate, plate_reason = extract_license_plate(frame_jpeg=ticket_jpeg)
                if license_plate != "11111":
                    print(f"[Job {job.id}] OCR detected plate: {license_plate}", flush=True)
                else:
                    print(f"[Job {job.id}] Plate not extracted: {plate_reason or 'Unknown'}", flush=True)

        # Validate plate against Ministry of Transport registry (data.gov.il) when enabled
        validate_registry = getattr(settings, 'validate_plate_in_registry', False)
        if validate_registry and license_plate and license_plate != "11111":
            from app.violation.services.registry import VehicleRegistryService
            registry = VehicleRegistryService()
            if not registry.plate_exists(license_plate):
                print(f"[Job {job.id}] Plate {license_plate} not in MoT registry, rejecting", flush=True)
                plate_reason = "Plate not found in Ministry of Transport registry (data.gov.il)"
                license_plate = "11111"

        # Save to filesystem: videos/processed/job_{id}.mp4, videos/frames/job_{id}.jpg
        proc_path = videos_dir / "processed" / f"job_{job.id}.mp4"
        frame_path = videos_dir / "frames" / f"job_{job.id}.jpg"
        proc_path.write_bytes(blurred_bytes)
        frame_path.write_bytes(ticket_jpeg)

        rel_video = f"processed/job_{job.id}.mp4"
        rel_frame = f"frames/job_{job.id}.jpg"

        location_str = f"{job.latitude or 0:.6f}, {job.longitude or 0:.6f}"
        ticket_kw = dict(
            license_plate=license_plate,
            camera_id="mobile",
            location=location_str,
            violation_zone=job.violation_zone or "red_white",
            description=job.description or f"Mobile upload at {location_str}",
            status="pending_review",
            video_path=rel_video,
            ticket_image_path=rel_frame,
            latitude=job.latitude,
            longitude=job.longitude,
            captured_at=job.captured_at,
        )
        if plate_reason:
            ticket_kw["plate_detection_reason"] = plate_reason
        # Ref: plate format classification from ticket frame
        try:
            import cv2
            import numpy as np
            from app.services.video_processor import detect_plate_box, classify_plate_format
            frame = cv2.imdecode(np.frombuffer(ticket_jpeg, np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                box = detect_plate_box(frame)
                if box:
                    _, _, w, h = box
                    fmt = classify_plate_format(w, h)
                    if fmt:
                        ticket_kw["plate_format"] = fmt.get("name")
        except Exception:
            pass

        ticket = ticket_repo.create(**ticket_kw)

        job_repo.update(
            job.id,
            status="completed",
            ticket_id=ticket.id,
            completed_at=datetime.now(timezone.utc),
            error_message=None,
        )
        s = job_repo.get_queue_status()
        print(f"[{datetime.now().isoformat()}] Job {job.id} completed -> ticket {ticket.id} | {_fmt_queue(s)}", flush=True)
        return True
    except Exception as e:
        if job and job_repo:
            job_repo.update(job.id, status="failed", error_message=str(e))
        traceback.print_exc()
        if job_repo:
            s = job_repo.get_queue_status()
            print(f"[{datetime.now().isoformat()}] Job {job.id if job else '?'} failed: {e} | {_fmt_queue(s)}", flush=True)
        else:
            print(f"[{datetime.now().isoformat()}] Job {job.id if job else '?'} failed: {e}", flush=True)
        return True  # job was handled (failed)
    finally:
        db.close()


def main():
    poll_interval = 2.0
    videos_path = Path(settings.videos_dir).resolve()
    print(f"Upload worker started. Videos dir: {videos_path} Polling every {poll_interval}s.", flush=True)
    # Check Tesseract (plate OCR) at startup
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        print("Tesseract OCR: OK", flush=True)
    except Exception as e:
        print(f"WARNING: Tesseract not available for plate OCR: {e}", flush=True)
        print("Install: winget install UB-Mannheim.TesseractOCR", flush=True)
    while True:
        try:
            process_one_job()
        except KeyboardInterrupt:
            print("Worker stopped.")
            break
        except Exception as e:
            traceback.print_exc()
            print(f"Worker error: {e}")
        time.sleep(poll_interval)


if __name__ == "__main__":
    main()

