# Temporal blur patch

This patch does two things:

1. keeps blur settings in the database-backed `app_config` row
2. adds temporal blur tracking so brief detection misses do not leak a sharp plate

## Grounded repo facts

These facts come from the current public repo state:

- `AppConfig` already stores `blur_kernel_size` in the database.
- `settings.py` already exposes `blur_kernel_size` over `/api/settings`.
- `pipeline.py` currently uses `PlateTracker`, but the blur pass still depends on per-frame boxes and can benefit from a dedicated temporal blur tracker.

## What changed

### Database / settings

Added to `app_config`:

- `blur_expand_ratio`
- `temporal_blur_enabled`
- `temporal_blur_max_misses`

`blur_kernel_size` remains the main blur strength setting and is already persisted in DB.

### Pipeline

Added `TemporalBlurTracker`:

- expands the blur/restore box by `blur_expand_ratio`
- predicts a short forward motion using the last two reliable boxes
- keeps the box alive for `temporal_blur_max_misses` missed frames

## Why this helps

Short detector dropouts are common in motion blur, reflections, glare, or compression.
Without temporal carry-over, one missed frame can briefly reveal the target region.
This patch reduces that risk.

## Apply order

1. copy patched files into the repo
2. run:

```bash
cd backend
python migrate_app_config_temporal_blur.py
```

3. restart backend
4. update blur settings through `/api/settings`

## UI settings to expose

Expose these settings in the admin settings screen:

- Blur kernel size
- Blur expand ratio
- Temporal blur enabled
- Temporal blur max misses

Recommended defaults:

- blur kernel size: `15`
- blur expand ratio: `0.18`
- temporal blur enabled: `true`
- temporal blur max misses: `6`
