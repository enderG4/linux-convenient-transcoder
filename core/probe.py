"""
core.probe
~~~~~~~~~~
Thin wrapper around the ffprobe CLI.
Returns structured ProbeResult dataclasses — no Qt, no side effects.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from core.models import ProbeResult
from core.paths import FFPROBE_BIN


# ── Public API ────────────────────────────────────────────────────────────────

def probe(file: Path) -> ProbeResult:
    """
    Run ffprobe on *file* and return a ProbeResult.

    Raises:
        FileNotFoundError  – if the input file does not exist
        RuntimeError       – if ffprobe exits with a non-zero code
    """
    if not file.exists():
        raise FileNotFoundError(f"Input file not found: {file}")

    raw = _run_ffprobe(file)
    return _parse(file, raw)


def get_duration(file: Path) -> float:
    """
    Convenience shortcut — returns duration in seconds only.
    Returns 0.0 if the duration cannot be determined.
    """
    try:
        return probe(file).duration_seconds
    except Exception:
        return 0.0


# ── Internal helpers ──────────────────────────────────────────────────────────

def _run_ffprobe(file: Path) -> dict:
    """Execute ffprobe and return parsed JSON output."""
    cmd = [
        str(FFPROBE_BIN),
        "-v", "quiet",            # suppress banner
        "-print_format", "json",  # machine-readable output
        "-show_format",           # duration, bitrate, etc.
        "-show_streams",          # per-stream codec info
        str(file),
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed on {file.name}:\n{result.stderr.strip()}"
        )

    return json.loads(result.stdout)


def _parse(file: Path, data: dict) -> ProbeResult:
    """Extract the fields we care about from raw ffprobe JSON."""
    fmt = data.get("format", {})
    streams = data.get("streams", [])

    duration = float(fmt.get("duration", 0.0))

    # Pull the first video stream and first audio stream
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

    # Parse framerate — stored as a fraction string like "24000/1001"
    fps = _parse_fraction(video_stream.get("r_frame_rate", "0/1"))

    return ProbeResult(
        path=file,
        duration_seconds=duration,
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        video_codec=video_stream.get("codec_name", ""),
        audio_codec=audio_stream.get("codec_name", ""),
        fps=fps,
    )


def _parse_fraction(frac: str) -> float:
    """Convert a fraction string like '24000/1001' to a float."""
    try:
        num, den = frac.split("/")
        return float(num) / float(den) if float(den) != 0 else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0