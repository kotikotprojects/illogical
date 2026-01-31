from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from logic_plugin_manager.exceptions import CategoryExistsError

if TYPE_CHECKING:
    from logic_plugin_manager import Logic


@dataclass
class VirtualCategoryNode:
    name: str
    full_path: str
    parent: VirtualCategoryNode | None = None
    children: list[VirtualCategoryNode] = field(default_factory=list)
    plugin_count: int = 0

    @property
    def depth(self) -> int:
        level = 0
        node = self.parent
        while node is not None and node.full_path:
            level += 1
            node = node.parent
        return level

    @property
    def siblings(self) -> list[VirtualCategoryNode]:
        if self.parent is None:
            return [self]
        return self.parent.children

    @property
    def sibling_index(self) -> int:
        return self.siblings.index(self)

    @property
    def is_first(self) -> bool:
        return self.sibling_index == 0

    @property
    def is_last(self) -> bool:
        return self.sibling_index == len(self.siblings) - 1

    @property
    def is_empty(self) -> bool:
        return self.plugin_count == 0

    def descendants_flat(self) -> list[VirtualCategoryNode]:
        result: list[VirtualCategoryNode] = []
        for child in self.children:
            result.append(child)
            result.extend(child.descendants_flat())
        return result

    def all_nodes_flat(self) -> list[VirtualCategoryNode]:
        result = [self]
        for child in self.children:
            result.extend(child.all_nodes_flat())
        return result


