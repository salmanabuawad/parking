"""Full refresh: delete old sample, download new video, update DB, process, create ticket."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 1. Delete old file to force fresh download
SAMPLE_FILE = Path(__file__).parent / "sample_camera" / "sample_parking_red_curb.mp4"
if SAMPLE_FILE.exists():
    SAMPLE_FILE.unlink()
    print("Deleted old sample file")

# 2. Download fresh from YouTube
from sample_camera.download_sample import download
download()

# 3. Push file to DB (seed_sample_camera)
from seed_sample_camera import seed
seed()

# 4. Delete sample tickets, process video (face blur), create new ticket
from reseed_sample_ticket import reseed
reseed()

print("Refresh complete. Restart backend to clear in-memory caches.")
