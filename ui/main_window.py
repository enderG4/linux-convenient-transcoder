from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QStackedWidget, QSizePolicy, QDialog
)
from PySide6.QtCore import Qt

from core import JobOverseer
from core.models import TranscodeJob
from core.config import load_jobs
from core.paths import validate_binaries
from ui.dialogs.binary_setup import BinarySetupDialog
from ui.pages import HomePage, SettingsPage


class _Row(QWidget):
    """A label/value pair for the details panel."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)

        lbl = QLabel(label.upper())
        lbl.setStyleSheet("color: #555; font-size: 8pt; font-weight: 700; letter-spacing: 1px;")
        col.addWidget(lbl)

        self.value = QLabel("—")
        self.value.setStyleSheet("color: #cccccc; font-size: 11pt;")
        self.value.setWordWrap(True)
        col.addWidget(self.value)

    def set(self, text: str):
        self.value.setText(text or "—")


class _SidePanel(QWidget):
    """Right-hand details panel — shows info about the selected job."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1a1a1a;")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 16, 0, 16)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        title = QLabel("DETAILS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color: #666; font-size: 8pt; font-weight: 700; letter-spacing: 2px;"
        )
        root.addWidget(title)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #2e2e2e; margin-top: 8px; margin-bottom: 12px;")
        root.addWidget(sep)

        # ── Stacked: placeholder vs content ───────────────────────────────────
        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        # Page 0 — placeholder
        ph = QLabel("Select a job\nto see details.")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet("color: #444; font-size: 9pt;")
        self._stack.addWidget(ph)

        # Page 1 — job details
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        col = QVBoxLayout(content)
        col.setContentsMargins(16, 0, 16, 0)
        col.setSpacing(14)

        col.addStretch()

        self._r_name      = _Row("Job Name")
        self._r_status    = _Row("Status")
        self._r_input     = _Row("Input Folder")
        self._r_output    = _Row("Output Folder")
        self._r_format    = _Row("Output Format")
        self._r_codec     = _Row("Video Codec")
        self._r_compress  = _Row("Compression")
        self._r_audio     = _Row("Audio")
        self._r_interval  = _Row("Scan Interval")

        for row in (
            self._r_name, self._r_status, self._r_input, self._r_output,
            self._r_format, self._r_codec, self._r_compress, self._r_audio,
            self._r_interval,
        ):
            col.addWidget(row)

            sep = QWidget()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background-color: #2e2e2e;")
            col.addWidget(sep)

        col.addStretch()
        self._stack.addWidget(content)

    # ── Public API ────────────────────────────────────────────────────────────

    def show_job(self, job: TranscodeJob) -> None:
        """Populate the panel with the given job's data."""
        flags = job.extra_flags

        # Video codec — always at index 1 after "-c:v"
        codec = flags[flags.index("-c:v") + 1] if "-c:v" in flags else "—"

        # Compression
        if "-crf" in flags:
            compress = f"CRF {flags[flags.index('-crf') + 1]}"
        elif "-profile:v" in flags:
            compress = f"Profile: {flags[flags.index('-profile:v') + 1]}"
        else:
            compress = "None (remux)"

        # Audio codec — after "-c:a"
        audio = flags[flags.index("-c:a") + 1] if "-c:a" in flags else "—"

        # Interval in human-readable form
        secs = job.interval_seconds
        interval_str = f"{secs} second{'s' if secs != 1 else ''}"

        self._r_name.set(job.name)
        self._r_status.set(job.status.name.capitalize())
        self._r_input.set(str(job.input_folder))
        self._r_output.set(str(job.output_folder))
        self._r_format.set(job.output_extension)
        self._r_codec.set(codec)
        self._r_compress.set(compress)
        self._r_audio.set(audio)
        self._r_interval.set(interval_str)

        self._stack.setCurrentIndex(1)

    def clear(self) -> None:
        """Go back to the placeholder."""
        self._stack.setCurrentIndex(0)


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self):
        super().__init__()

        # ── Binary check — must happen before anything else ───────────────────
        if validate_binaries():
            dialog = BinarySetupDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                # Download failed — show a simple message and the window will
                # open anyway; ffmpeg errors will surface when jobs run.
                pass

        self.overseer = JobOverseer()

        self.setWindowTitle("Auto-Transcoder")
        self.resize(1000, 620)
        self.setMinimumSize(700, 400)
        self.setStyleSheet("background-color: #121212;")
        self.setContentsMargins(0, 0, 0, 0)

        central = QWidget()
        self.setCentralWidget(central)

        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._stack = QStackedWidget()
        self._home_page = HomePage(self._switch_page, self.overseer)
        self._settings_page = SettingsPage(self._switch_page)
        self._stack.addWidget(self._home_page)
        self._stack.addWidget(self._settings_page)
        self._stack.setCurrentWidget(self._home_page)

        self._side_panel = _SidePanel()
        self._side_panel.setFixedWidth(280)

        separator = QWidget()
        separator.setFixedWidth(1)
        separator.setStyleSheet("background-color: #2e2e2e;")

        outer.addWidget(self._stack, 1)
        outer.addWidget(separator)
        outer.addWidget(self._side_panel)

        # ── Wire detail panel signals ─────────────────────────────────────────
        self._home_page.job_selected.connect(self._side_panel.show_job)
        self._home_page.job_deselected.connect(self._side_panel.clear)

        # ── Restore persisted jobs ────────────────────────────────────────────
        self._restore_saved_jobs()

    def _restore_saved_jobs(self) -> None:
        for job in load_jobs():
            try:
                self.overseer.add_job(job)
                self._home_page.restore_job(job)
            except Exception:
                pass

    def _switch_page(self, page_name: str):
        pages = {
            "home":     self._home_page,
            "settings": self._settings_page,
        }
        widget = pages.get(page_name)
        if widget:
            self._stack.setCurrentWidget(widget)