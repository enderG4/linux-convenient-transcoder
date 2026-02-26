# ui/dialogs/add_job.py

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QFileDialog, QSpinBox, QComboBox, QStackedWidget,
    QWidget, QSlider, QLabel, QDialogButtonBox
)
from PySide6.QtCore import Qt

from core.presets import CODEC_PRESETS, AUDIO_PRESETS
from core.models import CompressionType, TranscodeJob, CodecConfig


class AddJobDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Transcode Job")
        self.setMinimumWidth(450)
        self.setStyleSheet("background-color: #1a1a1a; color: #e0e0e0;")

        self._build_ui()
        self._populate_codecs()
        self._wire_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Form Layout for standard inputs
        form = QFormLayout()

        self.name_input = QLineEdit()
        form.addRow("Job Name:", self.name_input)

        # Input Folder
        in_layout = QHBoxLayout()
        self.in_path_lbl = QLabel("No folder selected")
        in_btn = QPushButton("Browse...")
        in_btn.clicked.connect(self._browse_input)
        in_layout.addWidget(self.in_path_lbl, 1)
        in_layout.addWidget(in_btn)
        form.addRow("Input Folder:", in_layout)

        # Output Folder
        out_layout = QHBoxLayout()
        self.out_path_lbl = QLabel("No folder selected")
        out_btn = QPushButton("Browse...")
        out_btn.clicked.connect(self._browse_output)
        out_layout.addWidget(self.out_path_lbl, 1)
        out_layout.addWidget(out_btn)
        form.addRow("Output Folder:", out_layout)

        # Interval
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setValue(5)
        self.interval_spin.setSuffix(" minutes")
        form.addRow("Scan Interval:", self.interval_spin)

        # Divider
        form.addRow(QLabel("──────────────────────────────────"))

        # Encoding Settings
        self.codec_combo = QComboBox()
        form.addRow("Output Codec:", self.codec_combo)

        self.format_combo = QComboBox()
        form.addRow("Output Format:", self.format_combo)

        # Dynamic Compression Widget
        self.compression_stack = QStackedWidget()

        # 0: Empty/None
        self.none_widget = QWidget()
        self.compression_stack.addWidget(self.none_widget)

        # 1: CRF Slider
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
        self.compression_stack.addWidget(self.crf_widget)

        # 2: Profile Dropdown
        self.profile_combo = QComboBox()
        self.compression_stack.addWidget(self.profile_combo)

        form.addRow("Compression:", self.compression_stack)

        # Audio
        self.audio_combo = QComboBox()
        self.audio_combo.addItems(AUDIO_PRESETS)
        form.addRow("Audio:", self.audio_combo)

        layout.addLayout(form)

        # Dialog Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _populate_codecs(self):
        for preset in CODEC_PRESETS:
            self.codec_combo.addItem(preset.display_name, userData=preset)
        self._on_codec_changed()  # Trigger initial setup

    def _wire_signals(self):
        self.codec_combo.currentIndexChanged.connect(self._on_codec_changed)

    def _on_codec_changed(self):
        preset: CodecConfig = self.codec_combo.currentData()

        # Update Formats
        self.format_combo.clear()
        self.format_combo.addItems(preset.allowed_formats)
        self.format_combo.setCurrentText(preset.default_format)

        # Swap Compression Widget
        if preset.compression_type == CompressionType.NONE:
            self.compression_stack.setCurrentIndex(0)
        elif preset.compression_type == CompressionType.CRF:
            self.compression_stack.setCurrentIndex(1)
        elif preset.compression_type == CompressionType.PROFILE:
            self.profile_combo.clear()
            self.profile_combo.addItems(preset.profiles)
            self.compression_stack.setCurrentIndex(2)

    def _browse_input(self):
        path = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if path:
            self.in_path_lbl.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.out_path_lbl.setText(path)

    def get_transcode_job(self) -> TranscodeJob:
        """Constructs the TranscodeJob model from the dialog inputs."""
        preset: CodecConfig = self.codec_combo.currentData()

        # Build raw ffmpeg flags
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
            interval_seconds=self.interval_spin.value() * 60
        )