"""Regenerate per-car result VIDEOS in place for existing ticketed clips.

Applies the privacy change "keep the whole violating car sharp so the plate number is never
blurred" to videos that were already produced with the old (plate-box-only) rendering. Re-runs
the vehicle-first pipeline (OCR is deterministic, so the plate is unchanged), then overwrites
each ticket's existing video + frame + signature in place. Does NOT create or delete tickets,
and does not touch the license_plate / review fields.

Run from backend dir (venv + .env): python regen_videos.py [--ticket N]
"""
import argparse
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.database import SessionLocal
from app.models import AppConfig, Ticket
from app.repositories import TicketRepository
from app.plate_pipeline.pipeline import _run_pipeline_vehicle_multi
from app.plate_pipeline.config import PipelineConfig
from app.services.video_processor import extract_frames

videos_dir = Path(settings.videos_dir).resolve()


def _src_for(ticket) -> Path | None:
    jid = None
    m = re.search(r"job_(\d+)", ticket.video_path or "")
    if m:
        jid = m.group(1)
    if jid:
        f = videos_dir / "original" / f"job_{jid}.mp4"
        if f.exists():
            return f
    if ticket.original_video_path:
        f = videos_dir / ticket.original_video_path
        if f.exists():
            return f
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticket", type=int, default=0)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        repo = TicketRepository(db)
        cfg = db.query(AppConfig).first()
        blur = 3
        if cfg and getattr(cfg, "blur_kernel_size", None) and cfg.blur_kernel_size > 0:
            blur = max(3, cfg.blur_kernel_size)
        if blur % 2 == 0:
            blur += 1

        tickets = [
            t for t in db.query(Ticket).order_by(Ticket.id).all()
            if (t.license_plate or "") not in ("", "11111") and t.video_path
        ]
        if args.ticket:
            tickets = [t for t in tickets if t.id == args.ticket]
        print(f"Regenerating {len(tickets)} ticketed video(s)  blur={blur}", flush=True)

        for t in tickets:
            src = _src_for(t)
            if not src:
                print(f"#{t.id} {t.license_plate}: no source video — skip", flush=True)
                continue
            _clk = t.captured_at or t.created_at
            pc = PipelineConfig(
                input_path=src, output_path=Path(tempfile.mktemp(suffix=".mp4")),
                blur_kernel_size=blur, max_frames=150, output_json=False,
                detector_backend="enterprise", disable_ocr=False, ocr_every_n_frames=5,
                clock_start_epoch=(_clk.timestamp() if _clk else None),
                video_timestamp_overlay=bool(getattr(cfg, "video_timestamp_overlay", True)) if cfg else True,
            )
            # Force the on-video label to the ticket's recorded plate (noisy OCR isn't run-to-run
            # stable, so a re-run could otherwise show a different near-miss than the ticket).
            r = _run_pipeline_vehicle_multi(pc, overlay_plate_override=t.license_plate)
            tracks = r.get("tracks_render") or []
            if not tracks:
                print(f"#{t.id} {t.license_plate}: pipeline produced no car video — kept old", flush=True)
                continue
            pick = max(tracks, key=lambda x: x.get("vote_count", 0))  # primary car (all show ticket plate)
            vb = pick["video_bytes"]  # write_video already encodes H.264
            if not vb:
                print(f"#{t.id}: empty video bytes — skip", flush=True)
                continue
            dst = videos_dir / t.video_path
            dst.write_bytes(vb)
            # refresh the still frame
            try:
                fr = extract_frames(vb, count=1)
                if fr and t.ticket_image_path:
                    (videos_dir / t.ticket_image_path).write_bytes(fr[0][0])
            except Exception as e:
                print(f"    frame refresh failed: {e}", flush=True)
            # re-sign so the signature matches the new bytes
            try:
                from app.services.video_signing import sign_processed_video
                sig_hex, _pub, fp = sign_processed_video(
                    vb, job_id=t.upload_job_id or 0, ticket_id=t.id,
                    captured_at=t.captured_at, keys_dir=videos_dir,
                )
                dst.with_suffix(".mp4.sig").write_text(sig_hex)
                repo.update(t.id, video_signature=sig_hex, video_signature_key=fp,
                            video_signed_at=datetime.now(timezone.utc))
            except Exception as e:
                print(f"    re-sign failed (non-fatal): {e}", flush=True)
            print(f"#{t.id} {t.license_plate}: regenerated {t.video_path} ({len(vb)//1024} KB) — car kept sharp", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
