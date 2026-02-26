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
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from core.command_builder import build_transcode_command
from core.models import TranscodeJob, WorkItem, WorkerStatus
from core.probe import get_duration


class TranscodeWorker(QThread):

    duration_known   = Signal(float)   # emitted once, right after probing
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
            self.duration_known.emit(duration)

            cmd = build_transcode_command(
                self._job,
                self._item.input_file,
                self._item.output_file,
            )
            print(f"[WORKER] Command:\n  {' '.join(cmd)}")

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
            print("[WORKER] Process terminated")
        else:
            print("[WORKER] cancel() — no running process to terminate")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run_ffmpeg(self, cmd: list[str], duration: float):
        print("[WORKER] Launching subprocess...")
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print(f"[WORKER] PID = {self._process.pid}")

        # ── Drain stderr in a background thread to prevent pipe deadlock ──────
        # ffmpeg writes encoding info to stderr. If we only read stdout, the
        # stderr pipe buffer fills up (~64 KB), ffmpeg blocks waiting for it to
        # be consumed, stdout stalls, and this loop hangs indefinitely.
        stderr_lines: list[str] = []

        def _drain_stderr():
            for line in self._process.stderr:
                stripped = line.rstrip()
                if stripped:
                    stderr_lines.append(stripped)

        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

        # ── Read progress from stdout ─────────────────────────────────────────
        progress_line_count = 0
        for line in self._process.stdout:
            line = line.strip()
            if line:
                print(f"[WORKER] stdout: {line}")
            pct = _parse_progress_line(line, duration)
            if pct is not None:
                progress_line_count += 1
                self._item.progress = pct
                self.progress_changed.emit(pct)

        stderr_thread.join()
        self._process.wait()

        print(f"[WORKER] ffmpeg exited with code {self._process.returncode} "
              f"({progress_line_count} progress lines emitted)")

        if stderr_lines:
            print(f"[WORKER] ffmpeg stderr ({len(stderr_lines)} lines):\n"
                  + "\n".join(f"  {l}" for l in stderr_lines))

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
        print("[WORKER] Warning: duration is 0, cannot compute progress")
        return None

    pct = min(seconds / duration * 100.0, 100.0)
    return pct


def _hhmmss_to_seconds(time_str: str) -> float:
    try:
        parts = time_str.split(":")
        h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
        return h * 3600 + m * 60 + s
    except (ValueError, IndexError):
        print(f"[WORKER] Warning: could not parse time string '{time_str}'")
        return 0.0