"""
Re-run the detection engine on EXISTING tickets' videos and UPDATE each ticket in place.

No new tickets are created (no duplicates); ticket IDs, status, review state and metadata
(lat/lng/zone/time) are all preserved. Only the engine-result fields are overwritten:
  license_plate, plate_detection_reason, plate_format(*), violation_rule_id,
  violation_decision, violation_confidence, violation_description_he/en,
  vehicle_make/model/year/color/type, and the ANPR track rows.

It does NOT regenerate the blurred video / screenshots (engine RESULTS only).

Mirrors run_upload_worker.process_one_job's engine invocation exactly so results match
what the worker would now produce.

Run from the backend dir with the venv + .env pointing at the target DB:
  python reprocess_existing.py --dry-run --limit 1   # run engine on 1 ticket, write nothing
  python reprocess_existing.py --limit 1             # write just 1 ticket (verify)
  python reprocess_existing.py                       # all completed jobs/tickets
  python reprocess_existing.py --ticket 12           # only ticket id 12
"""
import argparse
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.database import SessionLocal
from app.models import AppConfig, UploadJob
from app.repositories import TicketRepository
from app.repositories.anpr_track_repo import AnprTrackRepository

_BACKEND_ROOT = Path(__file__).resolve().parent


def _engine_plate(video_bytes: bytes, blur_size: int, cfg, job_id: int):
    """Run the enterprise plate pipeline (same config as the worker). Returns (plate|None, anpr_tracks)."""
    from app.plate_pipeline.pipeline import run_pipeline
    from app.plate_pipeline.config import PipelineConfig

    plate_model = _BACKEND_ROOT / "models" / "license_plate_detector.pt"
    detector_backend = "enterprise"
    ocr_every = 5
    det_zoom = 1.60
    det_roi_y0 = 0.26
    max_frames = 150
    min_votes = 1
    if cfg:
        db_backend = str(getattr(cfg, "anpr_detector_backend", "enterprise") or "enterprise").lower()
        if db_backend in {"hsv", "yolo", "enterprise"}:
            detector_backend = db_backend
        ocr_every = max(3, min(12, int(getattr(cfg, "anpr_ocr_every_n_frames", 5) or 5)))
        det_zoom = max(1.0, min(4.0, float(getattr(cfg, "enterprise_detection_zoom", 1.75) or 1.75)))
        det_roi_y0 = max(0.0, min(0.85, float(getattr(cfg, "enterprise_detection_roi_y_start", 0.26) or 0.26)))
    plate_yolo = str(plate_model) if plate_model.is_file() else "models/license_plate_detector.pt"

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as t:
        t.write(video_bytes)
        in_path = Path(t.name)
    out_path = Path(tempfile.mktemp(suffix=".mp4"))
    try:
        pc = PipelineConfig(
            input_path=in_path,
            output_path=out_path,
            blur_kernel_size=blur_size,
            max_frames=max_frames,
            output_json=False,
            detector_backend=detector_backend,
            plate_yolo_model_path=plate_yolo,
            disable_ocr=False,  # always re-OCR when reprocessing
            ocr_every_n_frames=ocr_every,
            enterprise_detection_zoom=det_zoom,
            enterprise_detection_roi_y_start=det_roi_y0,
            anpr_min_votes_stable=min_votes,
        )
        result = run_pipeline(pc)
        return (result.get("validated_plate") or None, result.get("anpr_tracks") or [])
    finally:
        in_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)


def _engine_violation(video_bytes: bytes, zone, allowed_rules, captured_at) -> dict:
    from app.violation.services.violation_analyzer import ViolationAnalyzer
    v = ViolationAnalyzer().analyze(video_bytes, violation_zone=zone, allowed_rules=allowed_rules, captured_at=captured_at)
    return {
        "violation_rule_id":        v.rule_id or None,
        "violation_decision":       v.decision_state,
        "violation_confidence":     v.confidence,
        "violation_description_he": v.description_he or None,
        "violation_description_en": v.description_en or None,
    }


def _lookup_vehicle(plate: str) -> dict:
    if not plate or plate == "11111":
        return {}
    try:
        from app.violation.services.registry import VehicleRegistryService
        rec = VehicleRegistryService().lookup(plate)
        if rec:
            return {"vehicle_make": rec.manufacturer, "vehicle_model": rec.model_name, "vehicle_year": rec.production_year}
    except Exception:
        pass
    try:
        from app.violation.services.data_gov_il import data_gov_il_lookup
        gov = data_gov_il_lookup(plate)
        if gov:
            return {
                "vehicle_make":  gov.get("manufacturer"),
                "vehicle_model": gov.get("model_name"),
                "vehicle_year":  gov.get("year"),
                "vehicle_color": gov.get("color"),
                "vehicle_type":  gov.get("vehicle_type"),
            }
    except Exception:
        pass
    return {}


