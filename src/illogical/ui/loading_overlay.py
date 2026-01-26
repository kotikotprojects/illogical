from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from PySide6.QtGui import QResizeEvent, QShowEvent


class LoadingOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, on=False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._spinner = QProgressBar()
        self._spinner.setRange(0, 0)
        self._spinner.setFixedWidth(200)

        self._label = QLabel("Discovering plugins...")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._spinner)
        layout.addSpacing(12)
        layout.addWidget(self._label)

    def set_message(self, message: str) -> None:
        self._label.setText(message)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        parent = self.parent()
        if parent is not None:
            self.resize(cast("QWidget", parent).size())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        parent = self.parent()
        if parent is not None:
            self.resize(cast("QWidget", parent).size())
