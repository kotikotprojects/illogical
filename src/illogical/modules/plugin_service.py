from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from logic_plugin_manager import Logic
from PySide6.QtCore import QObject, QThread, Signal

if TYPE_CHECKING:
    from logic_plugin_manager import SearchResult

logger = logging.getLogger(__name__)


class PluginWorker(QObject):
    plugins_loaded = Signal(object)
    search_results = Signal(list)
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._logic: Logic | None = None

    def discover_plugins(self) -> None:
        try:
            self._logic = Logic()
            self.plugins_loaded.emit(self._logic)
        except OSError as e:
            logger.exception("Plugin discovery failed")
            self.error_occurred.emit(str(e))

    def search_plugins(self, query: str) -> None:
        if self._logic is None:
            self.search_results.emit([])
            return

        try:
            results: list[SearchResult] = self._logic.plugins.search(
                query, use_fuzzy=True
            )
            self.search_results.emit(results)
        except OSError as e:
            logger.exception("Plugin search failed")
            self.error_occurred.emit(str(e))


class PluginService(QObject):
    plugins_loaded = Signal(object)
    search_results = Signal(list)
    loading_started = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread = QThread()
        self._worker = PluginWorker()
        self._worker.moveToThread(self._thread)

        self._worker.plugins_loaded.connect(self.plugins_loaded)
        self._worker.search_results.connect(self.search_results)
        self._worker.error_occurred.connect(self.error_occurred)

        self._thread.start()

    def start_discovery(self) -> None:
        self.loading_started.emit()
        self._worker.discover_plugins()

    def search(self, query: str) -> None:
        self._worker.search_plugins(query)

    def shutdown(self) -> None:
        self._thread.quit()
        self._thread.wait()
