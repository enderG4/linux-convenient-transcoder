"""
core.overseer
~~~~~~~~~~~~~
JobOverseer manages all TranscodeJobs and their recurring timers.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from core.models import JobStatus, TranscodeJob, WorkItem, WorkerStatus
from core.scanner import build_output_path, find_pending_files
from core.worker import TranscodeWorker


class JobOverseer(QObject):

    job_status_changed       = Signal(str, object)
    work_item_duration       = Signal(str, object, float)   # (job_name, Path, seconds)
    work_item_progress       = Signal(str, object, float)
    work_item_status_changed = Signal(str, object, object)
    overseer_error           = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: dict[str, TranscodeJob]        = {}
        self._timers: dict[str, QTimer]            = {}
        self._workers: dict[Path, TranscodeWorker] = {}

    # ── Job management ────────────────────────────────────────────────────────

    def add_job(self, job: TranscodeJob) -> None:
        if job.name in self._jobs:
            raise ValueError(f"A job named '{job.name}' already exists.")
        print(f"[OVERSEER] add_job: '{job.name}' | interval={job.interval_seconds}s "
              f"| input='{job.input_folder}' | output='{job.output_folder}'")
        self._jobs[job.name] = job

        timer = QTimer(self)
        timer.setInterval(job.interval_seconds * 1000)
        timer.timeout.connect(lambda: self._on_timer(job.name))
        timer.start()
        self._timers[job.name] = timer
        print(f"[OVERSEER] Timer started for '{job.name}' (fires every {job.interval_seconds}s)")

    def remove_job(self, job_name: str) -> None:
        print(f"[OVERSEER] remove_job: '{job_name}'")
        self._stop_timer(job_name)
        self._cancel_workers_for_job(job_name)
        self._jobs.pop(job_name, None)

    def stop_job(self, job_name: str) -> None:
        print(f"[OVERSEER] stop_job: '{job_name}'")
        self._cancel_workers_for_job(job_name)
        job = self._jobs.get(job_name)
        if job:
            self._set_job_status(job, JobStatus.IDLE)

    def get_jobs(self) -> list[TranscodeJob]:
        return list(self._jobs.values())

    def get_job(self, job_name: str) -> TranscodeJob | None:
        return self._jobs.get(job_name)

    def scan_now(self, job_name: str) -> None:
        print(f"[OVERSEER] scan_now called for '{job_name}'")
        self._on_timer(job_name)

    # ── Timer callback ────────────────────────────────────────────────────────

    def _on_timer(self, job_name: str) -> None:
        print(f"[OVERSEER] _on_timer fired for '{job_name}'")
        job = self._jobs.get(job_name)
        if job is None:
            print(f"[OVERSEER] _on_timer: job '{job_name}' not found — skipping")
            return

        if job.status == JobStatus.RUNNING:
            print(f"[OVERSEER] _on_timer: '{job_name}' is already RUNNING — skipping")
            return

        self._set_job_status(job, JobStatus.SCANNING)

        print(f"[OVERSEER] Scanning '{job.input_folder}' for files not yet in "
              f"'{job.output_folder}' (ext={job.output_extension})")
        print(f"[OVERSEER] input_folder exists: {job.input_folder.is_dir()}")
        print(f"[OVERSEER] output_folder exists: {job.output_folder.is_dir()}")

        pending = find_pending_files(
            job.input_folder,
            job.output_folder,
            job.output_extension,
        )
        print(f"[OVERSEER] find_pending_files → {len(pending)} file(s): "
              f"{[f.name for f in pending]}")

        active_inputs = set(self._workers.keys())
        before  = len(pending)
        pending = [f for f in pending if f not in active_inputs]
        if before - len(pending):
            print(f"[OVERSEER] Filtered out {before - len(pending)} already-active file(s)")

        if not pending:
            print(f"[OVERSEER] Nothing to do for '{job_name}' — going IDLE")
            self._set_job_status(job, JobStatus.IDLE)
            return

        job.pending_files = pending
        self._set_job_status(job, JobStatus.QUEUED)
        print(f"[OVERSEER] Launching {len(pending)} worker(s) for '{job_name}'")

        for input_file in pending:
            self._start_worker(job, input_file)

    # ── Worker lifecycle ──────────────────────────────────────────────────────

    def _start_worker(self, job: TranscodeJob, input_file: Path) -> None:
        output_file = build_output_path(
            input_file, job.output_folder, job.output_extension
        )
        print(f"[OVERSEER] _start_worker: '{input_file.name}' → '{output_file}'")
        print(f"[OVERSEER] input_file exists: {input_file.exists()}")

        item   = WorkItem(input_file=input_file, output_file=output_file, job_name=job.name)
        worker = TranscodeWorker(job, item, parent=self)

        worker.duration_known.connect(
            lambda secs, f=input_file, n=job.name: self.work_item_duration.emit(n, f, secs)
        )
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
        print(f"[OVERSEER] Calling worker.start() for '{input_file.name}'")
        worker.start()
        print(f"[OVERSEER] worker.start() returned — isRunning={worker.isRunning()}")

    def _on_worker_status(self, job_name: str, input_file: Path, status: WorkerStatus) -> None:
        print(f"[OVERSEER] Worker status: '{input_file.name}' → {status}")
        self.work_item_status_changed.emit(job_name, input_file, status)

    def _on_worker_finished(self, job_name: str, input_file: Path) -> None:
        print(f"[OVERSEER] Worker finished: '{input_file.name}' (job='{job_name}')")
        self._workers.pop(input_file, None)

        job = self._jobs.get(job_name)
        if job is None:
            print(f"[OVERSEER] Job '{job_name}' gone by the time worker finished")
            return

        active_for_job = [f for f in self._workers if f in (job.pending_files or [])]
        print(f"[OVERSEER] Workers still active for '{job_name}': {len(active_for_job)}")
        if not active_for_job:
            self._set_job_status(job, JobStatus.IDLE)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_job_status(self, job: TranscodeJob, status: JobStatus) -> None:
        print(f"[OVERSEER] Status '{job.name}': {job.status.name} → {status.name}")
        job.status = status
        self.job_status_changed.emit(job.name, status)

    def _stop_timer(self, job_name: str) -> None:
        timer = self._timers.pop(job_name, None)
        if timer:
            print(f"[OVERSEER] Stopping timer for '{job_name}'")
            timer.stop()
            timer.deleteLater()
        else:
            print(f"[OVERSEER] _stop_timer: no timer for '{job_name}'")

    def _cancel_workers_for_job(self, job_name: str) -> None:
        job = self._jobs.get(job_name)
        if job is None:
            print(f"[OVERSEER] _cancel_workers_for_job: '{job_name}' not found")
            return
        targets = [f for f in self._workers if f in (job.pending_files or [])]
        print(f"[OVERSEER] Cancelling {len(targets)} worker(s) for '{job_name}'")
        for f in targets:
            self._workers[f].cancel()