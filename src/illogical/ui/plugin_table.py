from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QItemSelection, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QMenu,
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
    CategoryTreeItem,
    CategoryTreeModel,
    PluginTableModel,
)
from illogical.ui.search_bar import SearchBar

if TYPE_CHECKING:
    from logic_plugin_manager import AudioComponent, Logic
    from PySide6.QtCore import QEvent, QModelIndex
    from PySide6.QtGui import QKeyEvent, QMouseEvent, QResizeEvent


KVK_J = 0x26
KVK_K = 0x28


class _VimTableView(QTableView):
    enter_pressed = Signal()
    context_menu_requested = Signal(QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._anchor_row: int | None = None
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def _on_context_menu(self, pos: QPoint) -> None:
        if self.selectionModel().hasSelection():
            self.context_menu_requested.emit(pos)

    def event(self, e: QEvent) -> bool:
        from PySide6.QtCore import QEvent as QEventType  # noqa: PLC0415
        from PySide6.QtGui import QKeyEvent as QKeyEventType  # noqa: PLC0415

        if (
            e.type() == QEventType.Type.ShortcutOverride
            and isinstance(e, QKeyEventType)
            and e.key() == Qt.Key.Key_A
            and e.modifiers() == Qt.KeyboardModifier.ControlModifier
        ):
            e.accept()
            return True
        return super().event(e)

    def _select_all_rows(self) -> None:
        row_count = self.model().rowCount()
        if row_count > 0:
            top_left = self.model().index(0, 0)
            bottom_right = self.model().index(
                row_count - 1, self.model().columnCount() - 1
            )
            selection = QItemSelection(top_left, bottom_right)
            self.selectionModel().select(
                selection,
                self.selectionModel().SelectionFlag.ClearAndSelect
                | self.selectionModel().SelectionFlag.Rows,
            )
            self._anchor_row = 0

    def _select_row(self, row: int) -> None:
        index = self.model().index(row, 0)
        self.selectionModel().setCurrentIndex(
            index,
            self.selectionModel().SelectionFlag.ClearAndSelect
            | self.selectionModel().SelectionFlag.Rows,
        )
        self._anchor_row = row

    def _extend_selection_to(self, row: int) -> None:
        if self._anchor_row is None:
            self._anchor_row = self.currentIndex().row()

        start = min(self._anchor_row, row)
        end = max(self._anchor_row, row)

        self.selectionModel().clear()
        for r in range(start, end + 1):
            idx = self.model().index(r, 0)
            self.selectionModel().select(
                idx,
                self.selectionModel().SelectionFlag.Select
                | self.selectionModel().SelectionFlag.Rows,
            )

        index = self.model().index(row, 0)
        self.selectionModel().setCurrentIndex(
            index, self.selectionModel().SelectionFlag.NoUpdate
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        index = self.indexAt(event.position().toPoint())
        if not index.isValid():
            super().mousePressEvent(event)
            return

        mods = event.modifiers()
        has_cmd = bool(mods & Qt.KeyboardModifier.ControlModifier)
        has_shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        if has_cmd and not has_shift:
            self.selectionModel().setCurrentIndex(
                index,
                self.selectionModel().SelectionFlag.Toggle
                | self.selectionModel().SelectionFlag.Rows,
            )
            if self._anchor_row is None:
                self._anchor_row = index.row()
            event.accept()
            return

        if has_shift and self._anchor_row is not None:
            self.selectionModel().clear()
            start = min(self._anchor_row, index.row())
            end = max(self._anchor_row, index.row())
            for r in range(start, end + 1):
                idx = self.model().index(r, 0)
                self.selectionModel().select(
                    idx,
                    self.selectionModel().SelectionFlag.Select
                    | self.selectionModel().SelectionFlag.Rows,
                )
            self.selectionModel().setCurrentIndex(
                index, self.selectionModel().SelectionFlag.NoUpdate
            )
            event.accept()
            return

        self._anchor_row = index.row()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        vk = event.nativeVirtualKey()
        key = event.key()
        mods = event.modifiers()
        has_shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        has_alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        has_ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)

        if has_ctrl and key == Qt.Key.Key_A:
            self._select_all_rows()
            event.accept()
            return

        if has_alt and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.context_menu_requested.emit(QPoint(0, 0))
            event.accept()
            return

        if vk == KVK_J or key == Qt.Key.Key_Down:
            current = self.currentIndex()
            if current.row() < self.model().rowCount() - 1:
                new_row = current.row() + 1
                if has_shift:
                    self._extend_selection_to(new_row)
                else:
                    self._select_row(new_row)
            event.accept()
            return
        if vk == KVK_K or key == Qt.Key.Key_Up:
            current = self.currentIndex()
            if current.row() > 0:
                new_row = current.row() - 1
                if has_shift:
                    self._extend_selection_to(new_row)
                else:
                    self._select_row(new_row)
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.enter_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def get_selected_plugins(self) -> list[AudioComponent]:
        model = self.model()
        if not isinstance(model, PluginTableModel):
            return []
        plugins = []
        for index in self.selectionModel().selectedRows():
            plugin = model.get_plugin(index.row())
            if plugin:
                plugins.append(plugin)
        return plugins


class PluginTableView(QWidget):
    search_changed = Signal(str)
    plugin_selected = Signal(object)
    edit_requested = Signal(object, int, str)
    category_assignment_requested = Signal(list, str, bool)
    category_removal_requested = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._category_tree: CategoryTreeModel | None = None

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
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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
        self._table.enter_pressed.connect(self._on_enter_pressed)
        self._table.context_menu_requested.connect(self._on_context_menu_requested)

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if current.isValid():
            plugin = self._model.get_plugin(current.row())
            if plugin:
                self.plugin_selected.emit(plugin)

    def _on_enter_pressed(self) -> None:
        current = self._table.currentIndex()
        if current.isValid():
            plugin = self._model.get_plugin(current.row())
            if plugin:
                self.plugin_selected.emit(plugin)

    def set_category_tree(self, tree: CategoryTreeModel) -> None:
        self._category_tree = tree

    def _on_context_menu_requested(self, pos: QPoint) -> None:  # noqa: ARG002
        plugins = self._table.get_selected_plugins()
        if not plugins:
            return
        self._show_context_menu(plugins)

    def _show_context_menu(self, plugins: list[AudioComponent]) -> None:
        import pyqt_liquidglass as glass  # noqa: PLC0415

        opts = glass.GlassOptions(corner_radius=10.0)

        def apply_glass_on_show(m: QMenu) -> None:
            glass.prepare_window_for_glass(m)
            glass.apply_glass_to_window(m, opts)

        menu = QMenu(self)
        menu.setStyleSheet(self._get_glass_menu_stylesheet())
        glass.prepare_window_for_glass(menu)

        assign_menu = menu.addMenu("Assign to")
        assign_menu.setStyleSheet(self._get_glass_menu_stylesheet())
        assign_menu.aboutToShow.connect(lambda: apply_glass_on_show(assign_menu))
        self._build_category_submenu(assign_menu, plugins, is_move=False)

        has_categories = any(p.categories for p in plugins)
        if has_categories:
            move_menu = menu.addMenu("Move to")
            move_menu.setStyleSheet(self._get_glass_menu_stylesheet())
            move_menu.aboutToShow.connect(lambda: apply_glass_on_show(move_menu))
            self._build_category_submenu(move_menu, plugins, is_move=True)

            menu.addSeparator()
            remove_action = menu.addAction("Remove from current category")
            remove_action.triggered.connect(
                lambda: self._on_remove_from_category(plugins)
            )

        menu.popup(QCursor.pos())
        QTimer.singleShot(0, lambda: glass.apply_glass_to_window(menu, opts))

    def _build_category_submenu(
        self, menu: QMenu, plugins: list[AudioComponent], *, is_move: bool
    ) -> None:
        import pyqt_liquidglass as glass  # noqa: PLC0415

        if self._category_tree is None:
            return

        def apply_glass_on_show(submenu: QMenu) -> None:
            glass.prepare_window_for_glass(submenu)
            opts = glass.GlassOptions(corner_radius=8.0)
            glass.apply_glass_to_window(submenu, opts)

        def build_from_item(parent_menu: QMenu, item: CategoryTreeItem) -> None:
            for child in item.children:
                if child.full_path == "Top Level":
                    action = parent_menu.addAction("Top Level")
                    action.triggered.connect(
                        lambda _=None, p=plugins, m=is_move: self._on_category_action(
                            p, "", m
                        )
                    )
                elif child.children:
                    submenu = parent_menu.addMenu(child.name)
                    submenu.setStyleSheet(self._get_glass_menu_stylesheet())
                    submenu.aboutToShow.connect(
                        lambda s=submenu: apply_glass_on_show(s)
                    )

                    self_action = submenu.addAction(f"{child.name}")
                    self_action.triggered.connect(
                        lambda _=None, p=plugins, c=child.full_path, m=is_move: (
                            self._on_category_action(p, c, m)
                        )
                    )
                    submenu.addSeparator()
                    build_from_item(submenu, child)
                else:
                    action = parent_menu.addAction(child.name)
                    action.triggered.connect(
                        lambda _=None, p=plugins, c=child.full_path, m=is_move: (
                            self._on_category_action(p, c, m)
                        )
                    )

        build_from_item(menu, self._category_tree.root_item)

    def _on_category_action(
        self,
        plugins: list[AudioComponent],
        category_path: str,
        is_move: bool,  # noqa: FBT001
    ) -> None:
        self.category_assignment_requested.emit(plugins, category_path, is_move)

    def _on_remove_from_category(self, plugins: list[AudioComponent]) -> None:
        self.category_removal_requested.emit(plugins)

    def _get_glass_menu_stylesheet(self) -> str:
        return """
            QMenu {
                background: transparent;
                border: none;
                border-radius: 10px;
                padding: 4px 2px;
            }
            QMenu::item {
                padding: 4px 12px 4px 6px;
                margin: 0px 2px;
                border-radius: 6px;
                color: rgba(255, 255, 255, 0.9);
            }
            QMenu::item:selected {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QMenu::separator {
                height: 1px;
                background: rgba(255, 255, 255, 0.12);
                margin: 4px 10px;
            }
            QMenu::right-arrow {
                width: 8px;
                height: 8px;
                right: 9px;
                top: -1px;
            }
        """

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

        current = self._table.currentIndex()
        if current.isValid():
            plugin = self._model.get_plugin(current.row())
            if plugin:
                self.plugin_selected.emit(plugin)

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
