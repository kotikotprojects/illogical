from __future__ import annotations

from typing import TYPE_CHECKING

from AppKit import NSColor  # type: ignore[attr-defined]
from PySide6.QtCore import QModelIndex, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QMenu,
    QPushButton,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from illogical.modules.models import (
    CategoryTreeItem,
    CategoryTreeModel,
    ManufacturerFilterProxy,
    ManufacturerListModel,
)
from illogical.modules.sf_symbols import sf_symbol
from illogical.ui.search_bar import SearchBar

if TYPE_CHECKING:
    from logic_plugin_manager import Logic
    from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainter


KVK_H = 0x04
KVK_J = 0x26
KVK_K = 0x28
KVK_L = 0x25


class _VimTreeView(QTreeView):
    enter_pressed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu_requested)
        self._expanded_paths: set[str] = set()
        self.context_menu_path: str | None = None

    def setModel(self, model: CategoryTreeModel | None) -> None:  # noqa: N802
        old_model = self.model()
        if old_model is not None:
            old_model.modelAboutToBeReset.disconnect(self._save_expanded_state)
            old_model.modelReset.disconnect(self._restore_expanded_state)
        super().setModel(model)
        if model is not None:
            model.modelAboutToBeReset.connect(self._save_expanded_state)
            model.modelReset.connect(self._restore_expanded_state)

    def _save_expanded_state(self) -> None:
        self._expanded_paths.clear()
        model = self.model()
        if not isinstance(model, CategoryTreeModel):
            return

        def collect_expanded(parent: QModelIndex) -> None:
            for row in range(model.rowCount(parent)):
                index = model.index(row, 0, parent)
                if self.isExpanded(index):
                    path = index.data(Qt.ItemDataRole.UserRole)
                    if path:
                        self._expanded_paths.add(path)
                    collect_expanded(index)

        collect_expanded(QModelIndex())

    def _restore_expanded_state(self) -> None:
        model = self.model()
        if not isinstance(model, CategoryTreeModel):
            return

        for path in self._expanded_paths:
            index = model.index_for_path(path)
            if index.isValid():
                self.expand(index)

    def _select_and_activate(self, index: QModelIndex) -> None:
        self.selectionModel().setCurrentIndex(
            index, self.selectionModel().SelectionFlag.ClearAndSelect
        )
        self.clicked.emit(index)

    def _on_context_menu_requested(self, pos: QPoint) -> None:
        index = self.indexAt(pos)
        if index.isValid():
            self._show_context_menu(index)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            item: CategoryTreeItem = index.internalPointer()
            if item.children:
                if self.isExpanded(index):
                    self.collapse(index)
                else:
                    self.expand(index)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802, C901, PLR0911, PLR0912
        vk = event.nativeVirtualKey()
        key = event.key()
        mods = event.modifiers()

        has_alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        has_shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        has_ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        has_meta = bool(mods & Qt.KeyboardModifier.MetaModifier)

        if has_alt and has_shift and not has_ctrl and not has_meta:
            model = self.model()
            current = self.currentIndex()
            if isinstance(model, CategoryTreeModel):
                if key == Qt.Key.Key_Up:
                    if not model.move_category_up(current):
                        model.extract_category(current)
                    self._restore_selection_after_move(current)
                    event.accept()
                    return
                if key == Qt.Key.Key_Down:
                    if not model.move_category_down(current):
                        model.extract_category(current)
                    self._restore_selection_after_move(current)
                    event.accept()
                    return

        if (
            has_alt
            and not has_shift
            and not has_ctrl
            and not has_meta
            and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            self._show_context_menu(self.currentIndex())
            event.accept()
            return

        if vk == KVK_J or key == Qt.Key.Key_Down:
            next_idx = self.indexBelow(self.currentIndex())
            if next_idx.isValid():
                self._select_and_activate(next_idx)
            event.accept()
            return
        if vk == KVK_K or key == Qt.Key.Key_Up:
            prev_idx = self.indexAbove(self.currentIndex())
            if prev_idx.isValid():
                self._select_and_activate(prev_idx)
            event.accept()
            return
        if vk == KVK_H or key == Qt.Key.Key_Left:
            self.collapse(self.currentIndex())
            event.accept()
            return
        if vk == KVK_L or key == Qt.Key.Key_Right:
            self.expand(self.currentIndex())
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.enter_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _restore_selection_after_move(self, old_index: QModelIndex) -> None:
        if not old_index.isValid():
            return
        item: CategoryTreeItem = old_index.internalPointer()
        path = item.full_path
        model = self.model()
        if isinstance(model, CategoryTreeModel):
            new_index = model.index_for_path(path)
            if new_index.isValid():
                parent = new_index.parent()
                while parent.isValid():
                    self.expand(parent)
                    parent = parent.parent()
                self.selectionModel().setCurrentIndex(
                    new_index, self.selectionModel().SelectionFlag.ClearAndSelect
                )

    def _show_context_menu(self, index: QModelIndex) -> None:
        if not index.isValid():
            return

        model = self.model()
        if not isinstance(model, CategoryTreeModel):
            return

        item: CategoryTreeItem = index.internalPointer()
        if item.full_path == "Top Level":
            return

        self.context_menu_path = item.full_path
        self.viewport().update()

        import pyqt_liquidglass as glass  # noqa: PLC0415

        menu = QMenu(self)
        menu.aboutToHide.connect(self._on_context_menu_hidden)
        menu.setStyleSheet("""
            QMenu {
                background: transparent;
                border: none;
                border-radius: 10px;
                padding: 4px 2px;
            }
            QMenu::item {
                padding: 6px 14px 6px 6px;
                margin: 0px 2px;
                border-radius: 6px;
                color: rgba(255, 255, 255, 0.9);
            }
            QMenu::item:selected {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QMenu::icon {
                padding-left: 6px;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(255, 255, 255, 0.12);
                margin: 6px 10px;
            }
        """)
        glass.prepare_window_for_glass(menu)

        rename_action = menu.addAction(sf_symbol("pencil", 14), "Rename")
        rename_action.triggered.connect(lambda: self._do_rename(index))

        create_sub_action = menu.addAction(
            sf_symbol("folder.badge.plus", 14), "Create Subcategory"
        )
        create_sub_action.triggered.connect(
            lambda: self._do_create_subcategory(model, index)
        )

        menu.addSeparator()

        move_up_action = menu.addAction(sf_symbol("arrow.up", 14), "Move Up")
        move_up_action.setShortcut("Alt+Shift+Up")
        move_up_action.triggered.connect(lambda: self._do_move_up(model, index))

        move_down_action = menu.addAction(sf_symbol("arrow.down", 14), "Move Down")
        move_down_action.setShortcut("Alt+Shift+Down")
        move_down_action.triggered.connect(lambda: self._do_move_down(model, index))

        if item.parent_item and item.parent_item.full_path:
            menu.addSeparator()
            extract_action = menu.addAction(
                sf_symbol("arrow.turn.left.up", 14), "Move Out of Parent"
            )
            extract_action.triggered.connect(lambda: self._do_extract(model, index))

        if model.can_delete_category(index):
            menu.addSeparator()
            delete_action = menu.addAction(sf_symbol("trash", 14), "Delete Category")
            delete_action.triggered.connect(lambda: model.delete_category(index))

        menu.popup(QCursor.pos())
        opts = glass.GlassOptions(corner_radius=10.0)
        QTimer.singleShot(0, lambda: glass.apply_glass_to_window(menu, opts))

    def _on_context_menu_hidden(self) -> None:
        self.context_menu_path = None
        self.viewport().update()

    def _do_move_up(self, model: CategoryTreeModel, index: QModelIndex) -> None:
        model.move_category_up(index)
        self._restore_selection_after_move(index)

    def _do_move_down(self, model: CategoryTreeModel, index: QModelIndex) -> None:
        model.move_category_down(index)
        self._restore_selection_after_move(index)

    def _do_extract(self, model: CategoryTreeModel, index: QModelIndex) -> None:
        model.extract_category(index)
        self._restore_selection_after_move(index)

    def _do_rename(self, index: QModelIndex) -> None:
        self.edit(index)

    def _do_create_subcategory(
        self, model: CategoryTreeModel, index: QModelIndex
    ) -> None:
        item: CategoryTreeItem = index.internalPointer()
        new_index = model.create_category("Untitled", item.full_path)
        if new_index.isValid():
            self.expand(index)
            self.setCurrentIndex(new_index)
            self.edit(new_index)


class _VimListView(QListView):
    enter_pressed = Signal()

    def _select_and_activate(self, index: QModelIndex) -> None:
        self.selectionModel().setCurrentIndex(
            index, self.selectionModel().SelectionFlag.ClearAndSelect
        )
        self.clicked.emit(index)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        vk = event.nativeVirtualKey()
        key = event.key()

        if vk == KVK_J or key == Qt.Key.Key_Down:
            current = self.currentIndex()
            next_idx = self.model().index(current.row() + 1, 0)
            if next_idx.isValid():
                self._select_and_activate(next_idx)
            event.accept()
            return
        if vk == KVK_K or key == Qt.Key.Key_Up:
            current = self.currentIndex()
            if current.row() > 0:
                prev_idx = self.model().index(current.row() - 1, 0)
                self._select_and_activate(prev_idx)
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.enter_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _CategoryDelegate(QStyledItemDelegate):
    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        from PySide6.QtGui import QBrush, QColor, QPainterPath  # noqa: PLC0415

        full_path = index.data(Qt.ItemDataRole.UserRole)
        icon = index.data(Qt.ItemDataRole.DecorationRole)

        tree_view = option.widget
        is_context_target = (
            isinstance(tree_view, _VimTreeView)
            and tree_view.context_menu_path == full_path
        )
        if is_context_target:
            painter.save()
            path = QPainterPath()
            path.addRoundedRect(option.rect.toRectF(), 4, 4)
            painter.fillPath(path, QBrush(QColor(128, 128, 128, 60)))
            painter.restore()

        if full_path == "Top Level" and icon and not icon.isNull():
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            opt.icon = icon  # type: ignore[attr-defined]
            opt.decorationPosition = QStyleOptionViewItem.Position.Left  # type: ignore[attr-defined]

            style = opt.widget.style() if opt.widget else None  # type: ignore[attr-defined]
            if style:
                icon_rect = QRect(
                    opt.rect.left() - 14,  # type: ignore[attr-defined]
                    opt.rect.top() + (opt.rect.height() - 14) // 2,  # type: ignore[attr-defined]
                    14,
                    14,
                )

                opt.icon = type(icon)()  # type: ignore[attr-defined]
                opt.decorationSize = type(opt.decorationSize)(1, 1)  # type: ignore[attr-defined]
                opt.rect.adjust(-5, 0, 0, 0)  # type: ignore[attr-defined]
                style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter)

                if opt.state & QStyle.StateFlag.State_Selected:  # type: ignore[attr-defined]
                    selected_icon = sf_symbol("arrow.up", 14, (1.0, 1.0, 1.0, 1.0))
                    selected_icon.paint(painter, icon_rect)
                else:
                    icon.paint(painter, icon_rect)
                return

        super().paint(painter, option, index)

    def setEditorData(  # noqa: N802
        self, editor: QWidget, index: QModelIndex
    ) -> None:
        from PySide6.QtWidgets import QLineEdit  # noqa: PLC0415

        if isinstance(editor, QLineEdit):
            text = index.data(Qt.ItemDataRole.EditRole)
            if text:
                editor.setText(str(text))
                editor.selectAll()
        else:
            super().setEditorData(editor, index)


