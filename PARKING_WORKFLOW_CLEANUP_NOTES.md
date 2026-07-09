# Parking Workflow Cleanup Notes

This update cleans redundant workflow code and verifies the required parking-ticket workflow.

## Removed / cleaned

- Removed duplicate `GET /api/tickets` route from `backend/app/routers/tickets.py`.
- The remaining `GET /api/tickets` route is authenticated and returns the full ticket workflow payload.
- Added authentication to camera configuration endpoints, sensitive ticket/video endpoints, violation rules, and upload maintenance endpoints.
- `.git`, `.env`, `node_modules`, `__pycache__`, and generated temporary files are excluded from the output ZIP.

## Requirements coverage

1. **System configuration table**
   - `app_config`
   - Fields include:
     - `violation_dwell_seconds`
     - `required_video_seconds`
     - `evidence_video_pre_seconds`
     - `evidence_video_post_seconds`
     - `video_retention_days`
     - `original_video_retention_days`
     - `processed_video_retention_days`
     - `ticket_candidate_retention_days`
     - `video_timestamp_overlay`

2. **Violation types table**
   - `violation_rules`
   - Includes evidence/timing requirements:
     - `default_min_stay_seconds`
     - `default_evidence_video_seconds`
     - `requires_start_image`
     - `requires_end_image`
     - `requires_clear_plate_image`
     - `requires_context_image`
     - `requires_continuous_video`
   - Added `IL-STATIC-016`: `שני גלגלים על המדרכה / Two wheels on sidewalk`.

3. **Inspectors table**
   - `inspectors`

4. **Camera station has section table**
   - `camera_segments`
   - Each segment has:
     - `label`
     - `violation_rule_ids`
     - `x1/y1/x2/y2`
     - `polygon_json`
     - `min_stay_seconds`
     - `evidence_video_seconds`
     - schedule fields

5. **Ticket violation start/end**
   - `tickets.violation_start_at`
   - `tickets.violation_end_at`
   - `tickets.violation_duration_seconds`

6. **Video real-time timestamp overlay**
   - `AppConfig.video_timestamp_overlay`
   - Pipeline uses `clock_start_epoch` and `overlay_timestamp`.

7. **Inspector approval fields**
   - `inspector_violation_rule_id`
   - `inspector_plate`
   - `inspector_vehicle_color`
   - `inspector_vehicle_type`
   - `inspector_vehicle_make`
   - `inspector_vehicle_model`
   - Israeli plate validation requires 7/8 digits.
   - Registry lookup is performed via data.gov.il config in `app_config`.
   - Approval always requires four evidence images:
     - `start_violation_screenshot_id`
     - `end_violation_screenshot_id`
     - `clear_plate_screenshot_id`
     - `violation_context_screenshot_id`

8. **Camera assigned inspector**
   - `cameras.assigned_inspector_id`

9. **Inspector inbox and transfer**
   - `GET /api/tickets/inbox`
   - `PATCH /api/tickets/{ticket_id}/transfer`

10. **Multiple vehicles / subject-car marker**
   - `suspected_vehicle_box`
   - `suspected_vehicle_track_id`
   - `suspected_vehicle_marker_state`
   - Pending = green
   - Approved = red

## Run migration

```bash
cd backend
python migrate_parking_workflow_clean.py
python seed_violation_rules.py
```

## Checks

```bash
cd backend
python -m compileall -q app main.py
```
