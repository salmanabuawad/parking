"""Trim source video to 30 seconds. Uses imageio-ffmpeg (bundled ffmpeg)."""
import subprocess
from pathlib import Path

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG = "ffmpeg"

DIR = Path(__file__).parent
SOURCE = DIR / "sample_parking_red_curb.mp4"
OUTPUT = DIR / "sample_parking_30sec.mp4"


def trim(duration_sec: int = 30):
    """Trim SOURCE to first `duration_sec` seconds, save to OUTPUT."""
    if not SOURCE.exists():
        raise FileNotFoundError(f"Source not found: {SOURCE}. Run download_sample.py first.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"Trimming {SOURCE} to {duration_sec}s -> {OUTPUT}")
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-i", str(SOURCE),
            "-t", str(duration_sec),
            "-c", "copy",
            str(OUTPUT),
        ],
        check=True,
        capture_output=True,
    )
    print(f"Done. {OUTPUT}")
    return str(OUTPUT)


if __name__ == "__main__":
    trim(30)
