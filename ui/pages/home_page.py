from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QScrollArea, QSizePolicy, QFrame, QDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.models import TranscodeJob
from ui.dialogs.add_job import AddJobDialog
from core.overseer import JobOverseer
from ui.pages._job_card import JobCard

# ── Home page ─────────────────────────────────────────────────────────────────

class HomePage(QWidget):
    """Main job-list page."""

    def __init__(self, switch_callback, overseer: JobOverseer, parent=None):
        super().__init__(parent)
        self.switch_callback = switch_callback
        self.overseer = overseer # Store reference to the central overseer
        self._job_cards = {}     # Map job name -> JobCard widget
        self._jobs = []          # Store references to created JobCards

        # Connect to overseer signals
        self.overseer.job_status_changed.connect(self._on_job_status_changed)
        self.overseer.work_item_progress.connect(self._on_work_item_progress)
        self.overseer.work_item_status_changed.connect(self._on_work_item_status_changed)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Page header bar ───────────────────────────────────────────────────
        header_bar = QWidget()
        header_bar.setFixedHeight(56)
        header_bar.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #333;")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(16, 0, 16, 0)

        page_title = QLabel("Jobs")
        page_title.setStyleSheet("color: #e0e0e0; font-size: 14pt; font-weight: 700;")
        header_layout.addWidget(page_title)
        header_layout.addStretch()

        self.add_job_btn = QPushButton("＋  Add Job")
        self.add_job_btn.setFixedHeight(32)
        self.add_job_btn.setCursor(Qt.PointingHandCursor)
        self.add_job_btn.setStyleSheet("""
            QPushButton {
                background-color: #558B6E;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 14px;
                font-size: 10pt;
                font-weight: 600;
            }
            QPushButton:hover  { background-color: #67a382; }
            QPushButton:pressed{ background-color: #446e58; }
        """)
        self.add_job_btn.clicked.connect(self._add_job)
        header_layout.addWidget(self.add_job_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(32, 32)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #aaaaaa;
                border: 1px solid #444;
                border-radius: 6px;
                font-size: 14pt;
            }
            QPushButton:hover  { color: #e0e0e0; border-color: #666; }
        """)
        self.settings_btn.clicked.connect(lambda: switch_callback("settings"))
        header_layout.addWidget(self.settings_btn)

        root.addWidget(header_bar)

        # ── Scroll area ───────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background-color: #121212;")
        root.addWidget(scroll)

        canvas = QWidget()
        canvas.setStyleSheet("background-color: #121212;")
        canvas_layout = QHBoxLayout(canvas)
        canvas_layout.setContentsMargins(0, 16, 0, 16)
        scroll.setWidget(canvas)

        # Centre column at 80 % width
        self._jobs_column = QWidget()
        self._jobs_column.setStyleSheet("background: transparent;")
        self._jobs_layout = QVBoxLayout(self._jobs_column)
        self._jobs_layout.setSpacing(10)
        self._jobs_layout.setContentsMargins(0, 0, 0, 0)
        self._jobs_layout.setAlignment(Qt.AlignTop)

        canvas_layout.addStretch(1)
        canvas_layout.addWidget(self._jobs_column, 8)
        canvas_layout.addStretch(1)

        # ── Empty-state label ─────────────────────────────────────────────────
        self._empty_label = QLabel("No jobs yet.\nClick  ＋ Add Job  to get started.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #555; font-size: 11pt;")
        self._jobs_layout.addStretch()
        self._jobs_layout.addWidget(self._empty_label)
        self._jobs_layout.addStretch()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _add_job(self):
        """Triggered by the '+ Add Job' button."""
        dialog = AddJobDialog(self)

        # Execute dialog modally
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 1. Get the compiled job model
            new_job = dialog.get_transcode_job()

            # 2. Hand it off to the backend overseer
            self.overseer.add_job(new_job)

            # 3. Update the UI
            self._hide_empty_state()

            # Create and add the card
            card = JobCard(new_job)
            self._jobs_layout.addWidget(card)
            self._jobs.append(card)

    def _hide_empty_state(self):
        """Helper to clear out the initial placeholder text."""
        if not self._jobs:
            self._empty_label.hide()
            self._jobs_layout.removeWidget(self._empty_label)
            # Remove the stretch spacers
            for i in reversed(range(self._jobs_layout.count())):
                item = self._jobs_layout.itemAt(i)
                if item and item.spacerItem():
                    self._jobs_layout.removeItem(item)

