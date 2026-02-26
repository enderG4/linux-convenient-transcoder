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

    progress_changed = Signal(float)
    status_changed   = Signal(object)
    error_occurred   = Signal(str)
    finished         = Signal()

    def __init__(self, job: TranscodeJob, item: WorkItem, parent=None):
        super().__init__(parent)
        self._job  = job
        self._item = item
        self._process: subprocess.Popen | None = None
        print(f"[WORKER] Created for '{item.input_file.name}' → '{item.output_file.name}'")

    # ── QThread entry point ───────────────────────────────────────────────────

    def run(self):
        print(f"[WORKER] Thread started for '{self._item.input_file.name}'")
        self._item.status = WorkerStatus.RUNNING
        self.status_changed.emit(WorkerStatus.RUNNING)

        try:
            print(f"[WORKER] Probing duration of '{self._item.input_file}'")
            duration = get_duration(self._item.input_file)
            print(f"[WORKER] Duration = {duration:.2f}s")

            cmd = build_transcode_command(
                self._job,
                self._item.input_file,
                self._item.output_file,
            )
            print(f"[WORKER] Command: {' '.join(cmd)}")

            self._run_ffmpeg(cmd, duration)

        except Exception as exc:
            print(f"[WORKER] ❌ Exception in run(): {exc}")
            self._fail(str(exc))
            return

        print(f"[WORKER] ✅ Done: '{self._item.input_file.name}'")
        self._item.status = WorkerStatus.DONE
        self.status_changed.emit(WorkerStatus.DONE)
        self.finished.emit()

    # ── Cancel ────────────────────────────────────────────────────────────────

    def cancel(self):
        print(f"[WORKER] cancel() called for '{self._item.input_file.name}'")
        if self._process and self._process.poll() is None:
            self._process.terminate()
            print(f"[WORKER] Process terminated")
        else:
            print(f"[WORKER] cancel() — no running process to terminate")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run_ffmpeg(self, cmd: list[str], duration: float):
        print(f"[WORKER] Launching subprocess...")
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,   # capture stderr so we can log errors
            text=True,
        )
        print(f"[WORKER] PID = {self._process.pid}")

        progress_line_count = 0
        for line in self._process.stdout:
            line = line.strip()
            if line:
                print(f"[WORKER] ffmpeg stdout: {line}")
            pct = _parse_progress_line(line, duration)
            if pct is not None:
                progress_line_count += 1
                self._item.progress = pct
                self.progress_changed.emit(pct)

        # Drain stderr so the process doesn't deadlock and we can log it
        stderr_output = self._process.stderr.read()
        if stderr_output.strip():
            print(f"[WORKER] ffmpeg stderr:\n{stderr_output.strip()}")

        self._process.wait()
        print(f"[WORKER] ffmpeg exited with code {self._process.returncode} "
              f"({progress_line_count} progress lines seen)")

        if self._process.returncode not in (0, 255):
            raise RuntimeError(
                f"ffmpeg exited with code {self._process.returncode} "
                f"for {self._item.input_file.name}"
            )

    def _fail(self, message: str):
        print(f"[WORKER] _fail(): {message}")
        self._item.status        = WorkerStatus.ERROR
        self._item.error_message = message
        self.status_changed.emit(WorkerStatus.ERROR)
        self.error_occurred.emit(message)
        self.finished.emit()


# ── Progress line parser ───────────────────────────────────────────────────────

def _parse_progress_line(line: str, duration: float) -> float | None:
    if not line.startswith("out_time="):
        return None

    time_str = line.split("=", 1)[1]
    seconds  = _hhmmss_to_seconds(time_str)

    if duration <= 0:
        print(f"[WORKER] Warning: duration is 0, cannot compute progress")
        return None

    return min(seconds / duration * 100.0, 100.0)


def _hhmmss_to_seconds(time_str: str) -> float:
    try:
        parts = time_str.split(":")
        h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
        return h * 3600 + m * 60 + s
    except (ValueError, IndexError):
        print(f"[WORKER] Warning: could not parse time string '{time_str}'")
        return 0.0