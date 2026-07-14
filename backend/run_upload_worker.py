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
from datetime import datetime, timedelta, timezone
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


def _run_violation_analysis(video_bytes: bytes, violation_zone: str | None, job_id: int, allowed_rules: list | None = None, captured_at=None) -> dict:
    """Violation analysis worker: runs in thread pool."""
    try:
        from app.violation.services.violation_analyzer import ViolationAnalyzer
        analyzer = ViolationAnalyzer()
        v = analyzer.analyze(video_bytes, violation_zone=violation_zone, allowed_rules=allowed_rules, captured_at=captured_at)
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


def _camera_context(db, job) -> tuple[list | None, str | None, int | None, bool]:
    """Resolve a job's camera rules / zone / handling-inspector (all empty for mobile uploads).
    The 4th value is True when the job's camera is OUTSIDE its working days/hours at capture time."""
    allowed_rules: list | None = None
    violation_zone: str | None = job.violation_zone
    assigned_inspector: int | None = None
    off_schedule = False
    if job.camera_id and job.camera_id not in ("", "mobile"):
        try:
            from app.models import Camera as CameraModel
            cam = db.query(CameraModel).filter(CameraModel.id == int(job.camera_id)).first()
            if cam:
                assigned_inspector = getattr(cam, "assigned_inspector_id", None)
                if cam.violation_rules:
                    allowed_rules = cam.violation_rules
                if cam.violation_zone and not violation_zone:
                    violation_zone = cam.violation_zone
                if getattr(cam, "zones", None):
                    zone_codes = [z.zone_code for z in cam.zones if z.is_active]
                    if zone_codes:
                        violation_zone = zone_codes[0]
                from app.services.ticket_snapshot_service import camera_active_at
                off_schedule = not camera_active_at(cam, job.captured_at)
        except (ValueError, TypeError, Exception) as cam_err:
            print(f"[Job {job.id}] Camera lookup skipped: {cam_err}", flush=True)
    return allowed_rules, violation_zone, assigned_inspector, off_schedule


