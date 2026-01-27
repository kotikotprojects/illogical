from __future__ import annotations

from PySide6.QtCore import QSettings

from illogical.modules.backup_models import BackupSettings

_BACKUP_RETENTION_DAYS = "backup/retention_days"
_BACKUP_MAX_COUNT = "backup/max_count"
_BACKUP_AUTO_PURGE = "backup/auto_purge"


class Settings:
    def __init__(self) -> None:
        self._settings = QSettings("com.kotikot.illogical", "illogical")

    @property
    def backup_retention_days(self) -> int:
        value = self._settings.value(_BACKUP_RETENTION_DAYS, 30)
        return int(str(value)) if value is not None else 30

    @backup_retention_days.setter
    def backup_retention_days(self, value: int) -> None:
        self._settings.setValue(_BACKUP_RETENTION_DAYS, value)

    @property
    def backup_max_count(self) -> int:
        value = self._settings.value(_BACKUP_MAX_COUNT, 100)
        return int(str(value)) if value is not None else 100

    @backup_max_count.setter
    def backup_max_count(self, value: int) -> None:
        self._settings.setValue(_BACKUP_MAX_COUNT, value)

    @property
    def backup_auto_purge(self) -> bool:
        default_value = True
        value = self._settings.value(_BACKUP_AUTO_PURGE, default_value, type=bool)  # type: ignore[call-overload]
        return bool(value)

    @backup_auto_purge.setter
    def backup_auto_purge(self, value: bool) -> None:
        self._settings.setValue(_BACKUP_AUTO_PURGE, value)

    def get_backup_settings(self) -> BackupSettings:
        return BackupSettings(
            retention_days=self.backup_retention_days,
            max_backups=self.backup_max_count,
            auto_purge=self.backup_auto_purge,
        )

    def save_backup_settings(self, settings: BackupSettings) -> None:
        self.backup_retention_days = settings.retention_days
        self.backup_max_count = settings.max_backups
        self.backup_auto_purge = settings.auto_purge
