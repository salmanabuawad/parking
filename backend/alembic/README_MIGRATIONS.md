# Database migrations to add

This package adds a migration for the new evidence workflow and confidence engine.

## Why a migration is needed
The requested features add data that should be persisted:
- screenshot evidence captured from the blurred admin video
- timestamped screenshot metadata
- target-track and parking-vs-traffic-stop reasoning
- final confidence status and reason
- registry/vehicle cross-check payloads

## Included migration
- `alembic/versions/20260314_0001_masterpiece_evidence_and_confidence.py`

## What it adds
### New `tickets` columns
- `source_video_hash`
- `confidence_status`
- `confidence_reason`
- `parking_likelihood_score`
- `stop_due_to_traffic_possible`
- `stationary_duration_seconds`
- `traffic_flow_state`
- `target_track_id`
- `registry_match` (JSON)
- `vehicle_attributes` (JSON)
- `evidence_summary` (JSON)

### New table: `ticket_screenshots`
Stores screenshots taken by admins from the blurred video player with frame timestamp and audit metadata.

## If Alembic is not initialized in the repo yet
From `backend/`:

```bash
alembic init alembic
```

Then wire `env.py` to your SQLAlchemy metadata and place the included revision file under `alembic/versions/`.

## Apply
```bash
alembic upgrade head
```
