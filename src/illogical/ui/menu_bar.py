from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenuBar

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow


class MenuBar(QMenuBar):
    backup_now_triggered = Signal()
    restore_backup_triggered = Signal()
    backup_settings_triggered = Signal()

    def __init__(self, main_window: QMainWindow | None = None) -> None:
        super().__init__()
        self._main_window = main_window
        self.setNativeMenuBar(True)
        self._setup_menus()

    def _setup_menus(self) -> None:
        self._setup_file_menu()
        self._setup_edit_menu()
        self._setup_backup_menu()
        self._setup_help_menu()

    def _setup_file_menu(self) -> None:
        file_menu = self.addMenu("File")

        close_action = QAction("Close Window", self)
        close_action.setShortcut(QKeySequence.StandardKey.Close)
        if self._main_window is not None:
            close_action.triggered.connect(self._main_window.close)
        file_menu.addAction(close_action)

    def _setup_edit_menu(self) -> None:
        edit_menu = self.addMenu("Edit")

        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.setEnabled(False)
        edit_menu.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.setEnabled(False)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        cut_action = QAction("Cut", self)
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        edit_menu.addAction(cut_action)

        copy_action = QAction("Copy", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        edit_menu.addAction(copy_action)

        paste_action = QAction("Paste", self)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        edit_menu.addAction(paste_action)

        select_all_action = QAction("Select All", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        edit_menu.addAction(select_all_action)

    def _setup_backup_menu(self) -> None:
        backup_menu = self.addMenu("Backup")

        backup_now_action = QAction("Backup Now", self)
        backup_now_action.setShortcut(QKeySequence("Ctrl+B"))
        backup_now_action.triggered.connect(self.backup_now_triggered)
        backup_menu.addAction(backup_now_action)

        backup_menu.addSeparator()

        restore_action = QAction("Restore Backup...", self)
        restore_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        restore_action.triggered.connect(self.restore_backup_triggered)
        backup_menu.addAction(restore_action)

        backup_menu.addSeparator()

        settings_action = QAction("Backup Settings...", self)
        settings_action.setShortcut(QKeySequence.StandardKey.Preferences)
        settings_action.triggered.connect(self.backup_settings_triggered)
        backup_menu.addAction(settings_action)

    def _setup_help_menu(self) -> None:
        self.addMenu("Help")
