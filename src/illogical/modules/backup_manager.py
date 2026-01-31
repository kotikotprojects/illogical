from __future__ import annotations

import hashlib
import json
import plistlib
import shutil
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from logic_plugin_manager.defaults import tags_path

from illogical.modules.backup_models import (
    BackupChanges,
    BackupInfo,
    BackupManifest,
    BackupSettings,
    BackupTrigger,
    CategoryChange,
    CategoryChangeType,
    ChangeType,
    DetailedBackupChanges,
    FieldChange,
    PluginChange,
)

if TYPE_CHECKING:
    from pathlib import Path

    from logic_plugin_manager import Logic

MANIFEST_VERSION = 1
MANIFEST_FILENAME = "manifest.json"
BACKUP_INDEX_FILENAME = ".backup_index.json"

TAGS_PATH = tags_path
BACKUPS_PATH = tags_path.parent / ".nothing_to_see_here_just_illogical_saving_ur_ass"
MUSICAPPS_PROPERTIES = "MusicApps.properties"


def _compute_file_checksum(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"


def _get_backup_files() -> list[Path]:
    if not TAGS_PATH.exists():
        return []
    return [f for f in TAGS_PATH.iterdir() if f.is_file()]


def _generate_backup_name(trigger: BackupTrigger) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    return f"{timestamp}_{trigger.value}"


def _load_manifest(backup_path: Path) -> BackupManifest | None:
    manifest_file = backup_path / MANIFEST_FILENAME
    if not manifest_file.exists():
        return None
    try:
        with manifest_file.open() as f:
            return BackupManifest.from_dict(json.load(f))
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _save_manifest(backup_path: Path, manifest: BackupManifest) -> None:
    manifest_file = backup_path / MANIFEST_FILENAME
    with manifest_file.open("w") as f:
        json.dump(manifest.to_dict(), f, indent=2)


def _get_latest_backup() -> BackupInfo | None:
    backups = list_backups()
    return backups[0] if backups else None


def _compute_changes_between(
    current_files: dict[str, str], previous_files: dict[str, str]
) -> BackupChanges:
    added = [f for f in current_files if f not in previous_files]
    deleted = [f for f in previous_files if f not in current_files]
    modified = [
        f
        for f in current_files
        if f in previous_files and current_files[f] != previous_files[f]
    ]
    return BackupChanges(added=added, modified=modified, deleted=deleted)


def create_backup(
    trigger: BackupTrigger = BackupTrigger.MANUAL, description: str = ""
) -> BackupInfo:
    BACKUPS_PATH.mkdir(parents=True, exist_ok=True)

    backup_name = _generate_backup_name(trigger)
    backup_path = BACKUPS_PATH / backup_name
    backup_path.mkdir()

    source_files = _get_backup_files()
    checksums: dict[str, str] = {}
    total_size = 0

    for src_file in source_files:
        dst_file = backup_path / src_file.name
        shutil.copy2(src_file, dst_file)
        checksums[src_file.name] = _compute_file_checksum(src_file)
        total_size += src_file.stat().st_size

    latest = _get_latest_backup()
    previous_backup = latest.name if latest else None

    if latest:
        previous_manifest = _load_manifest(latest.path)
        if previous_manifest:
            changes = _compute_changes_between(checksums, previous_manifest.checksums)
        else:
            changes = BackupChanges()
    else:
        changes = BackupChanges(added=list(checksums.keys()))

    manifest = BackupManifest(
        version=MANIFEST_VERSION,
        timestamp=datetime.now(UTC),
        trigger=trigger,
        description=description,
        file_count=len(source_files),
        total_size_bytes=total_size,
        previous_backup=previous_backup,
        changes=changes,
        checksums=checksums,
    )
    _save_manifest(backup_path, manifest)

    return BackupInfo(
        name=backup_name,
        path=backup_path,
        timestamp=manifest.timestamp,
        trigger=trigger,
        file_count=manifest.file_count,
        total_size_bytes=manifest.total_size_bytes,
        description=description,
    )


def list_backups() -> list[BackupInfo]:
    if not BACKUPS_PATH.exists():
        return []

    backups: list[BackupInfo] = []
    for backup_dir in BACKUPS_PATH.iterdir():
        if not backup_dir.is_dir() or backup_dir.name.startswith("."):
            continue

        manifest = _load_manifest(backup_dir)
        if manifest:
            backups.append(
                BackupInfo(
                    name=backup_dir.name,
                    path=backup_dir,
                    timestamp=manifest.timestamp,
                    trigger=manifest.trigger,
                    file_count=manifest.file_count,
                    total_size_bytes=manifest.total_size_bytes,
                    description=manifest.description,
                )
            )
        else:
            try:
                parts = backup_dir.name.rsplit("_", 1)
                timestamp_str = parts[0]
                trigger_str = parts[1] if len(parts) > 1 else "manual"
                timestamp = datetime.strptime(
                    timestamp_str, "%Y-%m-%d_%H-%M-%S"
                ).replace(tzinfo=UTC)
                trigger = BackupTrigger(trigger_str)
            except (ValueError, IndexError):
                continue

            files = list(backup_dir.glob("*"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            backups.append(
                BackupInfo(
                    name=backup_dir.name,
                    path=backup_dir,
                    timestamp=timestamp,
                    trigger=trigger,
                    file_count=len(files),
                    total_size_bytes=total_size,
                )
            )

    backups.sort(key=lambda b: b.timestamp, reverse=True)
    return backups


def compute_changes(backup_name: str) -> BackupChanges:
    backup_path = BACKUPS_PATH / backup_name
    if not backup_path.exists():
        return BackupChanges()

    backup_manifest = _load_manifest(backup_path)
    if not backup_manifest:
        return BackupChanges()

    current_files = _get_backup_files()
    current_checksums = {f.name: _compute_file_checksum(f) for f in current_files}
    backup_checksums = backup_manifest.checksums

    added = [f for f in current_checksums if f not in backup_checksums]
    deleted = [f for f in backup_checksums if f not in current_checksums]
    modified = [
        f
        for f in current_checksums
        if f in backup_checksums and current_checksums[f] != backup_checksums[f]
    ]

    return BackupChanges(added=added, modified=modified, deleted=deleted)


def restore_backup(backup_name: str) -> bool:
    backup_path = BACKUPS_PATH / backup_name
    if not backup_path.exists():
        return False

    create_backup(BackupTrigger.AUTO, f"Auto-backup before restoring {backup_name}")

    for existing_file in TAGS_PATH.iterdir():
        if existing_file.is_file():
            existing_file.unlink()

    for backup_file in backup_path.iterdir():
        if backup_file.is_file() and backup_file.name != MANIFEST_FILENAME:
            shutil.copy2(backup_file, TAGS_PATH / backup_file.name)

    return True


def purge_old_backups(settings: BackupSettings) -> int:
    if not BACKUPS_PATH.exists():
        return 0

    backups = list_backups()
    if not backups:
        return 0

    to_delete: list[BackupInfo] = []
    cutoff_date = datetime.now(UTC) - timedelta(days=settings.retention_days)

    for i, backup in enumerate(backups):
        if i >= settings.max_backups or (
            settings.retention_days > 0 and backup.timestamp < cutoff_date
        ):
            to_delete.append(backup)

    for backup in to_delete:
        shutil.rmtree(backup.path)

    return len(to_delete)


def get_storage_usage() -> tuple[int, int]:
    if not BACKUPS_PATH.exists():
        return (0, 0)

    total_bytes = 0
    count = 0

    for backup_dir in BACKUPS_PATH.iterdir():
        if not backup_dir.is_dir() or backup_dir.name.startswith("."):
            continue
        count += 1
        for file in backup_dir.iterdir():
            if file.is_file():
                total_bytes += file.stat().st_size

    return (total_bytes, count)


def get_last_auto_backup_time() -> datetime | None:
    backups = list_backups()
    for backup in backups:
        if backup.trigger == BackupTrigger.AUTO:
            return backup.timestamp
    return None


def should_create_auto_backup(min_interval_seconds: int = 300) -> bool:
    last_auto = get_last_auto_backup_time()
    if last_auto is None:
        return True
    elapsed = (datetime.now(UTC) - last_auto).total_seconds()
    return elapsed >= min_interval_seconds


def _parse_tagset_plist(path: Path) -> dict | None:
    try:
        with path.open("rb") as f:
            return plistlib.load(f)
    except Exception:  # noqa: BLE001
        return None


def _compute_field_changes(
    old_data: dict | None, new_data: dict | None
) -> list[FieldChange]:
    changes: list[FieldChange] = []

    old_data = old_data or {}
    new_data = new_data or {}

    backup_nickname = old_data.get("nickname", "")
    current_nickname = new_data.get("nickname", "")
    if backup_nickname != current_nickname:
        changes.append(
            FieldChange("nickname", current_nickname or None, backup_nickname or None)
        )

    backup_shortname = old_data.get("shortname", "")
    current_shortname = new_data.get("shortname", "")
    if backup_shortname != current_shortname:
        changes.append(
            FieldChange(
                "shortname", current_shortname or None, backup_shortname or None
            )
        )

    backup_tags = set(old_data.get("tags", {}).keys())
    current_tags = set(new_data.get("tags", {}).keys())

    changes.extend(
        FieldChange(f"category:{tag}", None, "removed")
        for tag in current_tags - backup_tags
    )
    changes.extend(
        FieldChange(f"category:{tag}", None, "added")
        for tag in backup_tags - current_tags
    )

    return changes


def _resolve_plugin_name(tags_id: str, logic: Logic | None) -> str:
    if logic is None:
        return tags_id
    plugin = logic.plugins.get_by_tags_id(tags_id)
    if plugin:
        return plugin.name
    return tags_id


def _tags_id_from_filename(filename: str) -> str:
    return filename.removesuffix(".tagset")


def _parse_musicapps_sorting(path: Path) -> list[str]:
    props_file = path / MUSICAPPS_PROPERTIES
    if not props_file.exists():
        return []
    try:
        with props_file.open("rb") as f:
            data = plistlib.load(f)
        return data.get("sorting", [])
    except Exception:  # noqa: BLE001
        return []


def _compute_category_changes(
    backup_sorting: list[str], current_sorting: list[str]
) -> list[CategoryChange]:
    changes: list[CategoryChange] = []
    backup_set = set(backup_sorting)
    current_set = set(current_sorting)

    moved_new_paths: set[str] = set()

    for old_path in backup_set - current_set:
        base_name = old_path.split(":")[-1]
        moved_to = next(
            (c for c in current_set - backup_set if c.split(":")[-1] == base_name), None
        )
        if moved_to:
            changes.append(CategoryChange(old_path, moved_to, CategoryChangeType.MOVED))
            moved_new_paths.add(moved_to)
        else:
            changes.append(CategoryChange(old_path, None, CategoryChangeType.DELETED))

    changes.extend(
        CategoryChange(None, new_path, CategoryChangeType.ADDED)
        for new_path in current_set - backup_set
        if new_path not in moved_new_paths
    )

    return changes


def compute_detailed_changes(
    backup_name: str, logic: Logic | None = None
) -> DetailedBackupChanges:
    backup_path = BACKUPS_PATH / backup_name
    if not backup_path.exists():
        return DetailedBackupChanges()

    backup_manifest = _load_manifest(backup_path)
    if not backup_manifest:
        return DetailedBackupChanges()

    current_files = _get_backup_files()
    current_checksums = {f.name: _compute_file_checksum(f) for f in current_files}
    backup_checksums = backup_manifest.checksums

    added_files = [f for f in current_checksums if f not in backup_checksums]
    deleted_files = [f for f in backup_checksums if f not in current_checksums]
    modified_files = [
        f
        for f in current_checksums
        if f in backup_checksums and current_checksums[f] != backup_checksums[f]
    ]

    plugin_changes: list[PluginChange] = []

    for filename in added_files:
        tags_id = _tags_id_from_filename(filename)
        plugin_name = _resolve_plugin_name(tags_id, logic)
        plugin_changes.append(PluginChange(tags_id, plugin_name, ChangeType.ADDED))

    for filename in deleted_files:
        tags_id = _tags_id_from_filename(filename)
        plugin_name = _resolve_plugin_name(tags_id, logic)
        plugin_changes.append(PluginChange(tags_id, plugin_name, ChangeType.DELETED))

    for filename in modified_files:
        tags_id = _tags_id_from_filename(filename)
        plugin_name = _resolve_plugin_name(tags_id, logic)

        current_path = TAGS_PATH / filename
        backup_file_path = backup_path / filename

        current_data = _parse_tagset_plist(current_path)
        backup_data = _parse_tagset_plist(backup_file_path)

        field_changes = _compute_field_changes(backup_data, current_data)

        plugin_changes.append(
            PluginChange(tags_id, plugin_name, ChangeType.MODIFIED, field_changes)
        )

    backup_sorting = _parse_musicapps_sorting(backup_path)
    current_sorting = _parse_musicapps_sorting(TAGS_PATH)
    category_changes = _compute_category_changes(backup_sorting, current_sorting)

    return DetailedBackupChanges(plugins=plugin_changes, categories=category_changes)
