from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class BackupTrigger(Enum):
    MANUAL = "manual"
    AUTO = "auto"


class ChangeType(Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


class CategoryChangeType(Enum):
    MOVED = "moved"
    DELETED = "deleted"
    ADDED = "added"


@dataclass
class FieldChange:
    field_name: str
    old_value: str | None
    new_value: str | None


@dataclass
class PluginChange:
    tags_id: str
    plugin_name: str
    change_type: ChangeType
    field_changes: list[FieldChange] = field(default_factory=list)


@dataclass
class CategoryChange:
    old_path: str | None
    new_path: str | None
    change_type: CategoryChangeType


@dataclass
class DetailedBackupChanges:
    plugins: list[PluginChange] = field(default_factory=list)
    categories: list[CategoryChange] = field(default_factory=list)

    @property
    def added(self) -> list[PluginChange]:
        return [p for p in self.plugins if p.change_type == ChangeType.ADDED]

    @property
    def modified(self) -> list[PluginChange]:
        return [p for p in self.plugins if p.change_type == ChangeType.MODIFIED]

    @property
    def deleted(self) -> list[PluginChange]:
        return [p for p in self.plugins if p.change_type == ChangeType.DELETED]

    @property
    def categories_moved(self) -> list[CategoryChange]:
        return [c for c in self.categories if c.change_type == CategoryChangeType.MOVED]

    @property
    def categories_deleted(self) -> list[CategoryChange]:
        return [
            c for c in self.categories if c.change_type == CategoryChangeType.DELETED
        ]

    @property
    def categories_added(self) -> list[CategoryChange]:
        return [c for c in self.categories if c.change_type == CategoryChangeType.ADDED]

    @property
    def is_empty(self) -> bool:
        return len(self.plugins) == 0 and len(self.categories) == 0


@dataclass
class BackupChanges:
    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {"added": self.added, "modified": self.modified, "deleted": self.deleted}

    @classmethod
    def from_dict(cls, data: dict[str, list[str]]) -> BackupChanges:
        return cls(
            added=data.get("added", []),
            modified=data.get("modified", []),
            deleted=data.get("deleted", []),
        )

    @property
    def is_empty(self) -> bool:
        return not self.added and not self.modified and not self.deleted

    @property
    def total_count(self) -> int:
        return len(self.added) + len(self.modified) + len(self.deleted)


@dataclass
class BackupManifest:
    version: int
    timestamp: datetime
    trigger: BackupTrigger
    description: str
    file_count: int
    total_size_bytes: int
    previous_backup: str | None
    changes: BackupChanges
    checksums: dict[str, str]

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "trigger": self.trigger.value,
            "description": self.description,
            "file_count": self.file_count,
            "total_size_bytes": self.total_size_bytes,
            "previous_backup": self.previous_backup,
            "changes": self.changes.to_dict(),
            "checksums": self.checksums,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BackupManifest:
        ts = datetime.fromisoformat(data["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return cls(
            version=data["version"],
            timestamp=ts,
            trigger=BackupTrigger(data["trigger"]),
            description=data.get("description", ""),
            file_count=data["file_count"],
            total_size_bytes=data["total_size_bytes"],
            previous_backup=data.get("previous_backup"),
            changes=BackupChanges.from_dict(data.get("changes", {})),
            checksums=data.get("checksums", {}),
        )


@dataclass
class BackupInfo:
    name: str
    path: Path
    timestamp: datetime
    trigger: BackupTrigger
    file_count: int
    total_size_bytes: int
    description: str = ""

    @property
    def display_name(self) -> str:
        trigger_label = "Manual" if self.trigger == BackupTrigger.MANUAL else "Auto"
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} ({trigger_label})"

    @property
    def size_display(self) -> str:
        return _format_size(self.total_size_bytes)


_BYTES_PER_KB = 1024


def _format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < _BYTES_PER_KB:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= _BYTES_PER_KB
    return f"{size:.1f} TB"


@dataclass
class BackupSettings:
    retention_days: int = 30
    max_backups: int = 100
    auto_purge: bool = True