class StickyItem(QWidget):
    clicked = Signal(str)

    def __init__(
        self, text: str, icon_name: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._icon_name = icon_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(6)

        self._icon_label = QLabel()
        icon = sf_symbol(icon_name, 16)
        if not icon.isNull():
            self._icon_label.setPixmap(icon.pixmap(16, 16))

        self._text_label = QLabel(text)

        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label)
        layout.addStretch()

    def set_selected(self, selected: bool) -> None:  # noqa: FBT001
        if selected:
            accent = NSColor.controlAccentColor()
            accent = accent.colorUsingColorSpaceName_("NSCalibratedRGBColorSpace")
            r, g, b = (
                accent.redComponent(),
                accent.greenComponent(),
                accent.blueComponent(),
            )
            self._text_label.setStyleSheet(
                f"color: rgb({int(r * 255)}, {int(g * 255)}, {int(b * 255)});"
            )
            icon = sf_symbol(self._icon_name, 16, (r, g, b, 1.0))
            if not icon.isNull():
                self._icon_label.setPixmap(icon.pixmap(16, 16))
        else:
            self._text_label.setStyleSheet("")
            icon = sf_symbol(self._icon_name, 16)
            if not icon.isNull():
                self._icon_label.setPixmap(icon.pixmap(16, 16))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: ARG002, N802
        self.clicked.emit(self._text)


