from __future__ import annotations

from typing import TYPE_CHECKING

import pyqt_liquidglass as glass
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent

SHORTCUTS: dict[str, list[tuple[str, str]]] = {
    "Navigation": [
        ("J / ↓", "Move down"),
        ("K / ↑", "Move up"),
        ("H / ←", "Collapse (categories)"),
        ("L / →", "Expand (categories)"),
        ("↩", "Enter category"),
    ],
    "Visual Mode": [("⇧V", "Select lines"), ("Esc", "Exit mode")],
    "Quick Access": [
        ("⌘1", "Show All"),
        ("⌘2", "Uncategorized"),
        ("⌘3", "Focus categories"),
        ("⌘4", "Focus manufacturers"),
        ("⌘F", "Search"),
    ],
    "Actions": [
        ("⌥↩", "Context menu"),
        ("⌥⇧↑", "Move category up"),
        ("⌥⇧↓", "Move category down"),
        ("⌘A", "Select all"),
    ],
    "Drag & Drop": [("⇧+Drop", "Add (don't move)")],
    "Backup": [("⌘B", "Create backup"), ("⌘⇧R", "Restore")],
}


class ShortcutsHelpWindow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_window()
        self._setup_ui()

    def _setup_window(self) -> None:
        self.setWindowTitle("Keyboard Shortcuts")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(24)

        title = QLabel("Keyboard Shortcuts")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 17px;
            font-weight: 600;
            color: white;
            background: transparent;
        """)
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(32)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        sections = list(SHORTCUTS.items())
        for i, (section_name, shortcuts) in enumerate(sections):
            col = i % 2
            row = i // 2
            section_widget = self._create_section(section_name, shortcuts)
            grid.addWidget(section_widget, row, col, Qt.AlignmentFlag.AlignTop)

        layout.addLayout(grid)
        layout.addStretch()

        hint = QLabel("Press Esc to close")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("""
            font-size: 11px;
            color: rgba(255, 255, 255, 0.4);
            background: transparent;
        """)
        layout.addWidget(hint)

    def _create_section(self, title: str, shortcuts: list[tuple[str, str]]) -> QWidget:
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QLabel(title)
        header.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.9);
            background: transparent;
            padding-bottom: 4px;
        """)
        layout.addWidget(header)

        for key, description in shortcuts:
            row = self._create_shortcut_row(key, description)
            layout.addWidget(row)

        return section

    def _create_shortcut_row(self, key: str, description: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(14)

        key_label = QLabel(key)
        key_label.setStyleSheet("""
            font-size: 13px;
            font-family: 'SF Mono', 'Menlo', monospace;
            color: rgba(255, 255, 255, 0.95);
            background: rgba(255, 255, 255, 0.1);
            border-radius: 5px;
            padding: 5px 10px;
        """)

        desc_label = QLabel(description)
        desc_label.setStyleSheet("""
            font-size: 13px;
            color: rgba(255, 255, 255, 0.7);
            background: transparent;
        """)

        layout.addWidget(key_label)
        layout.addWidget(desc_label, 1)

        return row

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, _event: object) -> None:  # noqa: N802
        self.close()

    def show_centered(self, parent: QWidget | None = None) -> None:
        glass.prepare_window_for_glass(self, frameless=True)
        self.adjustSize()
        self.show()
        self.activateWindow()
        self.setFocus()

        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.center().x() - self.width() // 2
            y = parent_geo.center().y() - self.height() // 2
            self.move(x, y)

        QTimer.singleShot(0, self._apply_glass)

    def _apply_glass(self) -> None:
        glass.apply_glass_to_window(
            self, options=glass.GlassOptions(corner_radius=16.0)
        )
