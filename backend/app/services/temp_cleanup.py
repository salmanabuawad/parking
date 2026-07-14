"""Best-effort cleanup of leaked temp video renders.

The ANPR pipeline writes multi-MB intermediate .mp4/.avi files via tempfile while rendering
per-car privacy videos. The pipeline now uses TemporaryDirectory / finally cleanup so these
shouldn't leak, but a hard-killed worker (SIGKILL, OOM) can still orphan one mid-render. This
sweeps stale ones on a schedule so the temp filesystem never fills. Files younger than
`max_age_seconds` are left untouched so an in-flight render is never deleted.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

# tempfile's default prefix is "tmp"; mktemp / NamedTemporaryFile video temps are tmp*.mp4 / tmp*.avi.
_PATTERNS = ("tmp*.mp4", "tmp*.avi")
# write_video renders inside a TemporaryDirectory(prefix="anpr_render_"); a SIGKILL/OOM mid-render
# (the one case TemporaryDirectory can't self-clean) can orphan the whole dir.
_DIR_PATTERNS = ("anpr_render_*",)


def _candidate_dirs() -> list[Path]:
    """Temp dirs that may hold leaked renders: the disk-backed one we redirect to, the current
    default temp dir, and (on Linux) the legacy tmpfs /tmp where older strays may still sit."""
    dirs: list[Path] = []
    seen: set[str] = set()

    def _add(p: Path | None) -> None:
        if p is None:
            return
        try:
            rp = p.resolve()
        except OSError:
            return
        if str(rp) not in seen:
            seen.add(str(rp))
            dirs.append(rp)

    try:
        from app.config import settings
        _add(getattr(settings, "videos_tmp_dir", None))
    except Exception:
        pass
    _add(Path(tempfile.gettempdir()))
    if os.name == "posix":
        _add(Path("/tmp"))
    return dirs


def sweep_stale_renders(max_age_seconds: int = 3600) -> dict:
    """Delete leaked tmp*.mp4 / tmp*.avi older than ``max_age_seconds``. Best-effort; never raises.

    Returns ``{"removed": int, "freed_mb": float}``.
    """
    now = time.time()
    removed = 0
    freed = 0
    for d in _candidate_dirs():
        try:
            if not d.is_dir():
                continue
        except OSError:
            continue
        for pattern in _PATTERNS:
            try:
                matches = list(d.glob(pattern))
            except OSError:
                continue
            for f in matches:
                try:
                    if not f.is_file():
                        continue
                    st = f.stat()
                    if now - st.st_mtime < max_age_seconds:
                        continue  # young enough to be an in-flight render — leave it
                    size = st.st_size
                    f.unlink()
                    removed += 1
                    freed += size
                except OSError:
                    continue
        for pattern in _DIR_PATTERNS:
            try:
                dir_matches = list(d.glob(pattern))
            except OSError:
                continue
            for sub in dir_matches:
                try:
                    if not sub.is_dir():
                        continue
                    if now - sub.stat().st_mtime < max_age_seconds:
                        continue  # in-flight render dir — leave it
                    size = sum(p.stat().st_size for p in sub.rglob("*") if p.is_file())
                    shutil.rmtree(sub, ignore_errors=True)
                    if not sub.exists():
                        removed += 1
                        freed += size
                except OSError:
                    continue
    return {"removed": removed, "freed_mb": round(freed / (1024 * 1024), 1)}
