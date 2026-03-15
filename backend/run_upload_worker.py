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
    extract_video_params,
    extract_frames,
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
        videos_dir = Path(settings.videos_dir).resolve()
        raw_dir = videos_dir / "raw"
        path_str = (job.raw_video_path or "").strip().replace("\\", "/")
        raw_path = (videos_dir / path_str).resolve()
        # Fallback 1: raw dir + filename only
        if not raw_path.exists():
            base_name = Path(path_str).name
            fallback = raw_dir / base_name
            if fallback.resolve().exists():
                raw_path = fallback.resolve()
        # Fallback 2: path may be truncated in DB; find file whose name starts with same prefix
        if not raw_path.exists() and raw_dir.exists():
            base_name = Path(path_str).name
            prefix = base_name.rsplit(".", 1)[0] if "." in base_name else base_name
            if len(prefix) >= 8:
                for p in raw_dir.iterdir():
                    if p.is_file() and p.name.startswith(prefix):
                        raw_path = p.resolve()
                        print(f"[Job {job.id}] Resolved raw video by prefix: {p.name}", flush=True)
                        break
        if not raw_path.exists():
            err = (
                f"Raw video not found at {raw_path}. "
                f"Videos dir: {videos_dir}. "
                f"Ensure API and worker use the same VIDEOS_DIR (or run from backend dir)."
            )
            job_repo.update(job.id, status="failed", error_message=err)
            return True

        video_bytes = raw_path.read_bytes()
        if not video_bytes:
            job_repo.update(job.id, status="failed", error_message="Raw video file is empty")
            return True

        cfg = db.query(AppConfig).first()
        use_violation = cfg.use_violation_pipeline if cfg is not None else getattr(settings, 'use_violation_pipeline', True)
        use_fast = getattr(settings, 'use_fast_hsv_pipeline', True)
        # Always apply blur for privacy (default 15 when settings have 0 or None)
        blur_size = 15
        if cfg and getattr(cfg, 'blur_kernel_size', None) is not None and cfg.blur_kernel_size > 0:
            blur_size = max(3, cfg.blur_kernel_size)
        if blur_size % 2 == 0:
            blur_size += 1
        blur_kw = {'blur_strength': blur_size}
        plate_reason = None
        if use_fast:
            # Fast path: HSV yellow plates only, no YOLO. Black-on-yellow OCR.
            blurred_bytes, ticket_jpeg = process_video_fast_hsv(video_bytes, **blur_kw)
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
                blur_size = (cfg.blur_kernel_size if cfg and getattr(cfg, "blur_kernel_size", None) is not None else None) or 15
                if blur_size <= 0:
                    blur_size = 15
                blurred_bytes, ticket_jpeg, license_plate = process_video_with_violation_pipeline(
                    video_bytes,
                    output_dir=str(videos_dir / "evidence"),
                    extract_frame_at=0.5,
                    blur_kernel_size=blur_size,
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
                blurred_bytes, ticket_jpeg = process_video(video_bytes, **blur_kw)
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
            blurred_bytes, ticket_jpeg = process_video(video_bytes, **blur_kw)
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
                print(f"[Job {job.id}] Plate {license_plate} not found in MoT registry (keeping detected value)", flush=True)
                plate_reason = f"Detected plate {license_plate} — not found in Ministry of Transport registry (data.gov.il); may be OCR error or unregistered vehicle"

        # Store "" for "not identified" in DB (UI shows Hebrew "לא זוהה")
        display_plate = "" if (not license_plate or license_plate == "11111") else license_plate

        # Save to filesystem: videos/processed/job_{id}.mp4, videos/frames/job_{id}.jpg
        proc_path = videos_dir / "processed" / f"job_{job.id}.mp4"
        frame_path = videos_dir / "frames" / f"job_{job.id}.jpg"
        proc_path.write_bytes(blurred_bytes)
        frame_path.write_bytes(ticket_jpeg)

        rel_video = f"processed/job_{job.id}.mp4"
        rel_frame = f"frames/job_{job.id}.jpg"

        video_params = extract_video_params(str(raw_path))

        location_str = f"{job.latitude or 0:.6f}, {job.longitude or 0:.6f}"
        ticket_kw = dict(
            license_plate=display_plate,
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
            video_params=video_params if video_params else None,
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

        # Extract 5 evenly-spaced screenshots from the blurred video and save them
        try:
            frames = extract_frames(blurred_bytes, count=5)
            screenshots_dir = videos_dir / "screenshots" / f"ticket_{ticket.id}"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            from sqlalchemy import text as _text
            now_utc = datetime.now(timezone.utc)
            for jpeg_bytes, frame_sec in frames:
                fname = f"shot_{int(frame_sec * 1000):08d}ms.jpg"
                fpath = screenshots_dir / fname
                fpath.write_bytes(jpeg_bytes)
                rel = f"screenshots/ticket_{ticket.id}/{fname}"
                try:
                    db.execute(
                        _text("""
                            INSERT INTO ticket_screenshots
                                (ticket_id, storage_path, frame_time_seconds, created_at, is_blurred_source)
                            VALUES
                                (:ticket_id, :storage_path, :frame_time_seconds, :created_at, true)
                        """),
                        {"ticket_id": ticket.id, "storage_path": rel,
                         "frame_time_seconds": frame_sec, "created_at": now_utc},
                    )
                except Exception:
                    db.rollback()
            db.commit()
            print(f"[Job {job.id}] Saved {len(frames)} screenshots for ticket {ticket.id}", flush=True)
        except Exception as ss_err:
            print(f"[Job {job.id}] Screenshot extraction failed (non-fatal): {ss_err}", flush=True)

        job_repo.update(
            job.id,
            status="completed",
            ticket_id=ticket.id,
            license_plate=display_plate,
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
    # Check Tesseract (plate OCR) at startup; set path on Windows if not in PATH
    try:
        import pytesseract
        for _p in [
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ]:
            if _p.exists():
                pytesseract.pytesseract.tesseract_cmd = str(_p)
                break
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