class VirtualCategoryTree:
    def __init__(self) -> None:
        self._root = VirtualCategoryNode(name="", full_path="")
        self._nodes: dict[str, VirtualCategoryNode] = {}
        self._top_level: VirtualCategoryNode | None = None

    @property
    def root(self) -> VirtualCategoryNode:
        return self._root

    def get_node(self, path: str) -> VirtualCategoryNode | None:
        return self._nodes.get(path)

    def build_from_logic(self, logic: Logic) -> None:
        self._root = VirtualCategoryNode(name="", full_path="")
        self._nodes = {}

        self._top_level = VirtualCategoryNode(
            name="Top Level", full_path="Top Level", parent=self._root
        )
        self._root.children.append(self._top_level)
        self._nodes["Top Level"] = self._top_level

        plugin_categories: dict[str, int] = {}
        for plugin in logic.plugins.all():
            for cat in plugin.categories:
                if cat.name:
                    plugin_categories[cat.name] = plugin_categories.get(cat.name, 0) + 1

        tagpool_categories = set(logic.musicapps.tagpool.categories.keys())
        sorting_categories = set(logic.musicapps.properties.sorting)
        all_category_paths = (
            set(plugin_categories.keys()) | tagpool_categories | sorting_categories
        )

        for cat_path in all_category_paths:
            if not cat_path:
                continue
            self._ensure_category_exists(cat_path, plugin_categories.get(cat_path, 0))

        self._sort_by_logic_indexes(logic)

    def _ensure_category_exists(
        self, cat_path: str, plugin_count: int = 0
    ) -> VirtualCategoryNode:
        if cat_path in self._nodes:
            if plugin_count > 0:
                self._nodes[cat_path].plugin_count = plugin_count
            return self._nodes[cat_path]

        parts = cat_path.split(":")
        current_path = ""
        parent_node = self._root

        for i, part in enumerate(parts):
            current_path = f"{current_path}:{part}" if current_path else part
            if current_path in self._nodes:
                parent_node = self._nodes[current_path]
            else:
                is_final = i == len(parts) - 1
                node = VirtualCategoryNode(
                    name=part,
                    full_path=current_path,
                    parent=parent_node,
                    plugin_count=plugin_count if is_final else 0,
                )
                parent_node.children.append(node)
                self._nodes[current_path] = node
                parent_node = node

        return self._nodes[cat_path]

    def _sort_by_logic_indexes(self, logic: Logic) -> None:
        def get_sort_key(node: VirtualCategoryNode) -> tuple[int, str]:
            if node.full_path in logic.categories:
                return (logic.categories[node.full_path].index, node.full_path.lower())
            return (2**31 - 1, node.full_path.lower())

        def sort_children(node: VirtualCategoryNode) -> None:
            top_level = [c for c in node.children if c.full_path == "Top Level"]
            others = [c for c in node.children if c.full_path != "Top Level"]
            others.sort(key=get_sort_key)
            node.children = top_level + others
            for child in node.children:
                sort_children(child)

        sort_children(self._root)

    def move_within_level(self, node: VirtualCategoryNode, delta: int) -> bool:
        if node.parent is None:
            return False

        siblings = node.parent.children
        current_idx = siblings.index(node)
        new_idx = current_idx + delta

        if node.full_path == "Top Level":
            return False
        if new_idx < 0 or new_idx >= len(siblings):
            return False

        target = siblings[new_idx]
        if target.full_path == "Top Level":
            return False

        siblings[current_idx], siblings[new_idx] = (
            siblings[new_idx],
            siblings[current_idx],
        )
        return True

    def extract_from_parent(self, node: VirtualCategoryNode) -> bool:
        if node.parent is None or not node.parent.full_path:
            return False
        if node.full_path == "Top Level":
            return False

        old_parent = node.parent
        grandparent = old_parent.parent
        if grandparent is None:
            return False

        old_node_path = node.full_path
        if grandparent.full_path:
            new_node_path = f"{grandparent.full_path}:{node.name}"
        else:
            new_node_path = node.name

        del self._nodes[node.full_path]
        node.full_path = new_node_path
        self._nodes[node.full_path] = node

        for desc in node.descendants_flat():
            del self._nodes[desc.full_path]
            desc.full_path = desc.full_path.replace(old_node_path, new_node_path, 1)
            self._nodes[desc.full_path] = desc

        old_parent.children.remove(node)
        parent_idx = grandparent.children.index(old_parent)
        grandparent.children.insert(parent_idx + 1, node)
        node.parent = grandparent

        return True

    def insert_into_parent(  # noqa: C901
        self, node: VirtualCategoryNode, new_parent: VirtualCategoryNode
    ) -> bool:
        if node.full_path == "Top Level":
            return False
        if new_parent.full_path == "Top Level":
            return False
        if node.parent is None:
            return False

        old_path = node.full_path
        new_path = (
            f"{new_parent.full_path}:{node.name}" if new_parent.full_path else node.name
        )

        if new_path == old_path:
            return False

        if new_path in self._nodes and self._nodes[new_path] != node:
            return False

        old_paths = {node.full_path: node}
        for desc in node.descendants_flat():
            old_paths[desc.full_path] = desc

        if node.full_path in self._nodes:
            del self._nodes[node.full_path]
        node.full_path = new_path
        self._nodes[new_path] = node

        for desc in node.descendants_flat():
            old_desc_path = next(k for k, v in old_paths.items() if v == desc)
            if old_desc_path in self._nodes:
                del self._nodes[old_desc_path]
            desc.full_path = desc.full_path.replace(old_path, new_path, 1)
            self._nodes[desc.full_path] = desc

        if node in node.parent.children:
            node.parent.children.remove(node)
        new_parent.children.append(node)
        node.parent = new_parent

        return True

    def move_before(  # noqa: C901, PLR0911
        self, node: VirtualCategoryNode, target: VirtualCategoryNode
    ) -> bool:
        if node.full_path == "Top Level" or target.full_path == "Top Level":
            return False
        if node == target:
            return False
        if target.parent is None:
            return False

        target_parent = target.parent
        if target not in target_parent.children:
            return False
        target_idx = target_parent.children.index(target)

        if node.parent == target_parent:
            if node not in target_parent.children:
                return False
            node_idx = target_parent.children.index(node)
            target_parent.children.remove(node)
            if node_idx < target_idx:
                target_idx -= 1
            target_parent.children.insert(target_idx, node)
            return True

        old_path = node.full_path
        new_prefix = target_parent.full_path
        new_path = f"{new_prefix}:{node.name}" if new_prefix else node.name

        if new_path in self._nodes and self._nodes[new_path] != node:
            return False

        if new_path != old_path:
            old_paths = list(self._nodes.keys())
            for p in old_paths:
                if p == old_path or p.startswith(old_path + ":"):
                    n = self._nodes.pop(p)
                    n.full_path = p.replace(old_path, new_path, 1)
                    self._nodes[n.full_path] = n

            node.full_path = new_path

        if node.parent and node in node.parent.children:
            node.parent.children.remove(node)
        target_parent.children.insert(target_idx, node)
        node.parent = target_parent

        return True

    def move_after(  # noqa: C901, PLR0911
        self, node: VirtualCategoryNode, target: VirtualCategoryNode
    ) -> bool:
        if node.full_path == "Top Level" or target.full_path == "Top Level":
            return False
        if node == target:
            return False
        if target.parent is None:
            return False

        target_parent = target.parent
        if target not in target_parent.children:
            return False
        target_idx = target_parent.children.index(target) + 1

        if node.parent == target_parent:
            if node not in target_parent.children:
                return False
            node_idx = target_parent.children.index(node)
            target_parent.children.remove(node)
            if node_idx < target_idx:
                target_idx -= 1
            target_parent.children.insert(target_idx, node)
            return True

        old_path = node.full_path
        new_prefix = target_parent.full_path
        new_path = f"{new_prefix}:{node.name}" if new_prefix else node.name

        if new_path in self._nodes and self._nodes[new_path] != node:
            return False

        if new_path != old_path:
            old_paths = list(self._nodes.keys())
            for p in old_paths:
                if p == old_path or p.startswith(old_path + ":"):
                    n = self._nodes.pop(p)
                    n.full_path = p.replace(old_path, new_path, 1)
                    self._nodes[n.full_path] = n

            node.full_path = new_path

        if node.parent and node in node.parent.children:
            node.parent.children.remove(node)
        target_parent.children.insert(target_idx, node)
        node.parent = target_parent

        return True

    def calculate_flat_indexes(self) -> dict[str, int]:
        indexes: dict[str, int] = {}
        current_index = 0

        def traverse(node: VirtualCategoryNode) -> None:
            nonlocal current_index
            if node.full_path and node.full_path != "Top Level":
                indexes[node.full_path] = current_index
                current_index += 1
            for child in node.children:
                traverse(child)

        traverse(self._root)
        return indexes

    def sync_to_logic(  # noqa: C901, PLR0912
        self, logic: Logic, changed_paths: dict[str, str] | None = None
    ) -> None:
        changed_new_paths: set[str] = set()
        old_paths_to_remove: set[str] = set()

        if changed_paths:
            sorted_changes = sorted(
                changed_paths.items(), key=lambda x: len(x[0]), reverse=True
            )

            for old_path, new_path in sorted_changes:
                if old_path == new_path:
                    continue

                changed_new_paths.add(new_path)
                old_paths_to_remove.add(old_path)

                plugins_to_move = list(logic.plugins.get_by_category(old_path))

                try:
                    new_cat = logic.introduce_category(new_path)
                except CategoryExistsError:
                    new_cat = logic.categories.get(new_path)
                    if new_cat is None:
                        logic.discover_categories()
                        new_cat = logic.categories[new_path]

                logic.discover_categories()

                for plugin in plugins_to_move:
                    plugin.add_to_category(new_cat)
                    old_cat = logic.categories.get(old_path)
                    if old_cat:
                        with contextlib.suppress(Exception):
                            plugin.remove_from_category(old_cat)

            logic.plugins.reindex_all()

            for new_path in changed_new_paths:
                if new_path in logic.categories:
                    logic.sync_category_plugin_amount(logic.categories[new_path])

                node = self.get_node(new_path)
                if node:
                    plugins_in_cat = list(logic.plugins.get_by_category(new_path))
                    node.plugin_count = len(plugins_in_cat)

            logic.discover_categories()

            sorted_old_paths = sorted(
                old_paths_to_remove, key=lambda p: len(p), reverse=True
            )
            for old_path in sorted_old_paths:
                if old_path in logic.categories:
                    remaining = list(logic.plugins.get_by_category(old_path))
                    if not remaining:
                        with contextlib.suppress(Exception):
                            logic.musicapps.remove_category(old_path)

        flat_indexes = self.calculate_flat_indexes()
        sorted_paths = sorted(flat_indexes.keys(), key=lambda p: flat_indexes[p])

        logic.discover_categories()

        for path in sorted_paths:
            if path not in logic.categories:
                continue
            cat = logic.categories[path]
            target_index = flat_indexes[path]
            if cat.index != target_index:
                with contextlib.suppress(ValueError):
                    cat.move_to(target_index)

    def update_plugin_counts(self, logic: Logic) -> None:
        logic.plugins.reindex_all()
        for path, node in self._nodes.items():
            if path == "Top Level":
                continue
            node.plugin_count = len(list(logic.plugins.get_by_category(path)))

    def delete_category(self, path: str, logic: Logic) -> bool:
        node = self.get_node(path)
        if node is None:
            return False
        if node.full_path == "Top Level":
            return False
        if node.plugin_count > 0:
            return False
        if node.children:
            return False

        if node.parent:
            node.parent.children.remove(node)
        del self._nodes[path]

        if path in logic.categories:
            logic.musicapps.remove_category(path)

        return True

    def get_category_paths_for_move(self, node: VirtualCategoryNode) -> dict[str, str]:
        result: dict[str, str] = {}
        old_path = node.full_path
        for n in node.all_nodes_flat():
            if n.full_path != old_path:
                result[n.full_path.replace(old_path, node.full_path, 1)] = n.full_path
        return result
