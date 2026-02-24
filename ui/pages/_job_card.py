from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QSizePolicy, QLabel, QHBoxLayout,
    QProgressBar, QWidget
)
from PySide6.QtGui import QColor

from core import TranscodeJob
from core.models import JobStatus


class StatusBadge(QLabel):
    """A colored status indicator badge."""

    def __init__(self, status: JobStatus, parent=None):
        super().__init__(parent)
        self.set_status(status)

    def set_status(self, status: JobStatus):
        """Update the badge with the given status."""
        status_map = {
            JobStatus.IDLE: ("Idle", "#666666"),
            JobStatus.SCANNING: ("Scanning...", "#3d7ec9"),
            JobStatus.QUEUED: ("Queued", "#f39c12"),
            JobStatus.RUNNING: ("Running", "#27ae60"),
            JobStatus.DONE: ("Done", "#558B6E"),
            JobStatus.ERROR: ("Error", "#e74c3c"),
        }

        text, color = status_map.get(status, ("Unknown", "#888888"))
        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 8pt;
                font-weight: 600;
            }}
        """)


class JobCard(QFrame):
    """A single job card displayed in the job list with comprehensive information and progress tracking."""

    def __init__(self, job: TranscodeJob, parent=None):
        super().__init__(parent)
        self.job = job
        self.work_items = {}  # Track work item progress by input_file Path
        self.setObjectName("JobCard")
        self.setStyleSheet("""
            QFrame#JobCard {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
            QFrame#JobCard:hover {
                border: 1px solid #558B6E;
            }
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._setup_ui()

    def _setup_ui(self):
        """Build the card UI."""
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        # ── Top row: title, details, status badge, buttons ────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        # Job name and codec/format details
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(self.job.name)
        self.title_label.setStyleSheet(
            "color: #e0e0e0; font-size: 11pt; font-weight: 600; background: transparent;"
        )
        info_layout.addWidget(self.title_label)

        # Extract codec name (usually at index 1 in extra_flags)
        codec_name = self.job.extra_flags[1] if len(self.job.extra_flags) > 1 else "Unknown"
        self.details_label = QLabel(
            f"{codec_name} • {self.job.output_extension} • "
            f"Input: {self.job.input_folder.name} → Output: {self.job.output_folder.name}"
        )
        self.details_label.setStyleSheet("color: #888; font-size: 8pt; background: transparent;")
        self.details_label.setWordWrap(True)
        info_layout.addWidget(self.details_label)

        top_row.addLayout(info_layout)
        top_row.addStretch()

        # Status badge
        self.status_badge = StatusBadge(self.job.status)
        top_row.addWidget(self.status_badge)

        root.addLayout(top_row)

        # ── Progress bar (hidden by default) ───────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                background-color: #1a1a1a;
                text-align: center;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #558B6E;
            }
        """)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        # ── Work items info (shows what file is being processed) ───────────────
        self.work_item_info = QLabel()
        self.work_item_info.setStyleSheet("color: #999; font-size: 8pt; background: transparent;")
        self.work_item_info.setVisible(False)
        self.work_item_info.setWordWrap(True)
        root.addWidget(self.work_item_info)

        # ── Error message (shown when status is ERROR) ────────────────────────
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #e74c3c; font-size: 8pt; background: transparent;")
        self.error_label.setVisible(False)
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        self.setMinimumHeight(90)

    def update_status(self, new_status: JobStatus):
        """Called when the job status changes."""
        self.job.status = new_status
        self.status_badge.set_status(new_status)

        # Show/hide progress bar based on status
        if new_status == JobStatus.RUNNING:
            self.progress_bar.setVisible(True)
            self.work_item_info.setVisible(True)
        elif new_status == JobStatus.ERROR:
            self.progress_bar.setVisible(False)
            self.work_item_info.setVisible(False)
            if self.job.error_message:
                self.error_label.setText(f"Error: {self.job.error_message}")
                self.error_label.setVisible(True)
        else:
            self.progress_bar.setVisible(False)
            self.work_item_info.setVisible(False)
            self.error_label.setVisible(False)

    def update_work_item_progress(self, input_file, progress: float):
        """Called when a work item's progress updates."""
        if input_file not in self.work_items:
            self.work_items[input_file] = {"progress": 0, "status": "pending"}

        self.work_items[input_file]["progress"] = progress
        self._update_progress_display()

    def update_work_item_status(self, input_file, status):
        """Called when a work item's status changes."""
        if input_file not in self.work_items:
            self.work_items[input_file] = {"progress": 0, "status": status}
        else:
            self.work_items[input_file]["status"] = status

        self._update_progress_display()

        # If any item errors, mark the job as having an error
        if str(status).upper() == "ERROR":
            self.error_label.setText(f"Error processing: {input_file.name}")
            self.error_label.setVisible(True)

    def _update_progress_display(self):
        """Update the progress bar and info label based on all work items."""
        if not self.work_items:
            return

        # Calculate average progress
        total_progress = sum(item["progress"] for item in self.work_items.values())
        avg_progress = int(total_progress / len(self.work_items))
        self.progress_bar.setValue(avg_progress)

        # Update info label showing current file(s)
        current_files = []
        for file_path, item_info in self.work_items.items():
            current_files.append(f"{file_path.name} ({item_info['progress']:.0f}%)")

        if current_files:
            self.work_item_info.setText(f"Processing: {', '.join(current_files)}")

    def clear_work_items(self):
        """Clear the work items tracking."""
        self.work_items.clear()
        self.progress_bar.setValue(0)
        self.work_item_info.setText("")
