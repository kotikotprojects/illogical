from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from illogical.modules.backup_models import (
    BackupInfo,
    BackupTrigger,
    CategoryChange,
    CategoryChangeType,
    ChangeType,
    DetailedBackupChanges,
    FieldChange,
    PluginChange,
)
from illogical.modules.sf_symbols import sf_symbol


class RestoreBackupWindow(QDialog):
    restore_requested = Signal(str)
    backup_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._backups: list[BackupInfo] = []
        self._changes_cache: dict[str, DetailedBackupChanges] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Restore Backup")
        self.resize(700, 500)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._create_backup_list())
        splitter.addWidget(self._create_details_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        layout.addWidget(self._create_buttons())

    def _create_backup_list(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Available Backups"))

        self._backup_list = QListWidget()
        self._backup_list.currentItemChanged.connect(self._on_backup_selected)
        layout.addWidget(self._backup_list)

        return container

    def _create_details_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Details"))

        self._details_label = QLabel("Select a backup to view details")
        self._details_label.setWordWrap(True)
        layout.addWidget(self._details_label)

        layout.addWidget(QLabel("Changes if restored:"))

        self._changes_tree = QTreeWidget()
        self._changes_tree.setHeaderHidden(True)
        self._changes_tree.setIndentation(16)
        layout.addWidget(self._changes_tree, 1)

        return container

    def _create_buttons(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        self._restore_btn = QPushButton("Restore")
        self._restore_btn.setEnabled(False)
        self._restore_btn.clicked.connect(self._on_restore_clicked)
        layout.addWidget(self._restore_btn)

        return container

    def set_backups(self, backups: list[BackupInfo]) -> None:
        self._backups = backups
        self._backup_list.clear()

        for backup in backups:
            item = QListWidgetItem()
            item.setText(backup.display_name)
            item.setData(Qt.ItemDataRole.UserRole, backup.name)

            if backup.trigger == BackupTrigger.MANUAL:
                icon_name = "hand.tap"
            else:
                icon_name = "clock.arrow.circlepath"
            icon = sf_symbol(icon_name, 16)
            if not icon.isNull():
                item.setIcon(icon)

            self._backup_list.addItem(item)

    def _on_backup_selected(self, current: QListWidgetItem | None) -> None:
        if current is None:
            self._restore_btn.setEnabled(False)
            self._details_label.setText("Select a backup to view details")
            self._changes_tree.clear()
            return

        backup_name = current.data(Qt.ItemDataRole.UserRole)
        self._restore_btn.setEnabled(True)

        backup = next((b for b in self._backups if b.name == backup_name), None)
        if backup:
            details = (
                f"Created: {backup.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Files: {backup.file_count}\n"
                f"Size: {backup.size_display}"
            )
            if backup.description:
                details += f"\nNote: {backup.description}"
            self._details_label.setText(details)

        self.backup_selected.emit(backup_name)

    def set_detailed_changes(
        self, backup_name: str, changes: DetailedBackupChanges
    ) -> None:
        self._changes_cache[backup_name] = changes

        current = self._backup_list.currentItem()
        if current and current.data(Qt.ItemDataRole.UserRole) == backup_name:
            self._display_changes(changes)

    def _display_changes(self, changes: DetailedBackupChanges) -> None:
        self._changes_tree.clear()

        if changes.is_empty:
            item = QTreeWidgetItem(["No changes (identical to current)"])
            self._changes_tree.addTopLevelItem(item)
            return

        self._add_category_group(
            changes.categories_added, "Categories to remove", "folder.badge.minus"
        )
        self._add_category_group(
            changes.categories_moved, "Categories to revert", "folder.badge.gearshape"
        )
        self._add_category_group(
            changes.categories_deleted, "Categories to restore", "folder.badge.plus"
        )

        self._add_plugin_group(changes.added, "Plugins to remove", "minus.circle")
        self._add_plugin_group(
            changes.modified, "Plugins to revert", "arrow.uturn.backward.circle"
        )
        self._add_plugin_group(changes.deleted, "Plugins to restore", "plus.circle")

    def _add_plugin_group(
        self, plugins: list[PluginChange], label: str, icon_name: str
    ) -> None:
        if not plugins:
            return

        group_item = QTreeWidgetItem([f"{label} ({len(plugins)})"])
        icon = sf_symbol(icon_name, 14)
        if not icon.isNull():
            group_item.setIcon(0, icon)

        for plugin in sorted(plugins, key=lambda p: p.plugin_name.lower()):
            plugin_item = QTreeWidgetItem(group_item, [plugin.plugin_name])

            if plugin.change_type == ChangeType.MODIFIED and plugin.field_changes:
                for field_change in plugin.field_changes:
                    change_text = self._format_field_change(field_change)
                    QTreeWidgetItem(plugin_item, [change_text])

        self._changes_tree.addTopLevelItem(group_item)
        group_item.setExpanded(True)

    def _add_category_group(
        self, categories: list[CategoryChange], label: str, icon_name: str
    ) -> None:
        if not categories:
            return

        group_item = QTreeWidgetItem([f"{label} ({len(categories)})"])
        icon = sf_symbol(icon_name, 14)
        if not icon.isNull():
            group_item.setIcon(0, icon)

        for cat in sorted(
            categories, key=lambda c: (c.old_path or c.new_path or "").lower()
        ):
            if cat.change_type == CategoryChangeType.MOVED:
                text = f"{cat.new_path} → {cat.old_path}"
            elif cat.change_type == CategoryChangeType.DELETED:
                text = cat.old_path or ""
            else:
                text = cat.new_path or ""
            QTreeWidgetItem(group_item, [text])

        self._changes_tree.addTopLevelItem(group_item)
        group_item.setExpanded(True)

    def _format_field_change(self, change: FieldChange) -> str:
        if change.field_name.startswith("category:"):
            category = change.field_name.split(":", 1)[1]
            if change.new_value == "added":
                return f"+ {category}"
            return f"− {category}"

        current = change.old_value or "(empty)"
        restored = change.new_value or "(empty)"
        return f"{change.field_name}: '{current}' → '{restored}'"

    def _on_restore_clicked(self) -> None:
        current = self._backup_list.currentItem()
        if not current:
            return

        backup_name = current.data(Qt.ItemDataRole.UserRole)
        backup = next((b for b in self._backups if b.name == backup_name), None)
        if not backup:
            return

        ts = backup.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            f"Are you sure you want to restore the backup from {ts}?\n\n"
            "An automatic backup will be created before restoring."
        )
        result = QMessageBox.question(
            self,
            "Restore Backup",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if result == QMessageBox.StandardButton.Yes:
            self.restore_requested.emit(backup_name)
            self.accept()
