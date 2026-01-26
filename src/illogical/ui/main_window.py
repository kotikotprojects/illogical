from __future__ import annotations

from typing import TYPE_CHECKING

import pyqt_liquidglass as glass
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QSplitter, QWidget

from illogical.modules.plugin_service import PluginService
from illogical.ui.loading_overlay import LoadingOverlay
from illogical.ui.plugin_table import PluginTableView
from illogical.ui.sidebar import Sidebar

if TYPE_CHECKING:
    from logic_plugin_manager import Logic, SearchResult
    from PySide6.QtGui import QCloseEvent, QKeyEvent, QShowEvent


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("illogical")
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)

        self._logic: Logic | None = None
        self._glass_applied = False

        self._setup_ui()
        self._setup_service()

        glass.prepare_window_for_glass(self)

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

    def _setup_service(self) -> None:
        self._service = PluginService(self)
        self._service.loading_started.connect(self._on_loading_started)
        self._service.plugins_loaded.connect(self._on_plugins_loaded)
        self._service.search_results.connect(self._on_search_results)
        self._service.error_occurred.connect(self._on_error)

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

    def _on_search_results(self, results: list[SearchResult]) -> None:
        plugins = [r.plugin for r in results]
        self._plugin_table.filter_by_search_results(plugins)

    def _on_error(self, message: str) -> None:
        self._loading_overlay.set_message(f"Error: {message}")

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
        super().closeEvent(event)
