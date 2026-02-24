"""
core.paths
~~~~~~~~~~
Single source of truth for filesystem paths used across the app.
Import these instead of hard-coding strings anywhere else.
"""

from pathlib import Path

# Project root = the directory that contains main.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent

BIN_DIR    = PROJECT_ROOT / "bin"
FFMPEG_BIN = BIN_DIR / "ffmpeg"
FFPROBE_BIN = BIN_DIR / "ffprobe"


def validate_binaries() -> list[str]:
    """
    Return a list of error strings for any missing/non-executable binaries.
    Empty list means all good.

    Call this at startup and show a dialog if errors is non-empty.
    """
    errors: list[str] = []
    for binary in (FFMPEG_BIN, FFPROBE_BIN):
        if not binary.exists():
            errors.append(f"Binary not found: {binary}")
        elif not binary.is_file():
            errors.append(f"Not a file: {binary}")
        elif not binary.stat().st_mode & 0o111:
            errors.append(f"Not executable: {binary}")
    return errors