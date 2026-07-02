"""Video retention (system-settings requirement #1): purge processed/original video files once they
are older than app_config.video_retention_days. The ticket ROW is kept (the record is retained for
audit); only the large media is freed and its paths nulled so the UI shows 'no video'.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AppConfig, Ticket


def cleanup_expired_videos(db: Session) -> dict:
    """Delete processed + original videos for tickets older than the configured retention window."""
    cfg = db.query(AppConfig).first()
    days = int(getattr(cfg, "video_retention_days", 90) or 90) if cfg else 90
    if days <= 0:  # 0/negative disables retention purging
        return {"days": days, "tickets": 0, "freed_mb": 0.0}
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    vd = Path(settings.videos_dir)
    tickets = 0
    freed = 0
    for t in db.query(Ticket).filter(Ticket.created_at < cutoff).all():
        touched = False
        for attr in ("video_path", "original_video_path"):
            rel = getattr(t, attr, None)
            if not rel:
                continue
            p = vd / rel
            if p.exists():
                freed += p.stat().st_size
                p.unlink()
            sig = Path(str(p) + ".sig")
            if sig.exists():
                sig.unlink()
            setattr(t, attr, None)
            touched = True
        if touched:
            tickets += 1
    if tickets:
        db.commit()
    return {"days": days, "tickets": tickets, "freed_mb": round(freed / 1e6, 1)}
