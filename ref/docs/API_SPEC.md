# API Specification

## POST /analyze-video

Uploads a video for processing.

### Request
multipart/form-data:
- file: video file
- debug: boolean optional
- detector_backend: hsv | yolo optional

### Response
```json
{
  "job_id": "string",
  "status": "queued"
}
```

## GET /jobs/{job_id}

### Response
```json
{
  "job_id": "string",
  "status": "processing | completed | failed",
  "output_video": "path-or-url",
  "result_json": "path-or-url"
}
```

## Result payload shape

```json
{
  "validated_plate": "12345678",
  "registry_match": true,
  "vehicle": {
    "manufacturer": "string",
    "model_name": "string",
    "year": 2020
  },
  "plate_format": {
    "name": "private_long",
    "width_cm": 52.0,
    "height_cm": 12.0
  },
  "curb": {
    "detected": false,
    "distance_px": null,
    "distance_cm": null
  },
  "frames_processed": 240,
  "debug_dir": "debug_output"
}
```
