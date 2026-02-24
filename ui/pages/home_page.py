from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QScrollArea, QSizePolicy, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


# ── Reusable job card ─────────────────────────────────────────────────────────

class JobCard(QFrame):
    """A single job card displayed in the job list."""

    def __init__(self, job_number: int, parent=None):
        super().__init__(parent)
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
        self.setFixedHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(6)

        # Top row: label + status badge
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.title_label = QLabel(f"Job {job_number}")
        self.title_label.setStyleSheet("color: #e0e0e0; font-size: 11pt; font-weight: 600; background: transparent;")
        top_row.addWidget(self.title_label)

        self.status_badge = QLabel("Queued")
        self.status_badge.setStyleSheet("""
            color: #aaaaaa;
            background-color: #3a3a3a;
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 8pt;
        """)
        self.status_badge.setFixedHeight(18)
        top_row.addWidget(self.status_badge)
        top_row.addStretch()

        root.addLayout(top_row)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setValue(20)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #3a3a3a;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #558B6E;
                border-radius: 3px;
            }
        """)
        root.addWidget(self.progress)


# ── Home page ─────────────────────────────────────────────────────────────────

class HomePage(QWidget):
    """Main job-list page."""

    def __init__(self, switch_callback, parent=None):
        super().__init__(parent)
        self.switch_callback = switch_callback
        self._jobs: list[JobCard] = []

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
        # Hide empty-state placeholder on first card
        if not self._jobs:
            self._jobs_layout.removeWidget(self._empty_label)
            self._empty_label.hide()
            # Remove the stretch spacers too
            for i in reversed(range(self._jobs_layout.count())):
                item = self._jobs_layout.itemAt(i)
                if item and item.spacerItem():
                    self._jobs_layout.removeItem(item)

        card = JobCard(len(self._jobs) + 1)
        self._jobs_layout.addWidget(card)
        self._jobs.append(card)