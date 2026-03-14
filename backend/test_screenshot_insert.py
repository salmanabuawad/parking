"""Reproduce screenshot INSERT to see actual DB error."""
from datetime import datetime, timezone
from sqlalchemy import text
from app.database import engine

ticket_id = 97
stored_rel = "screenshots/ticket_97/shot_test.png"
frame_time_sec = 0.0
video_ts_text = "2026-03-14T14:47:39"
username = "admin"
now = datetime.now(timezone.utc)
frame_ms = 0
captured_at = datetime(2026, 3, 14, 14, 47, 39, 829000, tzinfo=timezone.utc)

params = {
    "ticket_id": ticket_id,
    "storage_path": stored_rel,
    "frame_time_seconds": frame_time_sec,
    "video_timestamp": captured_at,
    "created_by": username,
    "created_at": now,
    "frame_time_sec": frame_time_sec,
    "captured_at": captured_at,
    "image_path": stored_rel,
    "frame_timestamp_ms": frame_ms,
    "video_timestamp_text": video_ts_text or " ",
    "captured_by_val": username,
}

sql = """
INSERT INTO ticket_screenshots (
    ticket_id, storage_path, frame_time_seconds,
    video_timestamp, created_by, created_at,
    frame_time_sec, captured_at, image_path, frame_timestamp_ms,
    video_timestamp_text, captured_by, is_blurred_source
) VALUES (
    :ticket_id, :storage_path, :frame_time_seconds,
    :video_timestamp, :created_by, :created_at,
    :frame_time_sec, :captured_at, :image_path, :frame_timestamp_ms,
    :video_timestamp_text, :captured_by_val, true
)
RETURNING id, created_at
"""

try:
    with engine.connect() as conn:
        row = conn.execute(text(sql), params).fetchone()
        conn.commit()
    print("OK", row)
except Exception as e:
    print("ERROR:", type(e).__name__, e)
