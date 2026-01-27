from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QThread, Signal

from illogical.modules import backup_manager
from illogical.modules.backup_models import BackupSettings, BackupTrigger

logger = logging.getLogger(__name__)


class BackupWorker(QObject):
    backup_created = Signal(object)
    backup_list_ready = Signal(list)
    restore_completed = Signal(bool, str)
    changes_computed = Signal(str, object)
    storage_usage_ready = Signal(int, int)
    purge_completed = Signal(int)
    error_occurred = Signal(str)

    def create_backup(
        self, trigger: BackupTrigger = BackupTrigger.MANUAL, description: str = ""
    ) -> None:
        try:
            backup_info = backup_manager.create_backup(trigger, description)
            self.backup_created.emit(backup_info)
        except OSError as e:
            logger.exception("Backup creation failed")
            self.error_occurred.emit(str(e))

    def list_backups(self) -> None:
        try:
            backups = backup_manager.list_backups()
            self.backup_list_ready.emit(backups)
        except OSError as e:
            logger.exception("Listing backups failed")
            self.error_occurred.emit(str(e))

    def restore_backup(self, backup_name: str) -> None:
        try:
            success = backup_manager.restore_backup(backup_name)
            self.restore_completed.emit(success, backup_name)
        except OSError as e:
            logger.exception("Restore failed")
            self.error_occurred.emit(str(e))

    def compute_changes(self, backup_name: str) -> None:
        try:
            changes = backup_manager.compute_changes(backup_name)
            self.changes_computed.emit(backup_name, changes)
        except OSError as e:
            logger.exception("Computing changes failed")
            self.error_occurred.emit(str(e))

    def get_storage_usage(self) -> None:
        try:
            total_bytes, count = backup_manager.get_storage_usage()
            self.storage_usage_ready.emit(total_bytes, count)
        except OSError as e:
            logger.exception("Getting storage usage failed")
            self.error_occurred.emit(str(e))

    def purge_old_backups(self, settings: BackupSettings) -> None:
        try:
            deleted_count = backup_manager.purge_old_backups(settings)
            self.purge_completed.emit(deleted_count)
        except OSError as e:
            logger.exception("Purging backups failed")
            self.error_occurred.emit(str(e))

    def ensure_backup_before_change(self) -> None:
        try:
            if backup_manager.should_create_auto_backup():
                backup_info = backup_manager.create_backup(
                    BackupTrigger.AUTO, "Auto-backup before plugin modification"
                )
                self.backup_created.emit(backup_info)
        except OSError as e:
            logger.exception("Auto-backup before change failed")
            self.error_occurred.emit(str(e))


class BackupService(QObject):
    backup_created = Signal(object)
    backup_list_ready = Signal(list)
    restore_completed = Signal(bool, str)
    changes_computed = Signal(str, object)
    storage_usage_ready = Signal(int, int)
    purge_completed = Signal(int)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread = QThread()
        self._worker = BackupWorker()
        self._worker.moveToThread(self._thread)

        self._worker.backup_created.connect(self.backup_created)
        self._worker.backup_list_ready.connect(self.backup_list_ready)
        self._worker.restore_completed.connect(self.restore_completed)
        self._worker.changes_computed.connect(self.changes_computed)
        self._worker.storage_usage_ready.connect(self.storage_usage_ready)
        self._worker.purge_completed.connect(self.purge_completed)
        self._worker.error_occurred.connect(self.error_occurred)

        self._thread.start()

    def create_backup(
        self, trigger: BackupTrigger = BackupTrigger.MANUAL, description: str = ""
    ) -> None:
        self._worker.create_backup(trigger, description)

    def list_backups(self) -> None:
        self._worker.list_backups()

    def restore_backup(self, backup_name: str) -> None:
        self._worker.restore_backup(backup_name)

    def compute_changes(self, backup_name: str) -> None:
        self._worker.compute_changes(backup_name)

    def get_storage_usage(self) -> None:
        self._worker.get_storage_usage()

    def purge_old_backups(self, settings: BackupSettings) -> None:
        self._worker.purge_old_backups(settings)

    def ensure_backup_before_change(self) -> None:
        self._worker.ensure_backup_before_change()

    def shutdown(self) -> None:
        self._thread.quit()
        self._thread.wait()
