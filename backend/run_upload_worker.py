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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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

_VIDEOS_DIR = settings.videos_dir


def _fmt_queue(status: dict) -> str:
    q, p, c, f = status.get("queued", 0), status.get("processing", 0), status.get("completed", 0), status.get("failed", 0)
    extra = ""
    ids = status.get("next_ids") or []
    if ids:
        extra = f" | next: {ids}"
    return f"q:{q} p:{p} c:{c} f:{f}{extra}"


def _run_ocr(video_bytes: bytes, job_id: int) -> tuple[str, str | None]:
    """OCR worker: runs in thread pool."""
    try:
        plate, reason = extract_license_plate(video_bytes=video_bytes)
        if plate != "11111":
            print(f"[Job {job_id}] OCR detected plate: {plate}", flush=True)
        else:
            print(f"[Job {job_id}] Plate not extracted: {reason or 'Unknown'}", flush=True)
        return plate, reason
    except Exception as e:
        print(f"[Job {job_id}] OCR failed: {e}", flush=True)
        return "11111", str(e)


def _run_violation_analysis(video_bytes: bytes, violation_zone: str | None, job_id: int) -> dict:
    """Violation analysis worker: runs in thread pool."""
    try:
        from app.violation.services.violation_analyzer import ViolationAnalyzer
        analyzer = ViolationAnalyzer()
        v = analyzer.analyze(video_bytes, violation_zone=violation_zone)
        print(
            f"[Job {job_id}] Violation: rule={v.rule_id} state={v.decision_state} conf={v.confidence:.2f}",
            flush=True,
        )
        return {
            "violation_rule_id":        v.rule_id or None,
            "violation_decision":       v.decision_state,
            "violation_confidence":     v.confidence,
            "violation_description_he": v.description_he or None,
            "violation_description_en": v.description_en or None,
        }
    except Exception as e:
        print(f"[Job {job_id}] Violation analysis failed (non-fatal): {e}", flush=True)
        return {}


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
            reset = job_repo.reset_stuck_processing()
            if reset > 0:
                print(f"[{datetime.now().isoformat()}] Reset {reset} stuck job(s) to queued", flush=True)
            return False

        if not job.raw_video_path:
            job_repo.update(job.id, status="failed", error_message="No raw video path (legacy job?)")
            return True

        job_repo.update(job.id, status="processing", processing_started_at=datetime.now(timezone.utc))
        s = job_repo.get_queue_status()
        print(f"[{datetime.now().isoformat()}] Job {job.id} picked up | {_fmt_queue(s)}", flush=True)

        videos_dir = Path(settings.videos_dir).resolve()
        raw_dir = videos_dir / "raw"
        path_str = (job.raw_video_path or "").strip().replace("\\", "/")
        raw_path = (videos_dir / path_str).resolve()

        if not raw_path.exists():
            base_name = Path(path_str).name
            fallback = raw_dir / base_name
            if fallback.resolve().exists():
                raw_path = fallback.resolve()

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
                f"Ensure API and worker use the same VIDEOS_DIR."
            )
            job_repo.update(job.id, status="failed", error_message=err)
            return True

        video_bytes = raw_path.read_bytes()
        if not video_bytes:
            job_repo.update(job.id, status="failed", error_message="Raw video file is empty")
            return True

        cfg = db.query(AppConfig).first()
        use_fast = getattr(settings, 'use_fast_hsv_pipeline', True)
        blur_size = 15
        if cfg and getattr(cfg, 'blur_kernel_size', None) is not None and cfg.blur_kernel_size > 0:
            blur_size = max(3, cfg.blur_kernel_size)
        if blur_size % 2 == 0:
            blur_size += 1
        blur_kw = {'blur_strength': blur_size}

        # --- Step 1: process video (blur) ---
        t0 = time.monotonic()
        if use_fast:
            blurred_bytes, ticket_jpeg = process_video_fast_hsv(video_bytes, **blur_kw)
        else:
            blurred_bytes, ticket_jpeg = process_video(video_bytes, **blur_kw)
        print(f"[Job {job.id}] Video processed in {time.monotonic()-t0:.1f}s", flush=True)

        # --- Step 2: OCR + violation analysis in parallel ---
        plate_from_job = job.license_plate
        skip_ocr = bool(plate_from_job and plate_from_job != "11111")

        t1 = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {}
            if not skip_ocr:
                futures["ocr"] = pool.submit(_run_ocr, video_bytes, job.id)
            futures["violation"] = pool.submit(
                _run_violation_analysis, video_bytes, job.violation_zone, job.id
            )

            ocr_result = (plate_from_job or "11111", None)
            violation_data: dict = {}
            for key, future in futures.items():
                try:
                    result = future.result()
                    if key == "ocr":
                        ocr_result = result
                    else:
                        violation_data = result
                except Exception as e:
                    print(f"[Job {job.id}] {key} future error: {e}", flush=True)

        license_plate, plate_reason = ocr_result
        print(f"[Job {job.id}] Parallel OCR+violation in {time.monotonic()-t1:.1f}s", flush=True)

        # Registry validation (optional)
        if getattr(settings, 'validate_plate_in_registry', False) and license_plate and license_plate != "11111":
            from app.violation.services.registry import VehicleRegistryService
            if not VehicleRegistryService().plate_exists(license_plate):
                print(f"[Job {job.id}] Plate {license_plate} not in MoT registry", flush=True)
                plate_reason = f"Detected {license_plate} — not in Ministry of Transport registry"

        display_plate = "" if (not license_plate or license_plate == "11111") else license_plate

        # --- Step 3: save files ---
        proc_path = videos_dir / "processed" / f"job_{job.id}.mp4"
        frame_path = videos_dir / "frames" / f"job_{job.id}.jpg"
        proc_path.write_bytes(blurred_bytes)
        frame_path.write_bytes(ticket_jpeg)

        # Delete raw file to free disk space
        try:
            raw_path.unlink(missing_ok=True)
        except Exception:
            pass

        video_params = extract_video_params(str(proc_path))

        # Plate format detection
        plate_format = None
        try:
            import cv2
            import numpy as np
            from app.plate_pipeline.plate_format import classify_plate_format
            frame = cv2.imdecode(np.frombuffer(ticket_jpeg, np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                from app.services.video_processor import detect_plate_box
                box = detect_plate_box(frame)
                if box:
                    _, _, w, h = box
                    fmt = classify_plate_format(w, h)
                    if fmt:
                        plate_format = fmt.get("name")
        except Exception:
            pass

        location_str = f"{job.latitude or 0:.6f}, {job.longitude or 0:.6f}"
        ticket_kw = dict(
            license_plate=display_plate,
            camera_id="mobile",
            location=location_str,
            violation_zone=job.violation_zone or "red_white",
            description=job.description or f"Mobile upload at {location_str}",
            status="pending_review",
            video_path=f"processed/job_{job.id}.mp4",
            ticket_image_path=f"frames/job_{job.id}.jpg",
            latitude=job.latitude,
            longitude=job.longitude,
            captured_at=job.captured_at,
            video_params=video_params if video_params else None,
        )
        if plate_reason:
            ticket_kw["plate_detection_reason"] = plate_reason
        if plate_format:
            ticket_kw["plate_format"] = plate_format

        ticket = ticket_repo.create(**ticket_kw)

        # Apply violation analysis result
        if violation_data:
            try:
                ticket_repo.update(ticket.id, **violation_data)
            except Exception:
                for k, v in violation_data.items():
                    setattr(ticket, k, v)
                db.commit()

        # --- Step 4: extract screenshots (non-blocking) ---
        try:
            frames = extract_frames(blurred_bytes, count=5, base_time=job.captured_at)
            screenshots_dir = videos_dir / "screenshots" / f"ticket_{ticket.id}"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            from sqlalchemy import text as _text
            now_utc = datetime.now(timezone.utc)
            for jpeg_bytes, frame_sec in frames:
                fname = f"shot_{int(frame_sec * 1000):08d}ms.jpg"
                (screenshots_dir / fname).write_bytes(jpeg_bytes)
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
        return True
    finally:
        db.close()


def main():
    idle_interval = 2.0   # seconds to wait when queue is empty
    videos_path = Path(settings.videos_dir).resolve()
    print(f"Upload worker started. Videos dir: {videos_path}", flush=True)

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
        print(f"WARNING: Tesseract not available: {e}", flush=True)

    while True:
        try:
            did_work = process_one_job()
            if not did_work:
                # Idle: wait before next poll
                time.sleep(idle_interval)
            # If we processed a job, immediately check for the next one (no sleep)
        except KeyboardInterrupt:
            print("Worker stopped.")
            break
        except Exception as e:
            traceback.print_exc()
            print(f"Worker error: {e}")
            time.sleep(idle_interval)


if __name__ == "__main__":
    main()
