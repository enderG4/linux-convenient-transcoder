"""
core.config
~~~~~~~~~~~
Persists TranscodeJob definitions to a JSON file in the platform's
standard config directory.

Config location
---------------
  Windows  : %APPDATA%\\AutoTranscoder\\jobs.json
  macOS    : ~/Library/Application Support/AutoTranscoder/jobs.json
  Linux    : ~/.config/AutoTranscoder/jobs.json

Only the fields that describe the job are stored — runtime state
(status, pending_files, error_message) is intentionally excluded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from core.models import TranscodeJob


# ── Config directory ──────────────────────────────────────────────────────────

def _config_dir() -> Path:
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"

    d = base / "AutoTranscoder"
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_DIR = _config_dir()
JOBS_FILE  = CONFIG_DIR / "jobs.json"


# ── Public API ────────────────────────────────────────────────────────────────

def save_jobs(jobs: list[TranscodeJob]) -> None:
    """
    Serialise *jobs* to JOBS_FILE, overwriting any previous data.
    Silently ignores I/O errors so a config issue never crashes the app.
    """
    payload = [_job_to_dict(j) for j in jobs]
    try:
        JOBS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_jobs() -> list[TranscodeJob]:
    """
    Read JOBS_FILE and return a list of TranscodeJob instances.
    Returns an empty list if the file is missing, empty, or malformed.
    """
    if not JOBS_FILE.exists():
        return []
    try:
        payload = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        return [_dict_to_job(d) for d in payload if isinstance(d, dict)]
    except Exception:
        return []


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _job_to_dict(job: TranscodeJob) -> dict:
    return {
        "name":             job.name,
        "input_folder":     str(job.input_folder),
        "output_folder":    str(job.output_folder),
        "output_extension": job.output_extension,
        "extra_flags":      job.extra_flags,
        "interval_seconds": job.interval_seconds,
    }


def _dict_to_job(d: dict) -> TranscodeJob:
    return TranscodeJob(
        name             = d["name"],
        input_folder     = Path(d["input_folder"]),
        output_folder    = Path(d["output_folder"]),
        output_extension = d["output_extension"],
        extra_flags      = d["extra_flags"],
        interval_seconds = int(d.get("interval_seconds", 300)),
    )