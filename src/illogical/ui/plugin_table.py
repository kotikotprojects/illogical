from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from illogical.modules.models import (
    COL_CUSTOM_NAME,
    COL_MANUFACTURER,
    COL_NAME,
    COL_SHORT_NAME,
    COL_TYPE,
    COL_VERSION,
    PluginTableModel,
)
from illogical.ui.search_bar import SearchBar

if TYPE_CHECKING:
    from logic_plugin_manager import AudioComponent, Logic
    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QKeyEvent, QResizeEvent


KVK_J = 0x26
KVK_K = 0x28


class _VimTableView(QTableView):
    def _select_row(self, row: int) -> None:
        index = self.model().index(row, 0)
        self.selectionModel().setCurrentIndex(
            index,
            self.selectionModel().SelectionFlag.ClearAndSelect
            | self.selectionModel().SelectionFlag.Rows,
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        vk = event.nativeVirtualKey()
        key = event.key()

        if vk == KVK_J or key == Qt.Key.Key_Down:
            current = self.currentIndex()
            if current.row() < self.model().rowCount() - 1:
                self._select_row(current.row() + 1)
            event.accept()
            return
        if vk == KVK_K or key == Qt.Key.Key_Up:
            current = self.currentIndex()
            if current.row() > 0:
                self._select_row(current.row() - 1)
            event.accept()
            return
        super().keyPressEvent(event)


class PluginTableView(QWidget):
    search_changed = Signal(str)
    plugin_selected = Signal(object)
    edit_requested = Signal(object, int, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 16)
        layout.setSpacing(12)

        self._search_bar = SearchBar()
        self._search_bar.search_changed.connect(self.search_changed)
        self._search_bar.escape_pressed.connect(self._on_search_escape)
        layout.addWidget(self._search_bar)

        self._model = PluginTableModel()
        self._model.edit_requested.connect(self.edit_requested)
        self._table = _VimTableView()
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._table.setFrameShape(QFrame.Shape.NoFrame)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._table.setStyleSheet("""
            QTableView {
                background: transparent;
            }
            QTableView::item {
                padding: 1px 4px;
            }
            QTableView::item:alternate {
                background: rgba(0, 0, 0, 0.08);
            }
            QTableView::item:selected {
                background: rgba(255, 255, 255, 0.1);
            }
            QHeaderView {
                background: transparent;
            }
            QHeaderView::section {
                padding: 4px 6px;
                background: rgba(0, 0, 0, 0.08);
                border: none;
            }
            QHeaderView::section:first {
                border-top-left-radius: 14px;
                border-bottom-left-radius: 14px;
            }
            QHeaderView::section:last {
                border-top-right-radius: 14px;
                border-bottom-right-radius: 14px;
            }
        """)

        layout.addWidget(self._table, 1)

        self._table.selectionModel().currentChanged.connect(self._on_current_changed)

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if current.isValid():
            plugin = self._model.get_plugin(current.row())
            if plugin:
                self.plugin_selected.emit(plugin)

    def set_plugins(self, logic: Logic) -> None:
        self._model.set_plugins(logic)
        self._resize_columns()

    def filter_by_category(self, category: str | None) -> None:
        self._model.filter_by_category(category)

    def filter_by_manufacturer(self, manufacturer: str) -> None:
        self._model.filter_by_manufacturer(manufacturer)

    def filter_by_search_results(
        self,
        plugins: list[AudioComponent],
        category: str | None = None,
        manufacturer: str | None = None,
    ) -> None:
        self._model.filter_by_search_results(plugins, category, manufacturer)

    def update_plugin_display(self, plugin: AudioComponent, column: int) -> None:
        self._model.update_plugin_display(plugin, column)

    def clear_search(self) -> None:
        self._search_bar.clear()

    def get_search_text(self) -> str:
        return self._search_bar.text()

    def focus_search(self) -> None:
        self._search_bar.setFocus()
        self._search_bar.selectAll()

    def focus_table(self) -> None:
        self._table.setFocus()
        has_selection = self._table.selectionModel().hasSelection()
        if not has_selection and self._model.rowCount() > 0:
            self._table.selectRow(0)

    def _on_search_escape(self) -> None:
        self._table.setFocus()

    def _resize_columns(self) -> None:
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)

        self._table.resizeColumnToContents(COL_TYPE)
        self._table.resizeColumnToContents(COL_MANUFACTURER)
        self._table.resizeColumnToContents(COL_VERSION)

        padding = 20
        type_width = header.sectionSize(COL_TYPE) + padding
        manufacturer_width = header.sectionSize(COL_MANUFACTURER) + padding
        version_width = header.sectionSize(COL_VERSION) + padding

        header.resizeSection(COL_TYPE, type_width)
        header.resizeSection(COL_MANUFACTURER, manufacturer_width)
        header.resizeSection(COL_VERSION, version_width)

        total_width = self._table.viewport().width()
        fixed_width = type_width + manufacturer_width + version_width
        remaining = total_width - fixed_width

        header.resizeSection(COL_NAME, int(remaining * 0.5))
        header.resizeSection(COL_CUSTOM_NAME, int(remaining * 0.25))
        header.resizeSection(COL_SHORT_NAME, int(remaining * 0.25))

        self._store_proportions()

    def _store_proportions(self) -> None:
        header = self._table.horizontalHeader()
        total = self._table.viewport().width()
        if total > 0:
            self._column_proportions = [
                header.sectionSize(i) / total for i in range(self._model.columnCount())
            ]

    def _apply_proportions(self) -> None:
        if not hasattr(self, "_column_proportions"):
            return
        header = self._table.horizontalHeader()
        total = self._table.viewport().width()
        for i, prop in enumerate(self._column_proportions):
            header.resizeSection(i, int(total * prop))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_proportions()