def _find_video(videos_dir: Path, job, ticket) -> Path | None:
    candidates = [
        videos_dir / "original" / f"job_{job.id}.mp4",
    ]
    if getattr(ticket, "original_video_path", None):
        candidates.append(videos_dir / ticket.original_video_path)
    for c in candidates:
        try:
            if c.exists() and c.stat().st_size > 1024:
                return c
        except Exception:
            pass
    return None


def main():
    ap = argparse.ArgumentParser(description="Re-run the engine on existing tickets, update in place")
    ap.add_argument("--limit", type=int, default=0, help="process only first N (0 = all)")
    ap.add_argument("--ticket", type=int, default=0, help="only this ticket id")
    ap.add_argument("--dry-run", action="store_true", help="run engine but DO NOT write to DB")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        ticket_repo = TicketRepository(db)
        cfg = db.query(AppConfig).first()
        videos_dir = Path(settings.videos_dir).resolve()
        print(f"Videos dir: {videos_dir}", flush=True)

        jobs = (
            db.query(UploadJob)
            .filter(UploadJob.status == "completed", UploadJob.ticket_id.isnot(None))
            .order_by(UploadJob.id)
            .all()
        )
        if args.ticket:
            jobs = [j for j in jobs if j.ticket_id == args.ticket]
        if args.limit:
            jobs = jobs[: args.limit]

        print(f"Reprocessing {len(jobs)} ticket(s).  dry_run={args.dry_run}", flush=True)
        ok = skipped = failed = 0

        for i, job in enumerate(jobs, 1):
            tid = job.ticket_id
            ticket = ticket_repo.get(tid)
            if not ticket:
                print(f"[{i}/{len(jobs)}] ticket {tid}: NOT FOUND — skip", flush=True)
                skipped += 1
                continue
            vid = _find_video(videos_dir, job, ticket)
            if not vid:
                print(f"[{i}/{len(jobs)}] ticket {tid} (job {job.id}): no source video — skip", flush=True)
                skipped += 1
                continue
            try:
                video_bytes = vid.read_bytes()
                blur = 3
                if cfg and getattr(cfg, "blur_kernel_size", None) and cfg.blur_kernel_size > 0:
                    blur = max(3, cfg.blur_kernel_size)
                if blur % 2 == 0:
                    blur += 1

                t0 = time.monotonic()
                plate, anpr = _engine_plate(video_bytes, blur, cfg, job.id)

                # camera-specific rules / zone (mirror the worker)
                allowed_rules = None
                zone = job.violation_zone
                if job.camera_id and job.camera_id not in ("", "mobile"):
                    try:
                        from app.models import Camera as CameraModel
                        cam = db.query(CameraModel).filter(CameraModel.id == int(job.camera_id)).first()
                        if cam:
                            if cam.violation_rules:
                                allowed_rules = cam.violation_rules
                            if cam.violation_zone and not zone:
                                zone = cam.violation_zone
                            if getattr(cam, "zones", None):
                                zc = [z.zone_code for z in cam.zones if z.is_active]
                                if zc:
                                    zone = zc[0]
                    except Exception:
                        pass

                viol = _engine_violation(video_bytes, zone, allowed_rules, job.captured_at)
                display_plate = "" if (not plate or plate == "11111") else plate
                veh = _lookup_vehicle(display_plate)

                fields = dict(license_plate=display_plate, **viol)
                fields["plate_detection_reason"] = None if display_plate else "Plate not detected by engine"
                if veh:
                    fields.update(veh)

                dur = time.monotonic() - t0
                print(
                    f"[{i}/{len(jobs)}] ticket {tid} (job {job.id}): "
                    f"plate {ticket.license_plate!r}->{display_plate!r}  "
                    f"decision {ticket.violation_decision!r}->{viol.get('violation_decision')!r}  "
                    f"conf={viol.get('violation_confidence')}  anpr={len(anpr)}  ({dur:.1f}s)",
                    flush=True,
                )

                if not args.dry_run:
                    ticket_repo.update(tid, **fields)
                    if anpr:
                        try:
                            AnprTrackRepository(db).replace_for_ticket(tid, anpr)
                        except Exception as e:
                            print(f"    ANPR update failed (non-fatal): {e}", flush=True)
                ok += 1
            except Exception as e:
                traceback.print_exc()
                print(f"[{i}/{len(jobs)}] ticket {tid} (job {job.id}): FAILED — {e}", flush=True)
                failed += 1

        print(f"\nDone. ok={ok} skipped={skipped} failed={failed}", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