class _SectionHeader(QWidget):
    def __init__(
        self, title: str, icon_name: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        icon_label = QLabel()
        icon = sf_symbol(icon_name, 16)
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(16, 16))

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 11px;")

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addStretch()


class _CategorySectionHeader(_SectionHeader):
    add_clicked = Signal()

    def __init__(
        self, title: str, icon_name: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(title, icon_name, parent)

        from PySide6.QtCore import QSize  # noqa: PLC0415

        self._add_button = QPushButton()
        self._add_button.setFixedSize(16, 16)
        self._add_button.setIconSize(QSize(10, 10))
        self._add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        icon = sf_symbol("plus", 10, (0.25, 0.25, 0.27, 1.0), bold=True)
        if not icon.isNull():
            self._add_button.setIcon(icon)
        self._add_button.setStyleSheet("""
            QPushButton {
                background-color: #9B999E;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #ADABAF;
            }
            QPushButton:pressed {
                background-color: #8A888D;
            }
        """)
        self._add_button.clicked.connect(self.add_clicked)

        layout = self.layout()
        if layout is not None:
            layout.addWidget(self._add_button)


class _DraggableHeader(_SectionHeader):
    dragged = Signal(int)

    def __init__(
        self, title: str, icon_name: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(title, icon_name, parent)
        self.setCursor(Qt.CursorShape.SplitVCursor)
        self._drag_start: int | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint().y()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_start is not None:
            delta = event.globalPosition().toPoint().y() - self._drag_start
            self.dragged.emit(delta)
            self._drag_start = event.globalPosition().toPoint().y()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: ARG002, N802
        self._drag_start = None


class Sidebar(QWidget):
    category_selected = Signal(object)
    manufacturer_selected = Signal(str)
    enter_pressed = Signal()
    backup_requested = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(200)

        self._active_category: str | None = None
        self._active_manufacturer: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._create_sticky_items())
        layout.addWidget(self._create_splitter(), 1)

    def _create_sticky_items(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(9, 18, 9, 9)
        layout.setSpacing(0)

        self._show_all = StickyItem("Show All", "tray.full")
        self._show_all.clicked.connect(self._on_show_all_clicked)

        self._uncategorized = StickyItem("Uncategorized", "questionmark.folder")
        self._uncategorized.clicked.connect(self._on_uncategorized_clicked)

        layout.addWidget(self._show_all)
        layout.addWidget(self._uncategorized)
        return container

    def _create_splitter(self) -> QWidget:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(9, 0, 9, 9)
        container_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        splitter.addWidget(self._create_category_section())
        splitter.addWidget(self._create_manufacturer_section())

        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        splitter.setCollapsible(0, False)  # noqa: FBT003
        splitter.setCollapsible(1, False)  # noqa: FBT003

        self._splitter = splitter
        container_layout.addWidget(splitter)
        return container

    def _create_category_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = _CategorySectionHeader("Category", "folder")
        header.add_clicked.connect(self._on_add_category_clicked)
        layout.addWidget(header)

        tree_container = QWidget()
        tree_layout = QHBoxLayout(tree_container)
        tree_layout.setContentsMargins(9, 0, 0, 0)
        tree_layout.setSpacing(0)

        self._category_model = CategoryTreeModel()
        self._category_model.error_occurred.connect(self._show_category_error)
        self._category_model.backup_requested.connect(self.backup_requested)
        self._category_tree = _VimTreeView(self)
        self._category_tree.setItemDelegate(_CategoryDelegate(self._category_tree))
        self._category_tree.setModel(self._category_model)
        self._category_tree.setHeaderHidden(True)
        self._category_tree.setIndentation(16)
        self._category_tree.setFrameShape(QFrame.Shape.NoFrame)
        self._category_tree.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._category_tree.viewport().setAutoFillBackground(False)
        self._category_tree.setStyleSheet("QTreeView::item { padding: 4px 2px; }")
        self._category_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        font = self._category_tree.font()
        font.setWeight(QFont.Weight.Normal)
        self._category_tree.setFont(font)
        self._category_tree.clicked.connect(self._on_category_clicked)
        self._category_tree.enter_pressed.connect(self.enter_pressed)
        tree_layout.addWidget(self._category_tree)

        layout.addWidget(tree_container, 1)

        return section

    def _create_manufacturer_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = _DraggableHeader("Manufacturer", "list.bullet")
        header.dragged.connect(self._on_header_dragged)
        layout.addWidget(header)

        self._manufacturer_search = SearchBar()
        self._manufacturer_search.setFixedHeight(28)
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(9, 4, 9, 4)
        search_layout.addWidget(self._manufacturer_search)
        layout.addWidget(search_container)

        self._manufacturer_model = ManufacturerListModel()
        self._manufacturer_proxy = ManufacturerFilterProxy()
        self._manufacturer_proxy.setSourceModel(self._manufacturer_model)
        self._manufacturer_list = _VimListView()
        self._manufacturer_list.setModel(self._manufacturer_proxy)
        self._manufacturer_list.setFrameShape(QFrame.Shape.NoFrame)
        self._manufacturer_list.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self._manufacturer_list.viewport().setAutoFillBackground(False)
        self._manufacturer_list.setStyleSheet("QListView::item { padding: 4px 8px; }")
        font = self._manufacturer_list.font()
        font.setWeight(QFont.Weight.Normal)
        self._manufacturer_list.setFont(font)
        self._manufacturer_list.clicked.connect(self._on_manufacturer_clicked)
        self._manufacturer_list.enter_pressed.connect(self.enter_pressed)
        self._manufacturer_search.search_changed.connect(self._filter_manufacturers)
        self._manufacturer_search.escape_pressed.connect(
            self._on_manufacturer_search_escape
        )
        layout.addWidget(self._manufacturer_list, 1)

        return section

    def populate(self, logic: Logic) -> None:
        self._category_model.build_from_plugins(logic)
        self._manufacturer_model.build_from_plugins(logic)

    def _clear_selections(self) -> None:
        self._category_tree.clearSelection()
        self._manufacturer_list.clearSelection()
        self._uncategorized.set_selected(False)

    def _show_category_error(self, title: str, message: str) -> None:
        from AppKit import NSAlert, NSAlertStyleWarning, NSApp  # noqa: PLC0415

        alert = NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)
        alert.setAlertStyle_(NSAlertStyleWarning)
        alert.addButtonWithTitle_("OK")

        window = None
        if self.window():
            window = self.window().winId().__int__()
            ns_window = NSApp.windowWithWindowNumber_(window)
            if ns_window:
                alert.beginSheetModalForWindow_completionHandler_(ns_window, None)
                return

        alert.runModal()

    def _on_show_all_clicked(self) -> None:
        self._active_category = "Show All"
        self._active_manufacturer = None
        self._clear_selections()
        self.category_selected.emit("Show All")

    def _on_uncategorized_clicked(self) -> None:
        self._active_category = None
        self._active_manufacturer = None
        self._clear_selections()
        self.category_selected.emit(None)

    def _on_category_clicked(self, index: QModelIndex) -> None:
        full_path = index.data(Qt.ItemDataRole.UserRole)
        if full_path:
            self._active_category = full_path
            self._active_manufacturer = None
            self._manufacturer_list.clearSelection()
            self.category_selected.emit(full_path)

    def _on_add_category_clicked(self) -> None:
        index = self._category_model.create_category("Untitled")
        if index.isValid():
            parent = index.parent()
            while parent.isValid():
                self._category_tree.expand(parent)
                parent = parent.parent()
            self._category_tree.setCurrentIndex(index)
            self._category_tree.edit(index)

    def _on_manufacturer_clicked(self, index: QModelIndex) -> None:
        manufacturer = index.data(Qt.ItemDataRole.DisplayRole)
        if manufacturer:
            self._active_manufacturer = manufacturer
            self._active_category = None
            self._category_tree.clearSelection()
            self.manufacturer_selected.emit(manufacturer)

    def _filter_manufacturers(self, text: str) -> None:
        self._manufacturer_proxy.setFilterFixedString(text)

    def _on_manufacturer_search_escape(self) -> None:
        self._manufacturer_list.setFocus()

    def is_manufacturer_mode(self) -> bool:
        return (
            self._manufacturer_search.hasFocus()
            or self._manufacturer_list.selectionModel().hasSelection()
        )

    def focus_manufacturer_search(self) -> None:
        self._manufacturer_search.setFocus()
        self._manufacturer_search.selectAll()

    def clear_manufacturer_search(self) -> None:
        self._manufacturer_search.clear()

    def select_show_all(self) -> None:
        self._active_category = "Show All"
        self._active_manufacturer = None
        self._clear_selections()
        self.category_selected.emit("Show All")

    def select_uncategorized(self) -> None:
        self._active_category = None
        self._active_manufacturer = None
        self._clear_selections()
        self._uncategorized.set_selected(True)
        self.category_selected.emit(None)

    def focus_category_tree(self) -> None:
        self._category_tree.setFocus()

        if self._active_category and self._active_category not in ("Show All", None):
            target_path = self._active_category
        else:
            target_path = "Top Level"

        target_index = self._category_model.index_for_path(target_path)
        if target_index.isValid():
            parent = target_index.parent()
            while parent.isValid():
                self._category_tree.expand(parent)
                parent = parent.parent()
            self._category_tree.selectionModel().setCurrentIndex(
                target_index,
                self._category_tree.selectionModel().SelectionFlag.ClearAndSelect,
            )

    def focus_manufacturer_list(self) -> None:
        self._manufacturer_list.setFocus()

        target_index = None
        if self._active_manufacturer:
            for row in range(self._manufacturer_proxy.rowCount()):
                index = self._manufacturer_proxy.index(row, 0)
                if index.data(Qt.ItemDataRole.DisplayRole) == self._active_manufacturer:
                    target_index = index
                    break

        if target_index is None:
            first_index = self._manufacturer_proxy.index(0, 0)
            if first_index.isValid():
                target_index = first_index

        if target_index is not None:
            self._manufacturer_list.selectionModel().setCurrentIndex(
                target_index,
                self._manufacturer_list.selectionModel().SelectionFlag.ClearAndSelect,
            )

    def _on_header_dragged(self, delta: int) -> None:
        sizes = self._splitter.sizes()
        min_size = 50
        new_top = max(min_size, sizes[0] + delta)
        new_bottom = max(min_size, sizes[1] - delta)
        self._splitter.setSizes([new_top, new_bottom])

    def highlight_categories(self, category_paths: list[str]) -> None:
        self._category_tree.clearSelection()

        if self._active_manufacturer is None:
            self._manufacturer_list.clearSelection()

        self._uncategorized.set_selected(False)

        if not category_paths:
            self._uncategorized.set_selected(True)
            return

        selection_model = self._category_tree.selectionModel()

        first_index = None
        for path in category_paths:
            index = self._category_model.index_for_path(path)
            if index.isValid():
                parent = index.parent()
                while parent.isValid():
                    self._category_tree.expand(parent)
                    parent = parent.parent()
                selection_model.select(index, selection_model.SelectionFlag.Select)
                if first_index is None:
                    first_index = index

        if first_index is not None:
            self._category_tree.scrollTo(first_index)
