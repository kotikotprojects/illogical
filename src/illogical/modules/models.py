from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from logic_plugin_manager.exceptions import (
    CategoryExistsError,
    CategoryValidationError,
    MusicAppsLoadError,
    MusicAppsWriteError,
)
from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractListModel,
    QAbstractTableModel,
    QByteArray,
    QMimeData,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Signal,
)

from illogical.modules.sf_symbols import sf_symbol
from illogical.modules.virtual_category import VirtualCategoryTree

if TYPE_CHECKING:
    from logic_plugin_manager import AudioComponent, Logic

CategoryError = (
    MusicAppsLoadError,
    MusicAppsWriteError,
    CategoryExistsError,
    CategoryValidationError,
    OSError,
    ValueError,
)

COL_NAME = 0
COL_CUSTOM_NAME = 1
COL_SHORT_NAME = 2
COL_TYPE = 3
COL_MANUFACTURER = 4
COL_VERSION = 5


def _format_version(version: int) -> str:
    if version <= 0:
        return ""
    major = (version >> 16) & 0xFF
    minor = (version >> 8) & 0xFF
    patch = version & 0xFF
    if patch:
        return f"{major}.{minor}.{patch}"
    if minor:
        return f"{major}.{minor}"
    return str(major)


class PluginTableModel(QAbstractTableModel):
    COLUMNS: ClassVar[list[str]] = [
        "Name",
        "Custom Name",
        "Short Name",
        "Type",
        "Manufacturer",
        "Version",
    ]

    edit_requested = Signal(object, int, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._all_plugins: list[AudioComponent] = []
        self._plugins: list[AudioComponent] = []
        self._sort_column: int = COL_NAME
        self._sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder

    def set_plugins(self, logic: Logic) -> None:
        self.beginResetModel()
        self._all_plugins = list(logic.plugins.all())
        self._plugins = self._all_plugins.copy()
        self._apply_sort()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._plugins)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self.COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(
            self.COLUMNS
        ):
            return self.COLUMNS[section]
        return None

    def data(  # noqa: PLR0911
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid() or not (0 <= index.row() < len(self._plugins)):
            return None

        plugin = self._plugins[index.row()]
        col = index.column()

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == COL_NAME:
                return plugin.name
            if col == COL_CUSTOM_NAME:
                return plugin.tagset.nickname
            if col == COL_SHORT_NAME:
                return plugin.tagset.shortname
            if col == COL_TYPE:
                return plugin.type_name.display_name
            if col == COL_MANUFACTURER:
                return plugin.manufacturer
            if col == COL_VERSION:
                version = getattr(plugin, "version", 0) or 0
                return _format_version(version)

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base_flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() in (COL_CUSTOM_NAME, COL_SHORT_NAME):
            return base_flags | Qt.ItemFlag.ItemIsEditable
        return base_flags

    def setData(  # noqa: N802
        self, index: QModelIndex, value: object, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole:
            return False
        if not index.isValid() or not (0 <= index.row() < len(self._plugins)):
            return False
        col = index.column()
        if col not in (COL_CUSTOM_NAME, COL_SHORT_NAME):
            return False

        plugin = self._plugins[index.row()]
        new_value = str(value) if value else ""

        if col == COL_CUSTOM_NAME:
            current_value = plugin.tagset.nickname
        else:
            current_value = plugin.tagset.shortname
        if new_value == (current_value or ""):
            return False

        self.edit_requested.emit(plugin, col, new_value)
        return False

    def update_plugin_display(self, plugin: AudioComponent, column: int) -> None:
        try:
            row = self._plugins.index(plugin)
        except ValueError:
            return
        index = self.index(row, column)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])

    def filter_by_category(self, category: str | None) -> None:
        self.beginResetModel()
        if category == "Show All":
            self._plugins = self._all_plugins.copy()
        elif category is None:
            self._plugins = [p for p in self._all_plugins if not p.categories]
        elif category == "Top Level":
            self._plugins = [
                p for p in self._all_plugins if any(c.name == "" for c in p.categories)
            ]
        else:
            self._plugins = [
                p
                for p in self._all_plugins
                if any(c.name == category for c in p.categories)
            ]
        self._apply_sort()
        self.endResetModel()

    def filter_by_manufacturer(self, manufacturer: str) -> None:
        self.beginResetModel()
        self._plugins = [
            p
            for p in self._all_plugins
            if p.manufacturer.lower() == manufacturer.lower()
        ]
        self._apply_sort()
        self.endResetModel()

    def filter_by_search_results(
        self,
        plugins: list[AudioComponent],
        category: str | None = None,
        manufacturer: str | None = None,
    ) -> None:
        self.beginResetModel()
        if manufacturer is not None:
            self._plugins = [
                p for p in plugins if p.manufacturer.lower() == manufacturer.lower()
            ]
        elif category == "Show All" or category is ...:
            self._plugins = plugins
        elif category is None:
            self._plugins = [p for p in plugins if not p.categories]
        elif category == "Top Level":
            self._plugins = [
                p for p in plugins if any(c.name == "" for c in p.categories)
            ]
        elif category is not None:
            self._plugins = [
                p for p in plugins if any(c.name == category for c in p.categories)
            ]
        else:
            self._plugins = plugins
        self._apply_sort()
        self.endResetModel()

    def get_plugin(self, row: int) -> AudioComponent | None:
        if 0 <= row < len(self._plugins):
            return self._plugins[row]
        return None

    def sort(
        self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
    ) -> None:
        self._sort_column = column
        self._sort_order = order
        self.beginResetModel()
        self._apply_sort()
        self.endResetModel()

    def _apply_sort(self) -> None:
        reverse = self._sort_order == Qt.SortOrder.DescendingOrder
        column = self._sort_column

        def get_sort_value(plugin: AudioComponent) -> str | int:
            if column == COL_VERSION:
                return getattr(plugin, "version", 0) or 0
            values = {
                COL_NAME: plugin.name,
                COL_CUSTOM_NAME: plugin.tagset.nickname or "",
                COL_SHORT_NAME: plugin.tagset.shortname or "",
                COL_TYPE: plugin.type_code,
                COL_MANUFACTURER: plugin.manufacturer,
            }
            return values.get(column, "").lower()

        self._plugins.sort(key=get_sort_value, reverse=reverse)


