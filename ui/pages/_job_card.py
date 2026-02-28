from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QSizePolicy, QLabel, QHBoxLayout,
    QProgressBar, QWidget, QPushButton
)
from PySide6.QtCore import Qt, Signal

from core import TranscodeJob
from core.models import JobStatus


class StatusBadge(QLabel):
    """A colored status indicator badge."""

    def __init__(self, status: JobStatus, parent=None):
        super().__init__(parent)
        self.set_status(status)

    def set_status(self, status: JobStatus):
        status_map = {
            JobStatus.IDLE:     ("Idle",      "#666666"),
            JobStatus.SCANNING: ("Scanning…", "#3d7ec9"),
            JobStatus.QUEUED:   ("Queued",    "#f39c12"),
            JobStatus.RUNNING:  ("Running",   "#27ae60"),
            JobStatus.DONE:     ("Done",      "#558B6E"),
            JobStatus.ERROR:    ("Error",     "#e74c3c"),
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


def _action_button(label: str, color: str, hover: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(28)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {color};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 0 16px;
            font-size: 9pt;
            font-weight: 600;
        }}
        QPushButton:hover   {{ background-color: {hover}; }}
        QPushButton:pressed {{ opacity: 0.8; }}
    """)
    return btn


class JobCard(QFrame):
    """
    Clickable job card. Clicking toggles a compact action bar with
    Run / Stop / Delete buttons.

    Signals
    -------
    card_selected(JobCard)
    run_requested(str)
    stop_requested(str)
    delete_requested(str)
    """

    card_selected    = Signal(object)
    card_deselected  = Signal()
    run_requested    = Signal(str)
    stop_requested   = Signal(str)
    edit_requested   = Signal(str)
    delete_requested = Signal(str)

    _STYLE = """
        QFrame#JobCard {{
            background-color: #2a2a2a;
            border: 1px solid {border};
            border-radius: 8px;
        }}
    """

    def __init__(self, job: TranscodeJob, parent=None):
        super().__init__(parent)
        self.job = job
        self.work_items: dict = {}
        self._expanded = False

        self.setObjectName("JobCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply_style(selected=False)
        self._setup_ui()

    # ── Style ─────────────────────────────────────────────────────────────────

    def _apply_style(self, selected: bool):
        self.setStyleSheet(self._STYLE.format(border="#558B6E" if selected else "#3a3a3a"))

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        # ── Top row ───────────────────────────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(self.job.name)
        self.title_label.setStyleSheet(
            "color: #e0e0e0; font-size: 11pt; font-weight: 600; background: transparent;"
        )
        info_col.addWidget(self.title_label)

        codec_name = self.job.extra_flags[1] if len(self.job.extra_flags) > 1 else "Unknown"
        self.details_label = QLabel(
            f"{codec_name}  •  {self.job.output_extension}  •  "
            f"Input: {self.job.input_folder.name}  →  Output: {self.job.output_folder.name}"
        )
        self.details_label.setStyleSheet("color: #888; font-size: 8pt; background: transparent;")
        self.details_label.setWordWrap(True)
        info_col.addWidget(self.details_label)

        top_row.addLayout(info_col)
        top_row.addStretch()

        self.status_badge = StatusBadge(self.job.status)
        top_row.addWidget(self.status_badge)

        root.addLayout(top_row)

        # ── Progress bar ──────────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                background-color: #1a1a1a;
                text-align: center;
                height: 18px;
            }
            QProgressBar::chunk { background-color: #558B6E; }
        """)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        # ── Work-item info label ──────────────────────────────────────────────
        self.work_item_info = QLabel()
        self.work_item_info.setStyleSheet("color: #999; font-size: 8pt; background: transparent;")
        self.work_item_info.setVisible(False)
        self.work_item_info.setWordWrap(True)
        root.addWidget(self.work_item_info)

        # ── Error label ───────────────────────────────────────────────────────
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #e74c3c; font-size: 8pt; background: transparent;")
        self.error_label.setVisible(False)
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        # ── Action bar (shown on click) ───────────────────────────────────────
        self._action_bar = self._build_action_bar()
        self._action_bar.setVisible(False)
        root.addWidget(self._action_bar)

        self.setMinimumHeight(90)

    def _build_action_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3a3a3a;")
        layout.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._run_btn    = _action_button("▶  Run Now", "#27ae60", "#2ecc71")
        self._stop_btn   = _action_button("■  Stop",    "#c0392b", "#e74c3c")
        self._edit_btn   = _action_button("✎  Edit",    "#2d6a9f", "#3a85c7")
        self._delete_btn = _action_button("🗑  Delete",  "#444444", "#666666")

        self._run_btn.clicked.connect(   lambda: self.run_requested.emit(self.job.name))
        self._stop_btn.clicked.connect(  lambda: self.stop_requested.emit(self.job.name))
        self._edit_btn.clicked.connect(  lambda: self.edit_requested.emit(self.job.name))
        self._delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.job.name))

        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addWidget(self._edit_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._delete_btn)

        layout.addLayout(btn_row)
        return bar

    # ── Click ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._expanded:
                self.collapse(user_initiated=True)
            else:
                self.card_selected.emit(self)
                self.expand()
        super().mousePressEvent(event)

    def expand(self):
        self._expanded = True
        self._action_bar.setVisible(True)
        self._apply_style(selected=True)

    def collapse(self, user_initiated: bool = False):
        self._expanded = False
        self._action_bar.setVisible(False)
        self._apply_style(selected=False)
        if user_initiated:
            self.card_deselected.emit()

    # ── Status / progress (called by HomePage) ────────────────────────────────

    def refresh_display(self):
        """Refresh title and details labels after the job data has been updated."""
        self.title_label.setText(self.job.name)
        codec_name = self.job.extra_flags[1] if len(self.job.extra_flags) > 1 else "Unknown"
        self.details_label.setText(
            f"{codec_name}  •  {self.job.output_extension}  •  "
            f"Input: {self.job.input_folder.name}  →  Output: {self.job.output_folder.name}"
        )

    def update_status(self, new_status: JobStatus):
        self.job.status = new_status
        self.status_badge.set_status(new_status)

        if new_status == JobStatus.RUNNING:
            self.progress_bar.setVisible(True)
            self.work_item_info.setVisible(True)
            self.error_label.setVisible(False)
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

    def set_work_item_duration(self, input_file, duration: float):
        """Store the probed duration for a file so progress can be weighted."""
        if input_file not in self.work_items:
            self.work_items[input_file] = {"progress": 0.0, "status": "running", "duration": duration}
        else:
            self.work_items[input_file]["duration"] = duration

    def update_work_item_progress(self, input_file, progress: float):
        if input_file not in self.work_items:
            self.work_items[input_file] = {"progress": 0.0, "status": "running"}

        self.work_items[input_file]["progress"] = progress

        # Safety net: make sure the progress bar is visible even if the
        # RUNNING status signal hasn't arrived yet (cross-thread race).
        if not self.progress_bar.isVisible():
            self.progress_bar.setVisible(True)
            self.work_item_info.setVisible(True)

        self._update_progress_display()

    def update_work_item_status(self, input_file, status):
        status_str = str(status).upper()

        # Drop completed files immediately so they leave the status text
        if "DONE" in status_str:
            self.work_items.pop(input_file, None)
            self._update_progress_display()
            return

        if input_file not in self.work_items:
            self.work_items[input_file] = {"progress": 0.0, "status": status}
        else:
            self.work_items[input_file]["status"] = status

        self._update_progress_display()

        if "ERROR" in status_str:
            self.error_label.setText(f"Error processing: {input_file.name}")
            self.error_label.setVisible(True)

    def _update_progress_display(self):
        if not self.work_items:
            return

        # Weighted average: each file contributes proportionally to its duration.
        # Falls back to equal weighting for any file whose duration isn't known yet.
        total_duration = sum(i.get("duration", 0.0) for i in self.work_items.values())

        if total_duration > 0:
            weighted = sum(
                i["progress"] / 100.0 * i.get("duration", 0.0)
                for i in self.work_items.values()
            )
            avg = (weighted / total_duration) * 100.0
        else:
            # Durations not known yet — fall back to simple average
            avg = sum(i["progress"] for i in self.work_items.values()) / len(self.work_items)

        self.progress_bar.setValue(int(avg))
        lines = [f"{p.name} ({d['progress']:.0f}%)" for p, d in self.work_items.items()]
        self.work_item_info.setText("Processing: " + ", ".join(lines))

    def clear_work_items(self):
        self.work_items.clear()
        self.progress_bar.setValue(0)
        self.work_item_info.setText("")