def _ensure_h264(video_bytes: bytes, job_id: int) -> bytes:
    """Re-encode the processed video to browser-playable H.264.

    OpenCV's VideoWriter (used by the enterprise/blur pipeline) emits MPEG-4 Part 2
    ('mp4v'), which Chrome/Firefox cannot decode -> the evidence video shows as a black
    player. Re-encode to H.264 (yuv420p + faststart) so it plays everywhere. Falls back
    to the original bytes if ffmpeg is unavailable or fails.
    """
    if not video_bytes:
        return video_bytes
    import subprocess
    import tempfile as _tf
    try:
        from app.services.video_processor import get_ffmpeg
        ffmpeg = get_ffmpeg()
    except Exception as e:
        print(f"[Job {job_id}] ffmpeg unavailable, leaving video as-is: {e}", flush=True)
        return video_bytes
    src = Path(_tf.mktemp(suffix=".mp4"))
    dst = Path(_tf.mktemp(suffix=".mp4"))
    try:
        src.write_bytes(video_bytes)
        r = subprocess.run(
            [ffmpeg, "-y", "-i", str(src), "-c:v", "libx264", "-preset", "fast",
             "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(dst)],
            capture_output=True, timeout=600,
        )
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 256:
            out = dst.read_bytes()
            print(f"[Job {job_id}] Re-encoded processed video to H.264 ({len(out)} B)", flush=True)
            return out
        err = (r.stderr or b"").decode(errors="replace")[-300:]
        print(f"[Job {job_id}] H.264 re-encode failed rc={r.returncode}: {err}", flush=True)
        return video_bytes
    except Exception as e:
        print(f"[Job {job_id}] H.264 re-encode error (non-fatal): {e}", flush=True)
        return video_bytes
    finally:
        src.unlink(missing_ok=True)
        dst.unlink(missing_ok=True)


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
        blur_size = 3  # default: very light blur; AppConfig.blur_kernel_size overrides
        if cfg and getattr(cfg, 'blur_kernel_size', None) is not None and cfg.blur_kernel_size > 0:
            blur_size = max(3, cfg.blur_kernel_size)
        if blur_size % 2 == 0:
            blur_size += 1
        blur_kw = {'blur_strength': blur_size}

        # --- Step 1: multi-car detect + per-car OCR + per-car privacy videos ---
        t0 = time.monotonic()
        _backend_root = Path(__file__).resolve().parent
        _plate_model = _backend_root / "models" / "license_plate_detector.pt"
        _detector_backend = "enterprise"
        _ocr_every = 5
        _det_zoom = 1.60
        _det_roi_y0 = 0.26
        _max_frames = 150
        _min_votes_stable = 1
        _blur_except_plate = True
        if cfg:
            _db_backend = str(getattr(cfg, "anpr_detector_backend", "enterprise") or "enterprise").lower()
            if _db_backend in {"hsv", "yolo", "enterprise"}:
                _detector_backend = _db_backend
            _ocr_every = max(3, min(12, int(getattr(cfg, "anpr_ocr_every_n_frames", 5) or 5)))
            _det_zoom = max(1.0, min(4.0, float(getattr(cfg, "enterprise_detection_zoom", 1.75) or 1.75)))
            _det_roi_y0 = max(0.0, min(0.85, float(getattr(cfg, "enterprise_detection_roi_y_start", 0.26) or 0.26)))
            _blur_except_plate = bool(getattr(cfg, "blur_except_plate", True))
        _plate_yolo_path = str(_plate_model) if _plate_model.is_file() else "models/license_plate_detector.pt"

        cars: list = []
        anpr_tracks: list = []
        overall_blurred: bytes = b""
        import tempfile as _tf
        try:
            from app.plate_pipeline.pipeline import _run_pipeline_vehicle_multi, _run_pipeline_enterprise_multi
            from app.plate_pipeline.config import PipelineConfig, hex_to_bgr

            print(
                f"[Job {job.id}] ENGINE: vehicle-first multi-car  "
                f"ocr_every={_ocr_every}  max_frames={_max_frames}",
                flush=True,
            )
            with _tf.NamedTemporaryFile(suffix=".mp4", delete=False) as _tmp_in:
                _tmp_in.write(video_bytes)
                _in_path = Path(_tmp_in.name)
            _pipe_cfg = PipelineConfig(
                input_path=_in_path,
                output_path=Path(_tf.mktemp(suffix=".mp4")),
                blur_kernel_size=blur_size,
                max_frames=_max_frames,
                output_json=False,
                detector_backend=_detector_backend,
                plate_yolo_model_path=_plate_yolo_path,
                disable_ocr=False,
                ocr_every_n_frames=_ocr_every,
                enterprise_detection_zoom=_det_zoom,
                enterprise_detection_roi_y_start=_det_roi_y0,
                anpr_min_votes_stable=_min_votes_stable,
                clock_start_epoch=(job.captured_at.timestamp() if job.captured_at else None),
                video_timestamp_overlay=bool(getattr(cfg, "video_timestamp_overlay", True)) if cfg else True,
                blur_except_plate=_blur_except_plate,
                box_color_bgr=(hex_to_bgr(getattr(cfg, "pending_frame_color", "#00FF00")) if cfg else (0, 255, 0)),
                timestamp_overlay_position=(getattr(cfg, "timestamp_overlay_position", "top_right") if cfg else "top_right"),
                plate_inset_enabled=(bool(getattr(cfg, "plate_inset_enabled", True)) if cfg else True),
                overlay_camera_id=(str(job.camera_id) if job.camera_id not in (None, "", "mobile") else None),
            )
            # Vehicle-first: track each car (occlusion-robust) and read its plate across the clip.
            try:
                _result = _run_pipeline_vehicle_multi(_pipe_cfg)
            except Exception as _veh_err:
                print(f"[Job {job.id}] vehicle-first failed ({_veh_err}); falling back to plate-first", flush=True)
                _result = {}
            cars = _result.get("tracks_render") or []
            anpr_tracks = _result.get("anpr_tracks") or []
            overall_blurred = _result.get("overall_video_bytes") or b""
            # Fallback: if no car was found, try plate-first detection (no vehicle model).
            if not cars:
                print(f"[Job {job.id}] vehicle-first found no car; trying plate-first", flush=True)
                _result2 = _run_pipeline_enterprise_multi(_pipe_cfg)
                cars = _result2.get("tracks_render") or []
                anpr_tracks = _result2.get("anpr_tracks") or anpr_tracks
                overall_blurred = _result2.get("overall_video_bytes") or overall_blurred
            _in_path.unlink(missing_ok=True)
            print(f"[Job {job.id}] multi-car: {len(cars)} car(s) in {time.monotonic()-t0:.1f}s", flush=True)
        except Exception as _pipe_err:
            print(f"[Job {job.id}] Multi-car pipeline failed ({_pipe_err}), falling back to single blur", flush=True)
            traceback.print_exc()
            try:
                if use_fast:
                    overall_blurred, _ = process_video_fast_hsv(video_bytes, **blur_kw)
                else:
                    overall_blurred, _ = process_video(video_bytes, **blur_kw)
                overall_blurred = _ensure_h264(overall_blurred, job.id)
            except Exception as _fb:
                print(f"[Job {job.id}] Fallback blur failed: {_fb}", flush=True)
                overall_blurred = b""

        # --- Step 2: camera rules/zone + video-level violation analysis (applied to each car) ---
        camera_allowed_rules, camera_violation_zone, camera_assigned_inspector, camera_off_schedule = _camera_context(db, job)

        # Enforcement schedule: outside a camera's working days/hours, still make a ticket but
        # auto-reject it (visible, not silently dropped) — see status/admin_notes in _finalize_ticket.
        if camera_off_schedule:
            print(f"[Job {job.id}] camera outside working days/hours at {job.captured_at} — ticket(s) auto-rejected", flush=True)

        violation_data: dict = _run_violation_analysis(
            video_bytes, camera_violation_zone, job.id, camera_allowed_rules, job.captured_at
        )

        # Preserve the original unblurred video once (shared by all this job's tickets)
        original_video_rel: str | None = None
        try:
            orig_dir = videos_dir / "original"
            orig_dir.mkdir(parents=True, exist_ok=True)
            orig_path = orig_dir / f"job_{job.id}.mp4"
            raw_path.rename(orig_path)
            original_video_rel = f"original/job_{job.id}.mp4"
        except Exception as move_err:
            print(f"[Job {job.id}] Could not preserve original (non-fatal): {move_err}", flush=True)
            try:
                raw_path.unlink(missing_ok=True)
            except Exception:
                pass

        def _finalize_ticket(*, video_bytes_out: bytes, plate: str, anpr_track, suffix: str, candidates=None):
            """Save one car's video + frame, sign it, create its ticket, attach violation/anpr/screenshots."""
            display_plate = "" if (not plate or plate == "11111") else plate
            proc_rel = f"processed/job_{job.id}{suffix}.mp4"
            frame_rel = f"frames/job_{job.id}{suffix}.jpg"
            proc_path = videos_dir / proc_rel
            proc_path.write_bytes(video_bytes_out or b"")
            try:
                _f = extract_frames(video_bytes_out, count=1) if video_bytes_out else []
                ticket_jpeg = _f[0][0] if _f else b""
            except Exception:
                ticket_jpeg = b""
            (videos_dir / frame_rel).write_bytes(ticket_jpeg)

            sig_hex = sig_key_fp = None
            try:
                from app.services.video_signing import sign_processed_video
                sig_hex, _pub, sig_key_fp = sign_processed_video(
                    video_bytes_out, job_id=job.id, ticket_id=0,
                    captured_at=job.captured_at, keys_dir=videos_dir,
                )
                proc_path.with_suffix(".mp4.sig").write_text(sig_hex)
            except Exception as sign_err:
                print(f"[Job {job.id}] signing failed (non-fatal): {sign_err}", flush=True)

            # Resolve plate/registry/exemption/snapshot/window fields (logic lives in the service).
            video_params = extract_video_params(str(proc_path))
            # #4 — which enforcement section the suspected vehicle sits in. Fixed cameras only
            # (mobile uploads have no polygons → None). The car-centre is scaled from video pixels
            # into the camera's calibration space when the two sizes differ. Best-effort; never fatal.
            _section_id = None
            try:
                if job.camera_id not in (None, "", "mobile") and anpr_track and anpr_track.get("vehicle_box"):
                    from app.services.ticket_snapshot_service import find_section_for_point
                    from app.models import Camera as _Camera
                    _bx1, _by1, _bx2, _by2 = anpr_track["vehicle_box"]
                    _ccx, _ccy = (_bx1 + _bx2) / 2.0, (_by1 + _by2) / 2.0
                    _cam = (db.query(_Camera).filter(_Camera.id == int(job.camera_id)).first()
                            if str(job.camera_id).isdigit() else None)
                    _vw = (video_params or {}).get("width")
                    _vh = (video_params or {}).get("height")
                    if _cam and _cam.calibration_width and _cam.calibration_height and _vw and _vh:
                        _ccx *= _cam.calibration_width / float(_vw)
                        _ccy *= _cam.calibration_height / float(_vh)
                    _section_id = find_section_for_point(db, job.camera_id, _ccx, _ccy)
            except Exception as _sec_err:
                print(f"[Job {job.id}] section derivation failed (non-fatal): {_sec_err}", flush=True)
            from app.services.ticket_finalization import resolve_ticket_fields
            _rule_code = (violation_data or {}).get("violation_rule_id")
            fields = resolve_ticket_fields(
                db, job=job, cfg=cfg, display_plate=display_plate, candidates=candidates,
                video_params=video_params, rule_code=_rule_code, section_id=_section_id,
            )
            display_plate = fields["plate"]
            has_gps = bool(job.latitude) and bool(job.longitude)
            location_str = f"{job.latitude:.6f}, {job.longitude:.6f}" if has_gps else None
            kw = dict(
                upload_job_id=job.id,
                license_plate=display_plate,
                camera_id=(str(job.camera_id) if job.camera_id not in (None, "", "mobile") else "mobile"),
                location=location_str,
                violation_zone=job.violation_zone or "red_white",
                description=job.description or ("העלאה מהנייד" if not has_gps else f"העלאה מהנייד — {location_str}"),
                status=("rejected" if camera_off_schedule else fields["ticket_status"]),
                video_path=proc_rel,
                ticket_image_path=frame_rel,
                original_video_path=original_video_rel,
                latitude=job.latitude,
                longitude=job.longitude,
                captured_at=job.captured_at,
                violation_start_at=fields["v_start"],
                violation_end_at=fields["v_end"],
                assigned_inspector_id=(None if fields["ticket_status"] == "exempt" else camera_assigned_inspector),
                video_params=video_params if video_params else None,
            )
            if camera_off_schedule:
                kw["admin_notes"] = "נדחה אוטומטית: הצילום בוצע מחוץ לימי/שעות הפעילות של המצלמה"
            if fields["reason"]:
                kw["plate_detection_reason"] = fields["reason"]
            if sig_hex:
                kw["video_signature"] = sig_hex
                kw["video_signature_key"] = sig_key_fp
                kw["video_signed_at"] = datetime.now(timezone.utc)
            if fields["vehicle_data"]:
                kw.update(fields["vehicle_data"])
            if fields["registry_status"]:
                kw["vehicle_registry_lookup_status"] = fields["registry_status"]
            if fields["registry_raw"]:
                import json
                kw["vehicle_registry_raw_json"] = json.dumps(fields["registry_raw"], ensure_ascii=False)
            if fields["review_status"]:
                kw["review_status"] = fields["review_status"]
            for _sf, _sv in fields["snapshots"].items():
                if _sv is not None:
                    kw[_sf] = _sv
            # Evidence-integrity hashes (rule 8) + suspected-vehicle track (#10).
            try:
                import hashlib as _hl
                if video_bytes:
                    kw["original_video_sha256"] = _hl.sha256(video_bytes).hexdigest()
                if video_bytes_out:
                    kw["evidence_video_sha256"] = _hl.sha256(video_bytes_out).hexdigest()
                if ticket_jpeg:
                    kw["best_frame_sha256"] = _hl.sha256(ticket_jpeg).hexdigest()
            except Exception:
                pass
            if anpr_track and anpr_track.get("track_id") is not None:
                kw["suspected_vehicle_track_id"] = str(anpr_track["track_id"])[:40]
            if anpr_track and anpr_track.get("vehicle_box"):
                kw["suspected_vehicle_box"] = anpr_track["vehicle_box"]   # xyxy, video px (#10)
            if anpr_track and anpr_track.get("plate_box"):
                kw["plate_box"] = anpr_track["plate_box"]                 # xyxy, video px (#10)
            if _section_id is not None:
                kw["camera_section_id"] = _section_id                     # enforcement section (#4)
            ticket = ticket_repo.create(**kw)

            # #12 — audit ticket creation, the registry lookup, and any manual-review flag.
            try:
                from app.services.audit_log_service import write_ticket_audit
                write_ticket_audit(db, ticket_id=ticket.id, action_type="ticket_created",
                                   new_value={"license_plate": display_plate, "status": kw.get("status")})
                if fields.get("registry_status"):
                    write_ticket_audit(db, ticket_id=ticket.id, action_type="registry_lookup",
                                       new_value={"status": fields["registry_status"]})
                if fields.get("review_status") == "manual_review_required":
                    write_ticket_audit(db, ticket_id=ticket.id, action_type="manual_review",
                                       notes=fields.get("reason"))
            except Exception as _aud_err:
                print(f"[Job {job.id}] creation audit failed (non-fatal): {_aud_err}", flush=True)

            if anpr_track:
                try:
                    from app.repositories.anpr_track_repo import AnprTrackRepository
                    AnprTrackRepository(db).replace_for_ticket(ticket.id, [anpr_track])
                except Exception as anpr_err:
                    print(f"[Job {job.id}] ANPR log failed: {anpr_err}", flush=True)
            if violation_data:
                try:
                    ticket_repo.update(ticket.id, **violation_data)
                except Exception:
                    for k, v in violation_data.items():
                        setattr(ticket, k, v)
                    db.commit()

            # #14 — flag a cross-upload duplicate (same plate + camera near the same capture time).
            try:
                from app.services.vehicle_exemption_service import find_duplicate_ticket
                _win = int(getattr(cfg, "duplicate_ticket_window_seconds", 300) or 300) if cfg else 300
                _dup = find_duplicate_ticket(
                    db, plate=display_plate, camera_id=kw.get("camera_id"),
                    at=job.captured_at, within_seconds=_win, exclude_id=ticket.id,
                )
                if _dup is not None:
                    ticket_repo.update(ticket.id, review_status="duplicate_candidate",
                                       duplicate_of_ticket_id=_dup.id)
                    print(f"[Job {job.id}] ticket {ticket.id} flagged duplicate of {_dup.id}", flush=True)
            except Exception as _dup_err:
                print(f"[Job {job.id}] duplicate check failed (non-fatal): {_dup_err}", flush=True)

            try:
                _ss = extract_frames(video_bytes_out, count=5, base_time=job.captured_at) if video_bytes_out else []
                ss_dir = videos_dir / "screenshots" / f"ticket_{ticket.id}"
                ss_dir.mkdir(parents=True, exist_ok=True)
                from sqlalchemy import text as _text
                now_utc = datetime.now(timezone.utc)
                for jb, fsec in _ss:
                    fn = f"shot_{int(fsec * 1000):08d}ms.jpg"
                    (ss_dir / fn).write_bytes(jb)
                    try:
                        db.execute(
                            _text(
                                "INSERT INTO ticket_screenshots (ticket_id, storage_path, frame_time_seconds, created_at, is_blurred_source)"
                                " VALUES (:t, :p, :f, :c, true)"
                            ),
                            {"t": ticket.id, "p": f"screenshots/ticket_{ticket.id}/{fn}", "f": fsec, "c": now_utc},
                        )
                    except Exception:
                        db.rollback()
                db.commit()
            except Exception as ss_err:
                print(f"[Job {job.id}] screenshots failed (non-fatal): {ss_err}", flush=True)
            return ticket, display_plate

        # --- Step 3: one ticket per car (or a single 'not detected' ticket if none) ---
        from app.services.israeli_plate import normalize_israeli_plate as _norm_plate
        created: list = []
        if cars:
            cars_sorted = sorted(cars, key=lambda c: c.get("vote_count", 0), reverse=True)
            # Collapse multi-track repeats: one physical car can fragment into several tracks that
            # read the same plate — keep the highest-vote track per plate so it yields ONE ticket,
            # not duplicates. Plateless tracks (review tickets) are kept individually.
            _seen: set = set()
            _unique = []
            for _c in cars_sorted:
                _n = _norm_plate(_c.get("raw_digits") or "")
                if _n and _n in _seen:
                    print(f"[Job {job.id}] duplicate track for plate {_n} — skipped", flush=True)
                    continue
                if _n:
                    _seen.add(_n)
                _unique.append(_c)
            for idx, car in enumerate(_unique):
                tid = car.get("track_id", idx + 1)
                anpr_track = {k: car.get(k) for k in ("track_id", "raw_digits", "normalized_plate", "vote_count", "vehicle_box", "plate_box")}
                created.append(_finalize_ticket(
                    video_bytes_out=car.get("video_bytes") or b"",
                    plate=car.get("raw_digits") or "",
                    anpr_track=anpr_track,
                    suffix=f"_car{tid}",
                    candidates=car.get("candidates"),
                ))
        else:
            created.append(_finalize_ticket(
                video_bytes_out=overall_blurred,
                plate="",
                anpr_track=None,
                suffix="",
            ))

        primary_ticket, primary_plate = created[0]
        job_repo.update(
            job.id,
            status="completed",
            ticket_id=primary_ticket.id,
            license_plate=primary_plate,
            completed_at=datetime.now(timezone.utc),
            error_message=None,
        )
        s = job_repo.get_queue_status()
        print(
            f"[{datetime.now().isoformat()}] Job {job.id} completed -> {len(created)} ticket(s) "
            f"(primary {primary_ticket.id}) | {_fmt_queue(s)}",
            flush=True,
        )
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

    _last_retention = 0.0
    while True:
        try:
            did_work = process_one_job()
            # Video retention purge (system settings #1): on startup + hourly, free videos past the window.
            _now = time.monotonic()
            if _now - _last_retention > 3600:
                _last_retention = _now
                try:
                    from app.database import SessionLocal
                    from app.services.retention_service import cleanup_expired_videos
                    _rdb = SessionLocal()
                    _r = cleanup_expired_videos(_rdb)
                    _rdb.close()
                    if _r.get("tickets"):
                        print(f"[retention] purged videos from {_r['tickets']} ticket(s) older than {_r['days']}d, freed {_r['freed_mb']} MB", flush=True)
                except Exception as _re:
                    print(f"[retention] cleanup failed (non-fatal): {_re}", flush=True)
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
