"""
Evaluate OCR / license-plate detection quality.

Runs the plate engine (the SAME enterprise config the upload worker uses) over a set
of videos and reports:
  - detection rate (got any plate at all)
  - exact-match accuracy        (when ground-truth labels are provided)
  - normalized digit match      (digits-only comparison)
  - mean digit edit-distance    (Levenshtein over digits)

This measures the REAL engine output (no sample-filename shortcuts). Run it before and
after engine changes to see whether OCR/plate detection actually improved.

Run from the backend dir with the venv + .env on the box that has the engine deps
(the dev server):

  # Accuracy vs labels — labels.json: [{"video": "videos/original/job_137.mp4", "expected": "7046676"}, ...]
  python eval_plate_detection.py --labels eval_labels.json

  # Detection-rate only over a folder (no labels needed); --limit to sample N
  python eval_plate_detection.py --dir videos/original --limit 10

  # Single video
  python eval_plate_detection.py --video videos/original/job_137.mp4 --expected 7046676

Results are also written to eval_results.json for run-over-run diffing.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_BACKEND_ROOT = Path(__file__).resolve().parent


def _digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _edit_distance(a: str, b: str) -> int:
    a, b = a or "", b or ""
    dp = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, dp[0] = dp[0], i
        for j, cb in enumerate(b, 1):
            prev, dp[j] = dp[j], min(dp[j] + 1, dp[j - 1] + 1, prev + (ca != cb))
    return dp[-1]


def run_engine(video_path: Path) -> str:
    """Run the enterprise plate pipeline on one video; return the validated plate ('' if none)."""
    from app.plate_pipeline.pipeline import run_pipeline
    from app.plate_pipeline.config import PipelineConfig

    plate_model = _BACKEND_ROOT / "models" / "license_plate_detector.pt"
    out = Path(tempfile.mktemp(suffix=".mp4"))
    try:
        cfg = PipelineConfig(
            input_path=Path(video_path),
            output_path=out,
            blur_kernel_size=3,
            max_frames=150,
            output_json=False,
            detector_backend="enterprise",
            plate_yolo_model_path=str(plate_model) if plate_model.is_file() else "models/license_plate_detector.pt",
            disable_ocr=False,
            ocr_every_n_frames=5,
            enterprise_detection_zoom=1.60,
            enterprise_detection_roi_y_start=0.26,
            anpr_min_votes_stable=1,
        )
        r = run_pipeline(cfg)
        return r.get("validated_plate") or ""
    finally:
        out.unlink(missing_ok=True)


def _resolve(p: str) -> Path:
    pp = Path(p)
    return pp if pp.is_absolute() else (_BACKEND_ROOT / pp)


def main():
    ap = argparse.ArgumentParser(description="Evaluate OCR / plate-detection quality")
    ap.add_argument("--labels", help="JSON list of {video, expected}")
    ap.add_argument("--dir", help="directory of videos (detection-rate only unless labelled)")
    ap.add_argument("--video", help="single video path")
    ap.add_argument("--expected", help="expected plate for --video")
    ap.add_argument("--limit", type=int, default=0, help="process at most N videos (0 = all)")
    args = ap.parse_args()

    items = []  # (video_path, expected|None)
    if args.labels:
        for d in json.loads(_resolve(args.labels).read_text(encoding="utf-8")):
            items.append((d["video"], d.get("expected")))
    elif args.dir:
        for p in sorted(_resolve(args.dir).glob("*.mp4")):
            items.append((str(p), None))
    elif args.video:
        items.append((args.video, args.expected))
    else:
        ap.error("provide --labels, --dir, or --video")

    if args.limit:
        items = items[: args.limit]

    total = len(items)
    detected = exact = norm_match = labeled = dist_sum = 0
    rows = []
    print(f"Evaluating {total} video(s) with the live enterprise engine...\n", flush=True)
    for i, (vid, exp) in enumerate(items, 1):
        vp = _resolve(vid)
        try:
            got = run_engine(vp)
        except Exception as e:
            got = ""
            print(f"[{i}/{total}] {vp.name}: ENGINE ERROR {e}", flush=True)
        got_d = _digits(got)
        has = bool(got_d) and got_d != "11111"
        if has:
            detected += 1
        row = {"video": vp.name, "detected": got_d or None}
        if exp is not None:
            labeled += 1
            exp_d = _digits(exp)
            em = got_d == exp_d and bool(exp_d)
            ed = _edit_distance(got_d, exp_d)
            dist_sum += ed
            if em:
                exact += 1
            row.update({"expected": exp_d, "exact_match": em, "digit_errors": ed})
        rows.append(row)
        print(f"[{i}/{total}] " + json.dumps(row, ensure_ascii=False), flush=True)

    summary = {
        "videos": total,
        "detection_rate": f"{detected}/{total}" + (f" = {100*detected/total:.1f}%" if total else ""),
        "labeled": labeled,
    }
    if labeled:
        summary["exact_match"] = f"{exact}/{labeled} = {100*exact/labeled:.1f}%"
        summary["mean_digit_edit_distance"] = round(dist_sum / labeled, 2)

    print("\n=== SUMMARY ===")
    for k, v in summary.items():
        print(f"{k}: {v}")

    out = _BACKEND_ROOT / "eval_results.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
