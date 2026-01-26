from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLineEdit, QWidget

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent

from illogical.modules.sf_symbols import sf_symbol

MIN_SEARCH_LENGTH = 1


class SearchBar(QLineEdit):
    search_changed = Signal(str)
    escape_pressed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("Search")
        self.setClearButtonEnabled(True)

        search_icon = sf_symbol("magnifyingglass", 14)
        if not search_icon.isNull():
            self.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)

        self.setStyleSheet("""
            QLineEdit {
                border: none;
                border-radius: 14px;
                padding: 6px 12px 6px 8px;
                background: #302C33;
            }
            QLineEdit:focus {
                border: 2px solid palette(highlight);
            }
        """)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._emit_search)

        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text: str) -> None:
        self._debounce_timer.stop()
        if len(text) >= MIN_SEARCH_LENGTH or len(text) == 0:
            self._debounce_timer.start()

    def _emit_search(self) -> None:
        self.search_changed.emit(self.text())

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            if self.text():
                self.clear()
            else:
                self.escape_pressed.emit()
                self.clearFocus()
            event.accept()
            return
        super().keyPressEvent(event)
