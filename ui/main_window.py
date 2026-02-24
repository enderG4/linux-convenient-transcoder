from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QStackedWidget, QFrame
)
from PySide6.QtCore import Qt

from core import JobOverseer
from ui.pages import HomePage, SettingsPage


class _SidePanel(QWidget):
    """Right-hand detail / info panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            background-color: #1a1a1a;
            border-left: 1px solid #2e2e2e;
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(8)

        title = QLabel("Details")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #666; font-size: 10pt; font-weight: 600; letter-spacing: 1px;")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #2e2e2e;")
        layout.addWidget(sep)

        self._placeholder = QLabel("Select a job\nto see details.")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("color: #444; font-size: 9pt;")
        layout.addWidget(self._placeholder)
        layout.addStretch()


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self):
        super().__init__()

        self.overseer = JobOverseer()

        self.setWindowTitle("Auto-Transcoder")
        self.resize(1000, 620)
        self.setMinimumSize(700, 400)
        self.setStyleSheet("background-color: #121212;")

        central = QWidget()
        self.setCentralWidget(central)

        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Page stack (main content)
        self._stack = QStackedWidget()
        self._home_page = HomePage(self._switch_page, self.overseer)
        self._settings_page = SettingsPage(self._switch_page)
        self._stack.addWidget(self._home_page)
        self._stack.addWidget(self._settings_page)
        self._stack.setCurrentWidget(self._home_page)

        # Side panel
        self._side_panel = _SidePanel()

        # 4 : 1  →  ~80 % / ~20 %
        outer.addWidget(self._stack, 4)
        outer.addWidget(self._side_panel, 1)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _switch_page(self, page_name: str):
        pages = {
            "home": self._home_page,
            "settings": self._settings_page,
        }
        widget = pages.get(page_name)
        if widget:
            self._stack.setCurrentWidget(widget)