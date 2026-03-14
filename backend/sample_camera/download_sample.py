"""Download sample parking violation video (car on red/white curb)."""
import subprocess
import urllib.request
from pathlib import Path

# Primary: YouTube sample (parking/violation video)
YOUTUBE_URL = "https://www.youtube.com/shorts/ch26rQtTjQ8"
# Fallback: ABC7 News parking story
ABC7_URL = "https://abc7news.com/post/parking-in-san-francisco-red-zone-sf-ticket-street-pay-ticketsf/12072574/"

# Fallback: generic samples if yt-dlp fails
FALLBACK_URLS = [
    "https://www.w3schools.com/html/mov_bbb.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
]
OUTPUT = Path(__file__).parent / "sample_parking_red_curb.mp4"

OPENER = urllib.request.build_opener()
OPENER.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")]
urllib.request.install_opener(OPENER)


def download():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading sample video to {OUTPUT} ...")

    # Try yt-dlp first (YouTube, ABC7, etc.)
    for url in [YOUTUBE_URL, ABC7_URL]:
        try:
            subprocess.run(
                ["python", "-m", "yt_dlp", "-o", str(OUTPUT), "-f", "best", url],
                check=True,
                capture_output=True,
            )
            print(f"Done. Saved to {OUTPUT}")
            return str(OUTPUT)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"yt-dlp failed for {url[:50]}...: {e}")

    for url in FALLBACK_URLS:
        try:
            urllib.request.urlretrieve(url, OUTPUT)
            print(f"Done (fallback). Saved to {OUTPUT}")
            return str(OUTPUT)
        except Exception as e:
            print(f"  {url} failed: {e}")
    raise RuntimeError("All download sources failed. Install yt-dlp: pip install yt-dlp")


if __name__ == "__main__":
    download()
