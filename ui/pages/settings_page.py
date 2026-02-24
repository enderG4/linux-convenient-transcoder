from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt


class SettingsPage(QWidget):
    """Application settings page."""

    def __init__(self, switch_callback, parent=None):
        super().__init__(parent)
        self.switch_callback = switch_callback

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Page header bar ───────────────────────────────────────────────────
        header_bar = QWidget()
        header_bar.setFixedHeight(56)
        header_bar.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #333;")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(16, 0, 16, 0)

        back_btn = QPushButton("← Back")
        back_btn.setFixedHeight(32)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #aaaaaa;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 10pt;
            }
            QPushButton:hover { color: #e0e0e0; border-color: #666; }
        """)
        back_btn.clicked.connect(lambda: switch_callback("home"))
        header_layout.addWidget(back_btn)

        page_title = QLabel("Settings")
        page_title.setAlignment(Qt.AlignCenter)
        page_title.setStyleSheet("color: #e0e0e0; font-size: 14pt; font-weight: 700;")
        header_layout.addWidget(page_title)
        header_layout.addStretch()

        root.addWidget(header_bar)

        # ── Content placeholder ───────────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet("background-color: #121212;")
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignCenter)

        placeholder = QLabel("Settings coming soon…")
        placeholder.setStyleSheet("color: #555; font-size: 11pt;")
        placeholder.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(placeholder)

        root.addWidget(content, 1)