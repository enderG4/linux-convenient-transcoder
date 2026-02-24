"""
core.worker
~~~~~~~~~~~
QThread that runs a single ffmpeg transcode and emits signals the UI
can connect to directly.

Signals
-------
progress_changed(float)   0.0 – 100.0 as ffmpeg advances through the file
status_changed(WorkerStatus)
error_occurred(str)       human-readable error message
finished()                emitted when the process exits (success or failure)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from core.command_builder import build_transcode_command
from core.models import TranscodeJob, WorkItem, WorkerStatus
from core.probe import get_duration


class TranscodeWorker(QThread):
    """
    Runs one ffmpeg process in a background thread.

    Usage:
        item   = WorkItem(input_file=..., output_file=..., job_name=...)
        worker = TranscodeWorker(job, item)
        worker.progress_changed.connect(my_progress_bar.setValue)
        worker.finished.connect(on_done)
        worker.start()
    """

    progress_changed = Signal(float)       # 0.0 – 100.0
    status_changed   = Signal(object)      # WorkerStatus enum value
    error_occurred   = Signal(str)
    finished         = Signal()            # always emitted last

    def __init__(self, job: TranscodeJob, item: WorkItem, parent=None):
        super().__init__(parent)
        self._job  = job
        self._item = item
        self._process: subprocess.Popen | None = None

    # ── QThread entry point ───────────────────────────────────────────────────

    def run(self):
        self._item.status = WorkerStatus.RUNNING
        self.status_changed.emit(WorkerStatus.RUNNING)

        try:
            duration = get_duration(self._item.input_file)
            cmd      = build_transcode_command(
                self._job,
                self._item.input_file,
                self._item.output_file,
            )

            self._run_ffmpeg(cmd, duration)

        except Exception as exc:
            self._fail(str(exc))
            return

        self._item.status = WorkerStatus.DONE
        self.status_changed.emit(WorkerStatus.DONE)
        self.finished.emit()

    # ── Cancel from outside ───────────────────────────────────────────────────

    def cancel(self):
        """Terminate the running ffmpeg process (non-blocking)."""
        if self._process and self._process.poll() is None:
            self._process.terminate()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run_ffmpeg(self, cmd: list[str], duration: float):
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,   # -progress pipe:1  →  stdout
            stderr=subprocess.DEVNULL, # suppress normal ffmpeg output
            text=True,
        )

        for line in self._process.stdout:
            line = line.strip()
            pct  = _parse_progress_line(line, duration)
            if pct is not None:
                self._item.progress = pct
                self.progress_changed.emit(pct)

        self._process.wait()

        if self._process.returncode not in (0, 255):
            # 255 = cancelled via terminate(); treat as intentional stop
            raise RuntimeError(
                f"ffmpeg exited with code {self._process.returncode} "
                f"for {self._item.input_file.name}"
            )

    def _fail(self, message: str):
        self._item.status      = WorkerStatus.ERROR
        self._item.error_message = message
        self.status_changed.emit(WorkerStatus.ERROR)
        self.error_occurred.emit(message)
        self.finished.emit()


# ── Progress line parser (pure function — testable in isolation) ───────────────

def _parse_progress_line(line: str, duration: float) -> float | None:
    """
    Parse a single line from ffmpeg's `-progress pipe:1` output.

    Lines look like:
        out_time=00:00:05.916667
        progress=continue
        progress=end

    Returns a percentage float (0–100) when parseable, None otherwise.
    """
    if not line.startswith("out_time="):
        return None

    time_str = line.split("=", 1)[1]  # "00:00:05.916667"
    seconds  = _hhmmss_to_seconds(time_str)

    if duration <= 0:
        return None

    return min(seconds / duration * 100.0, 100.0)


def _hhmmss_to_seconds(time_str: str) -> float:
    """Convert 'HH:MM:SS.ffffff' to total seconds."""
    try:
        parts = time_str.split(":")
        h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
        return h * 3600 + m * 60 + s
    except (ValueError, IndexError):
        return 0.0