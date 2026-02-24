"""
core.command_builder
~~~~~~~~~~~~~~~~~~~~
Builds ffmpeg CLI commands as plain list[str].

Keeping command construction separate means you can:
  - log / print the exact command before running it
  - paste it straight into a terminal for debugging
  - unit-test flag generation without running any process
"""

from __future__ import annotations

from pathlib import Path

from core.models import TranscodeJob
from core.paths import FFMPEG_BIN


def build_transcode_command(
    job: TranscodeJob,
    input_file: Path,
    output_file: Path,
) -> list[str]:
    """
    Build the full ffmpeg command for transcoding one file.

    The command structure is:
        ffmpeg
          -i <input>
          -nostats               ← suppress human-readable stats on stderr
          -progress pipe:1       ← machine-readable key=value progress on stdout
          <job.extra_flags>      ← codec, filters, bitrate, etc. — verbatim
          -y                     ← overwrite output without prompting
          <output>

    Example output:
        ['/path/to/ffmpeg', '-i', '/rushes/clip.mov',
         '-nostats', '-progress', 'pipe:1',
         '-c:v', 'dnxhd', '-b:v', '36M', '-c:a', 'pcm_s16le',
         '-y', '/proxies/clip.mxf']
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    return [
        str(FFMPEG_BIN),
        "-i", str(input_file),
        "-nostats",
        "-progress", "pipe:1",
        *job.extra_flags,
        "-y",
        str(output_file),
    ]


def build_probe_command(input_file: Path) -> list[str]:
    """
    Convenience — the probe module builds its own command, but this
    lets you log/inspect what would be run without executing it.
    """
    from core.paths import FFPROBE_BIN
    return [
        str(FFPROBE_BIN),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(input_file),
    ]


def command_as_string(cmd: list[str]) -> str:
    """Human-readable version of the command for logging."""
    return " ".join(cmd)