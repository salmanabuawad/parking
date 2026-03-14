"""
Thin CLI for Israeli plate-processing pipeline.
All logic lives in modules; app.py only parses args and invokes run_pipeline.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import PipelineConfig
from .pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Israeli plate-processing: blur except validated target plate")
    parser.add_argument("--input", "-i", required=True, type=Path, help="Input video path")
    parser.add_argument("--output", "-o", required=True, type=Path, help="Output video path")
    parser.add_argument("--debug", action="store_true", help="Save debug frames (plate mask, crop, overlay)")
    parser.add_argument("--max-frames", type=int, default=None, help="Limit frames to process")
    parser.add_argument("--registry-csv", type=Path, default=None, help="Gov.il registry CSV path")
    parser.add_argument(
        "--detector-backend",
        choices=["hsv", "yolo"],
        default="hsv",
        help="Plate detector backend (default: hsv)",
    )
    parser.add_argument("--disable-ocr", action="store_true", help="Skip OCR; output fully blurred only")
    parser.add_argument("--output-json", action="store_true", default=True, help="Write JSON result (default: on)")
    parser.add_argument("--no-output-json", action="store_true", help="Disable JSON result output")

    args = parser.parse_args(argv)
    output_json = args.output_json and not args.no_output_json

    cfg = PipelineConfig(
        input_path=args.input,
        output_path=args.output,
        debug=args.debug,
        max_frames=args.max_frames,
        registry_csv=args.registry_csv,
        detector_backend=args.detector_backend,
        disable_ocr=args.disable_ocr,
        output_json=output_json,
    )

    run_pipeline(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
