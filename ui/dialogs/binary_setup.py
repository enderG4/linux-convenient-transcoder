# ui/dialogs/binary_setup.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
)
from PySide6.QtCore import Qt

from core.downloader import BinaryDownloader


class BinarySetupDialog(QDialog):
    """
    Shown at startup when ffmpeg/ffprobe are missing.
    Downloads the binaries and closes automatically on success.
    The user can close manually if it fails.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setting up binaries")
        self.setMinimumWidth(400)
        self.setFixedHeight(160)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
        )
        self.setStyleSheet("background-color: #1a1a1a; color: #e0e0e0;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._status_lbl = QLabel("Preparing download…")
        self._status_lbl.setStyleSheet("font-size: 10pt; color: #cccccc;")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                background-color: #121212;
                text-align: center;
                height: 20px;
                font-size: 9pt;
            }
            QProgressBar::chunk { background-color: #558B6E; }
        """)
        layout.addWidget(self._bar)

        self._close_btn = QPushButton("Close")
        self._close_btn.setVisible(False)
        self._close_btn.setFixedHeight(32)
        self._close_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 10pt;
            }
            QPushButton:hover { background-color: #666; }
        """)
        self._close_btn.clicked.connect(self.reject)
        layout.addWidget(self._close_btn)

        # Start downloading immediately
        self._downloader = BinaryDownloader(self)
        self._downloader.progress.connect(self._bar.setValue)
        self._downloader.status.connect(self._status_lbl.setText)
        self._downloader.finished.connect(self._on_finished)
        self._downloader.start()

    def _on_finished(self, success: bool):
        if success:
            self.accept()
        else:
            self._status_lbl.setStyleSheet("font-size: 10pt; color: #e74c3c;")
            self._close_btn.setVisible(True)