from __future__ import annotations

from typing import TYPE_CHECKING

import pyqt_liquidglass as glass
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QSplitter, QWidget

from illogical.modules import backup_manager
from illogical.modules.backup_models import BackupTrigger
from illogical.modules.backup_service import BackupService
from illogical.modules.models import COL_CUSTOM_NAME, COL_SHORT_NAME
from illogical.modules.plugin_service import PluginService
from illogical.modules.settings import Settings
from illogical.ui.backup_settings_window import BackupSettingsWindow
from illogical.ui.loading_overlay import LoadingOverlay
from illogical.ui.menu_bar import MenuBar
from illogical.ui.plugin_table import PluginTableView
from illogical.ui.restore_backup_window import RestoreBackupWindow
from illogical.ui.sidebar import Sidebar

if TYPE_CHECKING:
    from logic_plugin_manager import AudioComponent, Logic, SearchResult
    from PySide6.QtGui import QCloseEvent, QKeyEvent, QShowEvent

    from illogical.modules.backup_models import (
        BackupInfo,
        BackupSettings,
        DetailedBackupChanges,
    )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("illogical")
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)

        self._logic: Logic | None = None
        self._glass_applied = False
        self._settings = Settings()

        self._setup_ui()
        self._setup_service()
        self._setup_backup_service()
        self._setup_menu_bar()

        glass.prepare_window_for_glass(self)

    def _setup_menu_bar(self) -> None:
        self._menu_bar = MenuBar(self)

        self._menu_bar.backup_now_triggered.connect(self._on_backup_now)
        self._menu_bar.restore_backup_triggered.connect(self._on_restore_backup)
        self._menu_bar.backup_settings_triggered.connect(self._on_backup_settings)

    def _setup_ui(self) -> None:
        self._central = QWidget()
        layout = QHBoxLayout(self._central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        self._sidebar = Sidebar()
        self._plugin_table = PluginTableView()

        self._splitter.addWidget(self._sidebar)
        self._splitter.addWidget(self._plugin_table)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 4)
        self._splitter.setCollapsible(0, False)  # noqa: FBT003
        self._splitter.setCollapsible(1, False)  # noqa: FBT003

        layout.addWidget(self._splitter)

        self.setCentralWidget(self._central)

        self._loading_overlay = LoadingOverlay(self._central)
        self._loading_overlay.hide()

        self._sidebar.category_selected.connect(self._on_category_selected)
        self._sidebar.manufacturer_selected.connect(self._on_manufacturer_selected)
        self._sidebar.enter_pressed.connect(self._plugin_table.focus_table)
        self._plugin_table.search_changed.connect(self._on_search_changed)
        self._plugin_table.plugin_selected.connect(self._on_plugin_selected)
        self._plugin_table.edit_requested.connect(self._on_plugin_edit_requested)

    def _setup_service(self) -> None:
        self._service = PluginService(self)
        self._service.loading_started.connect(self._on_loading_started)
        self._service.plugins_loaded.connect(self._on_plugins_loaded)
        self._service.search_results.connect(self._on_search_results)
        self._service.error_occurred.connect(self._on_error)

    def _setup_backup_service(self) -> None:
        self._backup_service = BackupService(self)
        self._backup_service.backup_created.connect(self._on_backup_created)
        self._backup_service.backup_list_ready.connect(self._on_backup_list_ready)
        self._backup_service.restore_completed.connect(self._on_restore_completed)
        self._backup_service.detailed_changes_computed.connect(
            self._on_detailed_changes_computed
        )
        self._backup_service.storage_usage_ready.connect(self._on_storage_usage_ready)
        self._backup_service.purge_completed.connect(self._on_purge_completed)
        self._backup_service.error_occurred.connect(self._on_backup_error)

        self._restore_window: RestoreBackupWindow | None = None
        self._settings_window: BackupSettingsWindow | None = None

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._glass_applied:
            self._glass_applied = True
            QTimer.singleShot(0, self._apply_glass)
            QTimer.singleShot(100, self._service.start_discovery)

    def _apply_glass(self) -> None:
        glass.setup_traffic_lights_inset(self, x_offset=18, y_offset=12)
        glass.apply_glass_to_widget(self._sidebar, options=glass.GlassOptions.sidebar())
        glass.apply_glass_to_widget(
            self._central, options=glass.GlassOptions(corner_radius=0.0)
        )

    def _on_loading_started(self) -> None:
        self._loading_overlay.set_message("Discovering plugins...")
        self._loading_overlay.show()
        self._loading_overlay.raise_()

    def _on_plugins_loaded(self, logic: Logic) -> None:
        self._logic = logic
        self._backup_service.set_logic(logic)
        self._sidebar.populate(logic)
        self._plugin_table.set_plugins(logic)
        self._loading_overlay.hide()
        self._plugin_table.focus_table()

    def _on_category_selected(self, category: str | None) -> None:
        self._plugin_table.clear_search()
        self._plugin_table.filter_by_category(category)

    def _on_manufacturer_selected(self, manufacturer: str) -> None:
        self._plugin_table.clear_search()
        self._plugin_table.filter_by_manufacturer(manufacturer)

    def _on_search_changed(self, query: str) -> None:
        if not query:
            self._plugin_table.filter_by_category("Show All")
            return
        self._service.search(query)

    def _on_plugin_selected(self, plugin: object) -> None:
        categories = getattr(plugin, "categories", [])
        paths = [c.name for c in categories if c.name]
        if any(c.name == "" for c in categories):
            paths.append("Top Level")
        self._sidebar.highlight_categories(paths)

    def _on_plugin_edit_requested(
        self, plugin: AudioComponent, column: int, new_value: str
    ) -> None:
        try:
            if backup_manager.should_create_auto_backup():
                field = "nickname" if column == COL_CUSTOM_NAME else "shortname"
                description = f"Before setting {field} of {plugin.name}"
                backup_manager.create_backup(BackupTrigger.AUTO, description)

            if column == COL_CUSTOM_NAME:
                self._set_plugin_field(plugin, "nickname", new_value)
            elif column == COL_SHORT_NAME:
                self._set_plugin_field(plugin, "shortname", new_value)

            self._plugin_table.update_plugin_display(plugin, column)
        except OSError as e:
            QMessageBox.warning(self, "Edit Failed", f"Failed to save changes: {e}")

    def _set_plugin_field(self, plugin: AudioComponent, field: str, value: str) -> None:
        tagset = plugin.tagset
        tagset.load()
        raw = tagset._Tagset__raw_data  # type: ignore[attr-defined]  # noqa: SLF001
        if value:
            raw[field] = value
        else:
            raw.pop(field, None)
        tagset._write_plist()  # noqa: SLF001
        tagset.load()

    def _on_search_results(self, results: list[SearchResult]) -> None:
        plugins = [r.plugin for r in results]
        self._plugin_table.filter_by_search_results(plugins)

    def _on_error(self, message: str) -> None:
        self._loading_overlay.set_message(f"Error: {message}")

    def _on_backup_now(self) -> None:
        self._backup_service.create_backup()

    def _on_restore_backup(self) -> None:
        self._restore_window = RestoreBackupWindow(self)
        self._restore_window.backup_selected.connect(self._on_restore_backup_selected)
        self._restore_window.restore_requested.connect(self._on_restore_requested)
        self._backup_service.list_backups()
        self._restore_window.show()

    def _on_backup_settings(self) -> None:
        settings = self._settings.get_backup_settings()
        self._settings_window = BackupSettingsWindow(settings, self)
        self._settings_window.settings_saved.connect(self._on_settings_saved)
        self._settings_window.purge_requested.connect(self._on_purge_requested)
        self._backup_service.get_storage_usage()
        self._settings_window.show()

    def _on_backup_created(self, backup_info: BackupInfo) -> None:
        QMessageBox.information(
            self,
            "Backup Created",
            f"Backup created successfully.\n\n"
            f"Files: {backup_info.file_count}\n"
            f"Size: {backup_info.size_display}",
        )

    def _on_backup_list_ready(self, backups: list[BackupInfo]) -> None:
        if self._restore_window:
            self._restore_window.set_backups(backups)

    def _on_restore_backup_selected(self, backup_name: str) -> None:
        self._backup_service.compute_detailed_changes(backup_name)

    def _on_detailed_changes_computed(
        self, backup_name: str, changes: DetailedBackupChanges
    ) -> None:
        if self._restore_window:
            self._restore_window.set_detailed_changes(backup_name, changes)

    def _on_restore_requested(self, backup_name: str) -> None:
        self._backup_service.restore_backup(backup_name)

    def _on_restore_completed(self, success: bool, backup_name: str) -> None:  # noqa: FBT001
        if success:
            QMessageBox.information(
                self,
                "Restore Complete",
                f"Backup '{backup_name}' has been restored.\n\n"
                "Please restart the application to see the changes.",
            )
        else:
            QMessageBox.warning(
                self, "Restore Failed", f"Failed to restore backup '{backup_name}'."
            )

    def _on_storage_usage_ready(self, total_bytes: int, count: int) -> None:
        if self._settings_window:
            self._settings_window.update_storage_info(total_bytes, count)

    def _on_settings_saved(self, settings: BackupSettings) -> None:
        self._settings.save_backup_settings(settings)
        if settings.auto_purge:
            self._backup_service.purge_old_backups(settings)

    def _on_purge_requested(self) -> None:
        settings = self._settings.get_backup_settings()
        self._backup_service.purge_old_backups(settings)

    def _on_purge_completed(self, deleted_count: int) -> None:
        self._backup_service.get_storage_usage()
        if deleted_count > 0:
            QMessageBox.information(
                self, "Purge Complete", f"Deleted {deleted_count} old backup(s)."
            )

    def _on_backup_error(self, message: str) -> None:
        QMessageBox.warning(self, "Backup Error", message)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        mods = event.modifiers()
        key = event.key()

        if mods == Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_F:
                if self._sidebar.is_manufacturer_mode():
                    self._sidebar.focus_manufacturer_search()
                else:
                    self._plugin_table.focus_search()
                event.accept()
                return
            if key == Qt.Key.Key_1:
                self._reset_to_show_all()
                self._plugin_table.focus_table()
                event.accept()
                return
            if key == Qt.Key.Key_2:
                self._select_uncategorized()
                self._plugin_table.focus_table()
                event.accept()
                return
            if key == Qt.Key.Key_3:
                self._sidebar.focus_category_tree()
                event.accept()
                return
            if key == Qt.Key.Key_4:
                self._sidebar.focus_manufacturer_list()
                event.accept()
                return

        if key == Qt.Key.Key_Escape:
            self._reset_to_show_all()
            event.accept()
            return

        super().keyPressEvent(event)

    def _select_uncategorized(self) -> None:
        self._plugin_table.clear_search()
        self._sidebar.clear_manufacturer_search()
        self._sidebar.select_uncategorized()

    def _reset_to_show_all(self) -> None:
        self._plugin_table.clear_search()
        self._sidebar.clear_manufacturer_search()
        self._sidebar.select_show_all()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._service.shutdown()
        self._backup_service.shutdown()
        super().closeEvent(event)
