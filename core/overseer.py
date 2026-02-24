"""
core.overseer
~~~~~~~~~~~~~
JobOverseer manages all TranscodeJobs and their recurring timers.
It is a QObject so the UI can connect to its signals directly.

Signals
-------
job_status_changed(str, JobStatus)          job name + new status
work_item_progress(str, Path, float)        job name + file + progress 0-100
work_item_status_changed(str, Path, object) job name + file + WorkerStatus
overseer_error(str)                         unrecoverable error message
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from core.models import JobStatus, TranscodeJob, WorkItem, WorkerStatus
from core.scanner import build_output_path, find_pending_files
from core.worker import TranscodeWorker


class JobOverseer(QObject):
    """
    Central controller — create one instance for the whole application.

    Usage:
        overseer = JobOverseer()
        overseer.job_status_changed.connect(my_slot)
        overseer.add_job(my_job)
        # timers fire automatically; call scan_now(job.name) to trigger manually
    """

    # ── Signals ───────────────────────────────────────────────────────────────
    job_status_changed       = Signal(str, object)   # (job_name, JobStatus)
    work_item_progress       = Signal(str, object, float)   # (job_name, Path, pct)
    work_item_status_changed = Signal(str, object, object)  # (job_name, Path, WorkerStatus)
    overseer_error           = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: dict[str, TranscodeJob]        = {}
        self._timers: dict[str, QTimer]            = {}
        self._workers: dict[Path, TranscodeWorker] = {}  # keyed by input_file

    # ── Job management ────────────────────────────────────────────────────────

    def add_job(self, job: TranscodeJob) -> None:
        """Register a job and start its recurring timer."""
        if job.name in self._jobs:
            raise ValueError(f"A job named '{job.name}' already exists.")

        self._jobs[job.name] = job

        timer = QTimer(self)
        timer.setInterval(job.interval_seconds * 1000)
        timer.timeout.connect(lambda: self._on_timer(job.name))
        timer.start()
        self._timers[job.name] = timer

    def remove_job(self, job_name: str) -> None:
        """Stop and remove a job, cancelling any active workers for it."""
        self._stop_timer(job_name)
        self._cancel_workers_for_job(job_name)
        self._jobs.pop(job_name, None)

    def get_jobs(self) -> list[TranscodeJob]:
        return list(self._jobs.values())

    def get_job(self, job_name: str) -> TranscodeJob | None:
        return self._jobs.get(job_name)

    def scan_now(self, job_name: str) -> None:
        """Trigger an immediate scan outside of the normal timer cycle."""
        self._on_timer(job_name)

    # ── Timer callback ────────────────────────────────────────────────────────

    def _on_timer(self, job_name: str) -> None:
        job = self._jobs.get(job_name)
        if job is None:
            return

        # Skip if this job is already actively running workers
        if job.status == JobStatus.RUNNING:
            return

        self._set_job_status(job, JobStatus.SCANNING)

        pending = find_pending_files(
            job.input_folder,
            job.output_folder,
            job.output_extension,
        )

        # Filter out files that already have a live worker
        active_inputs = set(self._workers.keys())
        pending       = [f for f in pending if f not in active_inputs]

        if not pending:
            self._set_job_status(job, JobStatus.IDLE)
            return

        job.pending_files = pending
        self._set_job_status(job, JobStatus.QUEUED)

        for input_file in pending:
            self._start_worker(job, input_file)

    # ── Worker lifecycle ──────────────────────────────────────────────────────

    def _start_worker(self, job: TranscodeJob, input_file: Path) -> None:
        output_file = build_output_path(
            input_file, job.output_folder, job.output_extension
        )
        item   = WorkItem(input_file=input_file, output_file=output_file, job_name=job.name)
        worker = TranscodeWorker(job, item, parent=self)

        # Wire signals — use default-arg capture to avoid closure-over-loop bugs
        worker.progress_changed.connect(
            lambda pct, f=input_file, n=job.name: self.work_item_progress.emit(n, f, pct)
        )
        worker.status_changed.connect(
            lambda status, f=input_file, n=job.name: self._on_worker_status(n, f, status)
        )
        worker.finished.connect(
            lambda f=input_file, n=job.name: self._on_worker_finished(n, f)
        )

        self._workers[input_file] = worker
        self._set_job_status(job, JobStatus.RUNNING)
        worker.start()

    def _on_worker_status(self, job_name: str, input_file: Path, status: WorkerStatus) -> None:
        self.work_item_status_changed.emit(job_name, input_file, status)

    def _on_worker_finished(self, job_name: str, input_file: Path) -> None:
        self._workers.pop(input_file, None)

        job = self._jobs.get(job_name)
        if job is None:
            return

        # If no more workers are active for this job → go back to IDLE
        active_for_job = [
            w for f, w in self._workers.items()
            if self._jobs.get(job_name) and f in (job.pending_files or [])
        ]
        if not active_for_job:
            self._set_job_status(job, JobStatus.IDLE)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_job_status(self, job: TranscodeJob, status: JobStatus) -> None:
        job.status = status
        self.job_status_changed.emit(job.name, status)

    def _stop_timer(self, job_name: str) -> None:
        timer = self._timers.pop(job_name, None)
        if timer:
            timer.stop()
            timer.deleteLater()

    def _cancel_workers_for_job(self, job_name: str) -> None:
        job = self._jobs.get(job_name)
        if job is None:
            return
        for input_file in list(self._workers.keys()):
            if input_file in (job.pending_files or []):
                self._workers[input_file].cancel()