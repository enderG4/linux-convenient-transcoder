"""
core.models
~~~~~~~~~~~
Pure dataclasses — no Qt, no I/O.
These travel freely between core and ui.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


# ── Enums ─────────────────────────────────────────────────────────────────────

class JobStatus(Enum):
    IDLE       = auto()  # waiting for its next timer tick
    SCANNING   = auto()  # overseer is diffing folders
    QUEUED     = auto()  # files found, workers not yet started
    RUNNING    = auto()  # at least one worker is active
    ERROR      = auto()  # something went wrong
    DONE       = auto()  # all pending files processed this cycle


class WorkerStatus(Enum):
    PENDING  = auto()
    RUNNING  = auto()
    DONE     = auto()
    ERROR    = auto()


# ── Probe result (returned by core.probe) ─────────────────────────────────────

@dataclass
class ProbeResult:
    """Metadata extracted from a media file via ffprobe."""
    path: Path
    duration_seconds: float        # 0.0 if unknown
    width: int  = 0
    height: int = 0
    video_codec: str = ""
    audio_codec: str = ""
    fps: float = 0.0


# ── Transcode job ─────────────────────────────────────────────────────────────

@dataclass
class TranscodeJob:
    """
    Everything needed to describe one recurring watch-folder job.
    The `extra_flags` list is passed verbatim to ffmpeg between
    the input file and the output file, e.g.:

        ["-c:v", "dnxhd", "-vf", "scale=1920:1080", "-b:v", "36M", "-c:a", "pcm_s16le"]
    """
    name: str
    input_folder: Path
    output_folder: Path
    output_extension: str          # e.g. ".mov", ".mp4"
    extra_flags: list[str]         # raw ffmpeg flags
    interval_seconds: int = 300    # how often the overseer scans (default 5 min)

    # Runtime state — not persisted, managed by overseer
    status: JobStatus = field(default=JobStatus.IDLE, compare=False)
    pending_files: list[Path] = field(default_factory=list, compare=False)
    error_message: str = field(default="", compare=False)


# ── Per-file worker descriptor ────────────────────────────────────────────────

@dataclass
class WorkItem:
    """
    Represents a single file being transcoded.
    The overseer creates these; the UI can display them inside a JobCard.
    """
    input_file: Path
    output_file: Path
    job_name: str
    status: WorkerStatus = WorkerStatus.PENDING
    progress: float = 0.0          # 0.0 – 100.0
    error_message: str = ""