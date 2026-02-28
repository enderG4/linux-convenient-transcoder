from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QDialog,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal

from ui.dialogs.add_job import AddJobDialog
from core.overseer import JobOverseer
from core.models import TranscodeJob
from core.config import save_jobs
from ui.pages._job_card import JobCard


class HomePage(QWidget):
    """Main job-list page."""

    job_selected   = Signal(object)   # TranscodeJob
    job_deselected = Signal()

    def __init__(self, switch_callback, overseer: JobOverseer, parent=None):
        super().__init__(parent)
        self.switch_callback = switch_callback
        self.overseer = overseer
        self._job_cards: dict[str, JobCard] = {}   # job name → card
        self._selected_card: JobCard | None = None

        # Connect overseer signals
        self.overseer.job_status_changed.connect(self._on_job_status_changed)
        self.overseer.work_item_duration.connect(self._on_work_item_duration)
        self.overseer.work_item_progress.connect(self._on_work_item_progress)
        self.overseer.work_item_status_changed.connect(self._on_work_item_status_changed)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────────────
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
        self.add_job_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #aaaaaa;
                border: 1px solid #444;
                border-radius: 6px;
                font-size: 14pt;
            }
            QPushButton:hover { color: #e0e0e0; border-color: #666; }
        """)
        self.settings_btn.clicked.connect(lambda: switch_callback("settings"))
        header_layout.addWidget(self.settings_btn)

        root.addWidget(header_bar)

        # ── Scroll area ───────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: #121212;")
        root.addWidget(scroll)

        canvas = QWidget()
        canvas.setStyleSheet("background-color: #121212;")
        canvas_layout = QHBoxLayout(canvas)
        canvas_layout.setContentsMargins(0, 16, 0, 16)
        scroll.setWidget(canvas)

        self._jobs_column = QWidget()
        self._jobs_column.setStyleSheet("background: transparent;")
        self._jobs_layout = QVBoxLayout(self._jobs_column)
        self._jobs_layout.setSpacing(10)
        self._jobs_layout.setContentsMargins(0, 0, 0, 0)
        self._jobs_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        canvas_layout.addStretch(1)
        canvas_layout.addWidget(self._jobs_column, 8)
        canvas_layout.addStretch(1)

        # ── Empty-state label ─────────────────────────────────────────────────
        self._empty_label = QLabel("No jobs yet.\nClick  ＋ Add Job  to get started.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #555; font-size: 11pt;")
        self._jobs_layout.addStretch()
        self._jobs_layout.addWidget(self._empty_label)
        self._jobs_layout.addStretch()

    # ── Public: restore a saved job on startup ────────────────────────────────

    def restore_job(self, job: TranscodeJob) -> None:
        """
        Add a card for an already-registered job without opening the dialog.
        Called by MainWindow during startup for each job loaded from config.
        """
        self._hide_empty_state()
        card = self._create_card(job)
        self._jobs_layout.addWidget(card)

    # ── Add job via dialog ────────────────────────────────────────────────────

    def _add_job(self):
        dialog = AddJobDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_job = dialog.get_transcode_job()
            self.overseer.add_job(new_job)
            self._hide_empty_state()
            card = self._create_card(new_job)
            self._jobs_layout.addWidget(card)
            self._save_config()

    # ── Card factory ──────────────────────────────────────────────────────────

    def _create_card(self, job: TranscodeJob) -> JobCard:
        card = JobCard(job)
        self._job_cards[job.name] = card
        card.card_selected.connect(self._on_card_selected)
        card.card_deselected.connect(self.job_deselected)
        card.run_requested.connect(self._on_run_requested)
        card.stop_requested.connect(self._on_stop_requested)
        card.edit_requested.connect(self._on_edit_requested)
        card.delete_requested.connect(self._on_delete_requested)
        return card

    # ── Empty-state helpers ───────────────────────────────────────────────────

    def _hide_empty_state(self):
        if not self._job_cards:
            self._empty_label.hide()
            self._jobs_layout.removeWidget(self._empty_label)
            for i in reversed(range(self._jobs_layout.count())):
                item = self._jobs_layout.itemAt(i)
                if item and item.spacerItem():
                    self._jobs_layout.removeItem(item)

    def _maybe_show_empty_state(self):
        if not self._job_cards:
            self._jobs_layout.addStretch()
            self._jobs_layout.addWidget(self._empty_label)
            self._jobs_layout.addStretch()
            self._empty_label.show()

    # ── Config persistence ────────────────────────────────────────────────────

    def _save_config(self):
        """Write the current job list to disk."""
        save_jobs([card.job for card in self._job_cards.values()])

    # ── Card signal handlers ──────────────────────────────────────────────────

    def _on_card_selected(self, clicked_card: JobCard):
        if self._selected_card and self._selected_card is not clicked_card:
            self._selected_card.collapse()   # not user-initiated, so no card_deselected
            self.job_deselected.emit()
        self._selected_card = clicked_card
        self.job_selected.emit(clicked_card.job)

    def _on_run_requested(self, job_name: str):
        self.overseer.scan_now(job_name)

    def _on_stop_requested(self, job_name: str):
        self.overseer.stop_job(job_name)

    def _on_edit_requested(self, job_name: str):
        card = self._job_cards.get(job_name)
        if not card:
            return

        # Stop any active workers before editing
        self.overseer.stop_job(job_name)

        dialog = AddJobDialog(self, title="Edit Job")
        dialog.populate_from_job(card.job)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        updated_job = dialog.get_transcode_job()

        # Swap in the overseer — remove old name, add updated
        self.overseer.remove_job(job_name)
        self.overseer.add_job(updated_job)

        # Update the card dict (name may have changed)
        del self._job_cards[job_name]
        card.job = updated_job
        card.refresh_display()
        self._job_cards[updated_job.name] = card

        self._save_config()

    def _on_delete_requested(self, job_name: str):
        reply = QMessageBox.question(
            self,
            "Delete Job",
            f"Remove job  \"{job_name}\"?\n\nAny active transcodes will be stopped.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.overseer.remove_job(job_name)

        card = self._job_cards.pop(job_name, None)
        if card:
            if self._selected_card is card:
                self._selected_card = None
                self.job_deselected.emit()
            self._jobs_layout.removeWidget(card)
            card.deleteLater()

        self._save_config()
        self._maybe_show_empty_state()

    # ── Overseer signal handlers ──────────────────────────────────────────────

    def _on_job_status_changed(self, job_name: str, new_status):
        card = self._job_cards.get(job_name)
        if card:
            card.update_status(new_status)

    def _on_work_item_duration(self, job_name: str, input_file, duration: float):
        card = self._job_cards.get(job_name)
        if card:
            card.set_work_item_duration(input_file, duration)

    def _on_work_item_progress(self, job_name: str, input_file, progress: float):
        card = self._job_cards.get(job_name)
        if card:
            card.update_work_item_progress(input_file, progress)

    def _on_work_item_status_changed(self, job_name: str, input_file, status):
        card = self._job_cards.get(job_name)
        if card:
            card.update_work_item_status(input_file, status)