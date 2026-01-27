from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from illogical.modules.backup_models import BackupSettings, _format_size

RETENTION_OPTIONS = [(7, "7 days"), (30, "30 days"), (90, "90 days"), (0, "Forever")]


class BackupSettingsWindow(QDialog):
    settings_saved = Signal(object)
    purge_requested = Signal()

    def __init__(self, settings: BackupSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Backup Settings")
        self.setFixedSize(400, 300)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(self._create_retention_group())
        layout.addWidget(self._create_storage_group())
        layout.addStretch()
        layout.addWidget(self._create_buttons())

    def _create_retention_group(self) -> QGroupBox:
        group = QGroupBox("Retention Policy")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        retention_row = QHBoxLayout()
        retention_row.addWidget(QLabel("Keep backups for:"))
        self._retention_combo = QComboBox()
        for _, label in RETENTION_OPTIONS:
            self._retention_combo.addItem(label)
        retention_row.addWidget(self._retention_combo)
        retention_row.addStretch()
        layout.addLayout(retention_row)

        max_row = QHBoxLayout()
        max_row.addWidget(QLabel("Maximum backups:"))
        self._max_spin = QSpinBox()
        self._max_spin.setRange(5, 500)
        self._max_spin.setValue(100)
        max_row.addWidget(self._max_spin)
        max_row.addStretch()
        layout.addLayout(max_row)

        self._auto_purge_check = QCheckBox("Automatically purge old backups")
        layout.addWidget(self._auto_purge_check)

        return group

    def _create_storage_group(self) -> QGroupBox:
        group = QGroupBox("Storage")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        self._storage_label = QLabel("Loading...")
        layout.addWidget(self._storage_label)

        self._purge_button = QPushButton("Purge Old Backups Now")
        self._purge_button.clicked.connect(self._on_purge_clicked)
        layout.addWidget(self._purge_button)

        return group

    def _create_buttons(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        layout.addWidget(save_btn)

        return container

    def _load_settings(self) -> None:
        retention_days = self._settings.retention_days
        for i, (days, _) in enumerate(RETENTION_OPTIONS):
            if days == retention_days:
                self._retention_combo.setCurrentIndex(i)
                break

        self._max_spin.setValue(self._settings.max_backups)
        self._auto_purge_check.setChecked(self._settings.auto_purge)

    def _on_save(self) -> None:
        idx = self._retention_combo.currentIndex()
        retention_days = RETENTION_OPTIONS[idx][0]

        settings = BackupSettings(
            retention_days=retention_days,
            max_backups=self._max_spin.value(),
            auto_purge=self._auto_purge_check.isChecked(),
        )
        self.settings_saved.emit(settings)
        self.accept()

    def _on_purge_clicked(self) -> None:
        self.purge_requested.emit()

    def update_storage_info(self, total_bytes: int, count: int) -> None:
        size_display = _format_size(total_bytes)
        self._storage_label.setText(f"{count} backups using {size_display}")
