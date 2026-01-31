from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractListModel,
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    Signal,
)

from illogical.modules.sf_symbols import sf_symbol

if TYPE_CHECKING:
    from logic_plugin_manager import AudioComponent, Logic


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
        self, name: str, full_path: str, parent: CategoryTreeItem | None = None
    ) -> None:
        self.name = name
        self.full_path = full_path
        self.parent_item = parent
        self.children: list[CategoryTreeItem] = []

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


class CategoryTreeModel(QAbstractItemModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root = CategoryTreeItem("", "")

    def build_from_plugins(self, logic: Logic) -> None:
        self.beginResetModel()
        self._root = CategoryTreeItem("", "")

        categories: set[str] = set()
        for plugin in logic.plugins.all():
            for cat in plugin.categories:
                if cat.name != "":
                    categories.add(cat.name)

        category_items: dict[str, CategoryTreeItem] = {}

        top_level_item = CategoryTreeItem("Top Level", "Top Level", self._root)
        self._root.append_child(top_level_item)

        for cat_path in categories:
            parts = cat_path.split(":")
            current_path = ""
            parent_item = self._root

            for part in parts:
                current_path = f"{current_path}:{part}" if current_path else part

                if current_path not in category_items:
                    item = CategoryTreeItem(part, current_path, parent_item)
                    parent_item.append_child(item)
                    category_items[current_path] = item

                parent_item = category_items[current_path]

        self._sort_category_tree(self._root, logic)
        self.endResetModel()

    def _sort_category_tree(self, item: CategoryTreeItem, logic: Logic) -> None:
        def get_sort_key(path: str) -> tuple[int, str]:
            if path in logic.categories:
                return (logic.categories[path].index, path.lower())
            return (2**31 - 1, path.lower())

        top_level = [c for c in item.children if c.full_path == "Top Level"]
        others = [c for c in item.children if c.full_path != "Top Level"]
        others.sort(key=lambda c: get_sort_key(c.full_path))
        item.children = top_level + others
        for child in item.children:
            self._sort_category_tree(child, logic)

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

        if role == Qt.ItemDataRole.DisplayRole:
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
