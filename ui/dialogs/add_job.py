# ui/dialogs/add_job.py

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QFileDialog, QSpinBox, QComboBox, QStackedWidget,
    QWidget, QSlider, QLabel, QDialogButtonBox
)
from PySide6.QtCore import Qt

from core.presets import CODEC_PRESETS, AUDIO_PRESETS
from core.models import CodecConfig, CompressionType, TranscodeJob


class AddJobDialog(QDialog):
    def __init__(self, parent=None, title: str = "Add Transcode Job"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(450)
        self.setStyleSheet("background-color: #1a1a1a; color: #e0e0e0;")

        self._build_ui()
        self._populate_codecs()
        self._wire_signals()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        form.addRow("Job Name:", self.name_input)

        in_layout = QHBoxLayout()
        self.in_path_lbl = QLabel("No folder selected")
        in_btn = QPushButton("Browse...")
        in_btn.clicked.connect(self._browse_input)
        in_layout.addWidget(self.in_path_lbl, 1)
        in_layout.addWidget(in_btn)
        form.addRow("Input Folder:", in_layout)

        out_layout = QHBoxLayout()
        self.out_path_lbl = QLabel("No folder selected")
        out_btn = QPushButton("Browse...")
        out_btn.clicked.connect(self._browse_output)
        out_layout.addWidget(self.out_path_lbl, 1)
        out_layout.addWidget(out_btn)
        form.addRow("Output Folder:", out_layout)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setValue(5)
        self.interval_spin.setSuffix(" minutes")
        form.addRow("Scan Interval:", self.interval_spin)

        form.addRow(QLabel("──────────────────────────────────"))

        self.codec_combo = QComboBox()
        form.addRow("Output Codec:", self.codec_combo)

        self.format_combo = QComboBox()
        form.addRow("Output Format:", self.format_combo)

        # Dynamic compression widget
        self.compression_stack = QStackedWidget()

        self.none_widget = QWidget()
        self.compression_stack.addWidget(self.none_widget)   # index 0

        self.crf_widget = QWidget()
        crf_layout = QHBoxLayout(self.crf_widget)
        crf_layout.setContentsMargins(0, 0, 0, 0)
        self.crf_slider = QSlider(Qt.Horizontal)
        self.crf_slider.setRange(0, 51)
        self.crf_slider.setValue(23)
        self.crf_value_lbl = QLabel("23")
        self.crf_slider.valueChanged.connect(lambda v: self.crf_value_lbl.setText(str(v)))
        crf_layout.addWidget(self.crf_slider)
        crf_layout.addWidget(self.crf_value_lbl)
        self.compression_stack.addWidget(self.crf_widget)    # index 1

        self.profile_combo = QComboBox()
        self.compression_stack.addWidget(self.profile_combo) # index 2

        form.addRow("Compression:", self.compression_stack)

        self.audio_combo = QComboBox()
        self.audio_combo.addItems(AUDIO_PRESETS)
        form.addRow("Audio:", self.audio_combo)

        layout.addLayout(form)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _populate_codecs(self):
        for preset in CODEC_PRESETS:
            self.codec_combo.addItem(preset.display_name, userData=preset)
        self._on_codec_changed()

    def _wire_signals(self):
        self.codec_combo.currentIndexChanged.connect(self._on_codec_changed)

    def _on_codec_changed(self):
        preset: CodecConfig = self.codec_combo.currentData()

        self.format_combo.clear()
        self.format_combo.addItems(preset.allowed_formats)
        self.format_combo.setCurrentText(preset.default_format)

        if preset.compression_type == CompressionType.NONE:
            self.compression_stack.setCurrentIndex(0)
        elif preset.compression_type == CompressionType.CRF:
            self.compression_stack.setCurrentIndex(1)
        elif preset.compression_type == CompressionType.PROFILE:
            self.profile_combo.clear()
            self.profile_combo.addItems(preset.profiles)
            self.compression_stack.setCurrentIndex(2)

    # ── Pre-populate for editing ──────────────────────────────────────────────

    def populate_from_job(self, job: TranscodeJob) -> None:
        """
        Fill every field from an existing job so the user can edit it.
        Parses extra_flags back into the UI controls.
        """
        self.name_input.setText(job.name)
        self.in_path_lbl.setText(str(job.input_folder))
        self.out_path_lbl.setText(str(job.output_folder))
        self.interval_spin.setValue(max(1, job.interval_seconds // 60))

        flags = job.extra_flags  # e.g. ["-c:v", "libx264", "-crf", "23", "-c:a", "aac"]

        # ── Codec ─────────────────────────────────────────────────────────────
        ffmpeg_codec = flags[flags.index("-c:v") + 1] if "-c:v" in flags else ""
        for i in range(self.codec_combo.count()):
            preset: CodecConfig = self.codec_combo.itemData(i)
            if preset.ffmpeg_codec == ffmpeg_codec:
                # Block signals so _on_codec_changed doesn't overwrite our
                # profile/CRF values before we set them below.
                self.codec_combo.blockSignals(True)
                self.codec_combo.setCurrentIndex(i)
                self.codec_combo.blockSignals(False)
                # Manually trigger the rest of the codec-changed logic
                self._on_codec_changed()
                break

        # ── Format ────────────────────────────────────────────────────────────
        self.format_combo.setCurrentText(job.output_extension)

        # ── Compression ───────────────────────────────────────────────────────
        if "-crf" in flags:
            try:
                self.crf_slider.setValue(int(flags[flags.index("-crf") + 1]))
            except (ValueError, IndexError):
                pass

        if "-profile:v" in flags:
            try:
                self.profile_combo.setCurrentText(flags[flags.index("-profile:v") + 1])
            except IndexError:
                pass

        # ── Audio ─────────────────────────────────────────────────────────────
        if "-c:a" in flags:
            try:
                self.audio_combo.setCurrentText(flags[flags.index("-c:a") + 1])
            except IndexError:
                pass

    # ── Browse helpers ────────────────────────────────────────────────────────

    def _browse_input(self):
        path = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if path:
            self.in_path_lbl.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.out_path_lbl.setText(path)

    # ── Result ────────────────────────────────────────────────────────────────

    def get_transcode_job(self) -> TranscodeJob:
        preset: CodecConfig = self.codec_combo.currentData()

        extra_flags = ["-c:v", preset.ffmpeg_codec]

        if preset.compression_type == CompressionType.CRF:
            extra_flags.extend(["-crf", str(self.crf_slider.value())])
        elif preset.compression_type == CompressionType.PROFILE:
            extra_flags.extend(["-profile:v", self.profile_combo.currentText()])

        extra_flags.extend(["-c:a", self.audio_combo.currentText()])

        return TranscodeJob(
            name=self.name_input.text() or "Untitled Job",
            input_folder=Path(self.in_path_lbl.text()),
            output_folder=Path(self.out_path_lbl.text()),
            output_extension=self.format_combo.currentText(),
            extra_flags=extra_flags,
            interval_seconds=self.interval_spin.value() * 60,
        )