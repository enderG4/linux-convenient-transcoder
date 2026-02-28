"""
core.downloader
~~~~~~~~~~~~~~~
QThread that downloads the ffmpeg and ffprobe binaries if they are missing.

Signals
-------
progress(int)        0–100 overall percentage across both files
status(str)          human-readable status line
finished(bool)       True = success, False = failure
"""

from __future__ import annotations

import stat
import sys
import urllib.request
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from core.paths import BIN_DIR, FFMPEG_BIN, FFPROBE_BIN

BASE_URL = "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1"

def _platform_suffix() -> str:
    if sys.platform == "win32":
        return "win32-x64"
    return "linux-x64"


def _remote_urls() -> list[tuple[str, Path]]:
    """Return [(download_url, local_path), ...] for each binary that is missing."""
    suffix = _platform_suffix()
    pairs = [
        (f"{BASE_URL}/ffmpeg-{suffix}",  FFMPEG_BIN),
        (f"{BASE_URL}/ffprobe-{suffix}", FFPROBE_BIN),
    ]
    return [(url, path) for url, path in pairs if not path.exists()]


class BinaryDownloader(QThread):

    progress = Signal(int)   # 0–100 overall
    status   = Signal(str)
    finished = Signal(bool)  # True = all good, False = error

    def run(self):
        BIN_DIR.mkdir(parents=True, exist_ok=True)

        pairs = _remote_urls()
        if not pairs:
            self.progress.emit(100)
            self.finished.emit(True)
            return

        total = len(pairs)

        for idx, (url, dest) in enumerate(pairs):
            self.status.emit(f"Downloading {dest.name}…")
            print(f"[DOWNLOADER] {url} → {dest}")

            try:
                base_pct = int(idx / total * 100)
                chunk_size = 1024 * 64  # 64 KB

                req = urllib.request.urlopen(url, timeout=60)
                content_length = req.headers.get("Content-Length")
                file_size = int(content_length) if content_length else 0

                downloaded = 0
                with open(dest, "wb") as f:
                    while True:
                        chunk = req.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if file_size:
                            file_pct = downloaded / file_size / total * 100
                            self.progress.emit(int(base_pct + file_pct))

                # Make executable
                dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                print(f"[DOWNLOADER] ✅ {dest.name} ready")

            except Exception as exc:
                print(f"[DOWNLOADER] ❌ Failed: {exc}")
                # Clean up partial download
                if dest.exists():
                    dest.unlink()
                self.status.emit(f"Failed to download {dest.name}: {exc}")
                self.finished.emit(False)
                return

        self.progress.emit(100)
        self.status.emit("Binaries ready.")
        self.finished.emit(True)