class CategoryTreeItem:
    def __init__(
        self,
        name: str,
        full_path: str,
        parent: CategoryTreeItem | None = None,
        plugin_count: int = 0,
    ) -> None:
        self.name = name
        self.full_path = full_path
        self.parent_item = parent
        self.children: list[CategoryTreeItem] = []
        self.plugin_count = plugin_count

    @property
    def is_empty(self) -> bool:
        return self.plugin_count == 0

    def append_child(self, child: CategoryTreeItem) -> None:
        self.children.append(child)

    def child(self, row: int) -> CategoryTreeItem | None:
        if 0 <= row < len(self.children):
            return self.children[row]
        return None

    def child_count(self) -> int:
        return len(self.children)

    def row(self) -> int:
        if self.parent_item:
            return self.parent_item.children.index(self)
        return 0


CATEGORY_MIME_TYPE = "application/x-illogical-category"


class CategoryTreeModel(QAbstractItemModel):
    category_changed = Signal()
    error_occurred = Signal(str, str)
    backup_requested = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root = CategoryTreeItem("", "")
        self._virtual_tree: VirtualCategoryTree | None = None
        self._logic: Logic | None = None

    def build_from_plugins(self, logic: Logic) -> None:
        self.beginResetModel()
        self._logic = logic
        self._virtual_tree = VirtualCategoryTree()
        self._virtual_tree.build_from_logic(logic)
        self._root = self._build_qt_tree_from_virtual()
        self.endResetModel()

    def _build_qt_tree_from_virtual(self) -> CategoryTreeItem:
        from illogical.modules.virtual_category import (  # noqa: PLC0415
            VirtualCategoryNode,
        )

        if self._virtual_tree is None:
            return CategoryTreeItem("", "")

        root = CategoryTreeItem("", "")

        def build_item(
            virtual_node: VirtualCategoryNode, parent_item: CategoryTreeItem
        ) -> None:
            for child_node in virtual_node.children:
                item = CategoryTreeItem(
                    child_node.name,
                    child_node.full_path,
                    parent_item,
                    child_node.plugin_count,
                )
                parent_item.append_child(item)
                build_item(child_node, item)

        build_item(self._virtual_tree.root, root)
        return root

    def _rebuild_from_virtual(self) -> None:
        self.beginResetModel()
        self._root = self._build_qt_tree_from_virtual()
        self.endResetModel()
        self.category_changed.emit()

    def index(
        self, row: int, column: int, parent: QModelIndex | None = None
    ) -> QModelIndex:
        if parent is None:
            parent = QModelIndex()
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = parent.internalPointer() if parent.isValid() else self._root
        child = parent_item.child(row)

        if child:
            return self.createIndex(row, column, child)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        child_item: CategoryTreeItem = index.internalPointer()
        parent_item = child_item.parent_item

        if parent_item is None or parent_item == self._root:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is None:
            parent = QModelIndex()
        if parent.column() > 0:
            return 0

        parent_item = parent.internalPointer() if parent.isValid() else self._root
        return parent_item.child_count()

    def columnCount(  # noqa: N802
        self,
        parent: QModelIndex | None = None,  # noqa: ARG002
    ) -> int:
        return 1

    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid():
            return None

        item: CategoryTreeItem = index.internalPointer()

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return item.name

        if role == Qt.ItemDataRole.UserRole:
            return item.full_path

        if role == Qt.ItemDataRole.DecorationRole and item.full_path == "Top Level":
            return sf_symbol("arrow.up", 14)

        return None

    def index_for_path(self, path: str) -> QModelIndex:
        def find_in_item(
            item: CategoryTreeItem, parent_index: QModelIndex
        ) -> QModelIndex:
            for row, child in enumerate(item.children):
                if child.full_path == path:
                    return self.index(row, 0, parent_index)
                result = find_in_item(child, self.index(row, 0, parent_index))
                if result.isValid():
                    return result
            return QModelIndex()

        return find_in_item(self._root, QModelIndex())

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        default_flags = super().flags(index)
        if not index.isValid():
            return default_flags | Qt.ItemFlag.ItemIsDropEnabled

        item: CategoryTreeItem = index.internalPointer()
        if item.full_path == "Top Level":
            return default_flags

        return (
            default_flags
            | Qt.ItemFlag.ItemIsDragEnabled
            | Qt.ItemFlag.ItemIsDropEnabled
            | Qt.ItemFlag.ItemIsEditable
        )

    def supportedDropActions(self) -> Qt.DropAction:  # noqa: N802
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list[str]:  # noqa: N802
        return [CATEGORY_MIME_TYPE]

    def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:  # noqa: N802
        mime_data = QMimeData()
        if not indexes:
            return mime_data

        paths = []
        for index in indexes:
            if index.isValid():
                item: CategoryTreeItem = index.internalPointer()
                if item.full_path and item.full_path != "Top Level":
                    paths.append(item.full_path)

        if paths:
            mime_data.setData(CATEGORY_MIME_TYPE, QByteArray(paths[0].encode("utf-8")))

        return mime_data

    def dropMimeData(  # noqa: N802, C901, PLR0911, PLR0912
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,  # noqa: ARG002
        parent: QModelIndex,
    ) -> bool:
        if action != Qt.DropAction.MoveAction:
            return False
        if not data.hasFormat(CATEGORY_MIME_TYPE):
            return False
        if self._virtual_tree is None or self._logic is None:
            return False

        raw_data = data.data(CATEGORY_MIME_TYPE).data()
        source_path = bytes(raw_data).decode("utf-8") if raw_data else ""
        source_node = self._virtual_tree.get_node(source_path)
        if source_node is None:
            return False

        all_nodes = source_node.all_nodes_flat()
        old_path_to_node = [(n.full_path, n) for n in all_nodes]

        if parent.isValid():
            target_item: CategoryTreeItem = parent.internalPointer()
            target_path = target_item.full_path
        else:
            target_path = ""

        if row == -1:
            target_node = self._virtual_tree.get_node(target_path)
            if target_node is None:
                return False
            if target_path == "Top Level":
                return False
            if not self._virtual_tree.insert_into_parent(source_node, target_node):
                return False
        else:
            if target_path:
                target_parent_node = self._virtual_tree.get_node(target_path)
            else:
                target_parent_node = self._virtual_tree.root

            if target_parent_node is None:
                return False

            if row < len(target_parent_node.children):
                sibling_node = target_parent_node.children[row]
                if not self._virtual_tree.move_before(source_node, sibling_node):
                    return False
            elif target_parent_node.children:
                last_sibling = target_parent_node.children[-1]
                if not self._virtual_tree.move_after(source_node, last_sibling):
                    return False

        changed = {
            old_path: n.full_path
            for old_path, n in old_path_to_node
            if old_path != n.full_path
        }

        self.backup_requested.emit(bool(changed))

        try:
            self._virtual_tree.sync_to_logic(self._logic, changed if changed else None)
            self._virtual_tree.update_plugin_counts(self._logic)
        except CategoryError as e:
            self.error_occurred.emit("Category Move Failed", str(e))
            return False
        self._rebuild_from_virtual()
        return True

    def move_category_up(self, index: QModelIndex) -> bool:
        if not index.isValid() or self._virtual_tree is None or self._logic is None:
            return False

        item: CategoryTreeItem = index.internalPointer()
        node = self._virtual_tree.get_node(item.full_path)
        if node is None:
            return False

        if not self._virtual_tree.move_within_level(node, -1):
            return False

        self.backup_requested.emit(False)  # noqa: FBT003

        try:
            self._virtual_tree.sync_to_logic(self._logic)
        except CategoryError as e:
            self.error_occurred.emit("Category Move Failed", str(e))
            return False
        self._rebuild_from_virtual()
        return True

    def move_category_down(self, index: QModelIndex) -> bool:
        if not index.isValid() or self._virtual_tree is None or self._logic is None:
            return False

        item: CategoryTreeItem = index.internalPointer()
        node = self._virtual_tree.get_node(item.full_path)
        if node is None:
            return False

        if not self._virtual_tree.move_within_level(node, 1):
            return False

        self.backup_requested.emit(False)  # noqa: FBT003

        try:
            self._virtual_tree.sync_to_logic(self._logic)
        except CategoryError as e:
            self.error_occurred.emit("Category Move Failed", str(e))
            return False
        self._rebuild_from_virtual()
        return True

    def extract_category(self, index: QModelIndex) -> bool:
        if not index.isValid() or self._virtual_tree is None or self._logic is None:
            return False

        item: CategoryTreeItem = index.internalPointer()
        node = self._virtual_tree.get_node(item.full_path)
        if node is None:
            return False

        all_nodes = node.all_nodes_flat()
        old_path_to_node = [(n.full_path, n) for n in all_nodes]

        if not self._virtual_tree.extract_from_parent(node):
            return False

        changed = {
            old_path: n.full_path
            for old_path, n in old_path_to_node
            if old_path != n.full_path
        }

        self.backup_requested.emit(True)  # noqa: FBT003

        try:
            self._virtual_tree.sync_to_logic(self._logic, changed if changed else None)
            self._virtual_tree.update_plugin_counts(self._logic)
        except CategoryError as e:
            self.error_occurred.emit("Category Move Failed", str(e))
            return False
        self._rebuild_from_virtual()
        return True

    def can_delete_category(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False

        item: CategoryTreeItem = index.internalPointer()
        if item.full_path == "Top Level":
            return False

        return item.is_empty and not item.children

    def delete_category(self, index: QModelIndex) -> bool:
        if not index.isValid() or self._virtual_tree is None or self._logic is None:
            return False
        if not self.can_delete_category(index):
            return False

        self.backup_requested.emit(True)  # noqa: FBT003

        item: CategoryTreeItem = index.internalPointer()
        if not self._virtual_tree.delete_category(item.full_path, self._logic):
            return False

        self._rebuild_from_virtual()
        return True

    def get_item_at_index(self, index: QModelIndex) -> CategoryTreeItem | None:
        if not index.isValid():
            return None
        return index.internalPointer()

    def setData(  # noqa: N802
        self, index: QModelIndex, value: object, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole:
            return False
        if not index.isValid():
            return False

        item: CategoryTreeItem = index.internalPointer()
        if item.full_path == "Top Level":
            return False

        new_name = str(value).strip() if value else ""
        if not new_name or new_name == item.name:
            return False

        if not self._virtual_tree or not self._logic:
            return False

        return self.rename_category(index, new_name)

    def create_category(self, name: str, parent_path: str | None = None) -> QModelIndex:
        if not self._virtual_tree or not self._logic:
            return QModelIndex()

        new_path = f"{parent_path}:{name}" if parent_path else name

        self.backup_requested.emit(True)  # noqa: FBT003

        try:
            if not self._virtual_tree.create_category(new_path, self._logic):
                return QModelIndex()
        except CategoryError as e:
            self.error_occurred.emit("Category Creation Failed", str(e))
            return QModelIndex()

        self._rebuild_from_virtual()
        return self.index_for_path(new_path)

    def rename_category(self, index: QModelIndex, new_name: str) -> bool:
        if not index.isValid() or not self._virtual_tree or not self._logic:
            return False

        item: CategoryTreeItem = index.internalPointer()
        if item.full_path == "Top Level":
            return False

        node = self._virtual_tree.get_node(item.full_path)
        if node is None:
            return False

        all_nodes = node.all_nodes_flat()
        old_path_to_node = [(n.full_path, n) for n in all_nodes]

        if not self._virtual_tree.rename_category(node, new_name):
            return False

        changed = {
            old_path: n.full_path
            for old_path, n in old_path_to_node
            if old_path != n.full_path
        }

        self.backup_requested.emit(True)  # noqa: FBT003

        try:
            self._virtual_tree.sync_to_logic(self._logic, changed if changed else None)
            self._virtual_tree.update_plugin_counts(self._logic)
        except CategoryError as e:
            self.error_occurred.emit("Category Rename Failed", str(e))
            return False

        QTimer.singleShot(0, self._rebuild_from_virtual)
        return True


class ManufacturerListModel(QAbstractListModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manufacturers: list[str] = []

    def build_from_plugins(self, logic: Logic) -> None:
        self.beginResetModel()
        manufacturers: set[str] = set()
        for plugin in logic.plugins.all():
            manufacturers.add(plugin.manufacturer)
        self._manufacturers = sorted(manufacturers, key=str.lower)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._manufacturers)

    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid() or not (0 <= index.row() < len(self._manufacturers)):
            return None

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole):
            return self._manufacturers[index.row()]

        return None


class ManufacturerFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def filterAcceptsRow(  # noqa: N802
        self, source_row: int, source_parent: QModelIndex
    ) -> bool:
        source_model = self.sourceModel()
        if source_model is None:
            return False
        index = source_model.index(source_row, 0, source_parent)
        manufacturer = index.data(Qt.ItemDataRole.DisplayRole)
        if manufacturer is None:
            return False
        return self.filterRegularExpression().match(manufacturer).hasMatch()
