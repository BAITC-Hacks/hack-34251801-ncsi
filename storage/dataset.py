"""Atomic persistence around core's unchanged native dataset contract.

The complete dataset is stored as JSON. No grade, skill or recommendation
calculations live here: every mutation is delegated to its supplied callback.
An immediate SQLite transaction rereads the latest document before updating it,
so independent Streamlit sessions cannot overwrite one another's progress.
"""

from __future__ import annotations

import json
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

from .config import ROOT, configure_storage

SCHEMA_VERSION = 1
T = TypeVar("T")


class DatasetStorageError(ValueError):
    """A safe, actionable storage message suitable for the application UI."""


def _json_native(value: Any) -> bool:
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(_json_native(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and _json_native(item) for key, item in value.items())
    return False


def _encode(dataset: dict) -> str:
    try:
        if not isinstance(dataset, dict) or not isinstance(dataset.get("employees"), list) or not _json_native(dataset):
            raise DatasetStorageError("Изменения не сохранены: движок должен вернуть dataset с массивом employees и корректными JSON-значениями.")
        document = json.dumps(dataset, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        document.encode("utf-8")
        return document
    except (TypeError, OverflowError, RecursionError, UnicodeError) as exc:
        raise DatasetStorageError("Изменения не сохранены: данные не удалось преобразовать в JSON.") from exc


def _decode(body: str) -> dict:
    try:
        dataset = json.loads(body)
        if not isinstance(dataset, dict) or not isinstance(dataset.get("employees"), list) or not _json_native(dataset):
            raise ValueError("Invalid dataset document")
        return dataset
    except (ValueError, TypeError, RecursionError) as exc:
        raise DatasetStorageError("Локальная база профилей содержит повреждённые данные. Восстановите её из резервной копии; стартовый набор не перезаписывает сохранённые данные.") from exc


class DatasetStore:
    def __init__(self, path: str | Path | None = None):
        configured = configure_storage().dataset_db if path is None else Path(path).expanduser()
        self.path = (configured if configured.is_absolute() else ROOT / configured).resolve()

    @contextmanager
    def _connection(self, *, create: bool = False) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            if create:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            elif not self.path.is_file():
                raise DatasetStorageError("Локальная база профилей ещё не создана. Откройте приложение для первой загрузки стартового набора.")
            # mode=rw prevents a missing/deleted database from becoming an empty file.
            database = str(self.path) if create else self.path.as_uri() + "?mode=rw"
            connection = sqlite3.connect(database, timeout=10, isolation_level=None, uri=not create)
            connection.execute("PRAGMA busy_timeout=10000")
            yield connection
        except (sqlite3.Error, OSError) as exc:
            raise DatasetStorageError("Локальная база профилей недоступна. Проверьте доступ к папке данных и повторите попытку; ваши изменения не сохранены.") from exc
        finally:
            if connection is not None:
                # An explicit rollback also covers exceptions from the caller's callback.
                try:
                    if connection.in_transaction:
                        connection.rollback()
                finally:
                    connection.close()

    @staticmethod
    def _check_version(connection: sqlite3.Connection) -> None:
        row = connection.execute("SELECT schema_version FROM storage_metadata WHERE id=1").fetchone()
        if row is None or type(row[0]) is not int or row[0] != SCHEMA_VERSION:
            raise DatasetStorageError("Версия локальной базы профилей не поддерживается. Используйте совместимую версию Career Quest; база не была изменена.")

    @staticmethod
    def _read(connection: sqlite3.Connection) -> tuple[dict, int]:
        row = connection.execute("SELECT document, revision FROM dataset_state WHERE id=1").fetchone()
        if row is None:
            raise DatasetStorageError("Локальная база профилей не инициализирована. Откройте приложение для загрузки стартового набора.")
        if type(row[1]) is not int or row[1] < 0:
            raise DatasetStorageError("В локальной базе профилей повреждена версия данных. Восстановите резервную копию.")
        return _decode(row[0]), row[1]

    def load_or_initialize(self, loader: Callable[[], dict]) -> tuple[dict, int]:
        """Seed once from loader, or read persisted data without invoking loader."""
        with self._connection(create=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            metadata_exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='storage_metadata'"
            ).fetchone()
            if metadata_exists:
                self._check_version(connection)
            else:
                existing_tables = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
                if existing_tables:
                    raise DatasetStorageError("Выбранный файл содержит другую базу. Укажите отдельный файл CAREER_QUEST_DATASET_DB.")
                connection.execute("CREATE TABLE storage_metadata (id INTEGER PRIMARY KEY CHECK(id=1), schema_version INTEGER NOT NULL)")
                connection.execute("INSERT INTO storage_metadata VALUES (1, ?)", (SCHEMA_VERSION,))
                connection.execute("CREATE TABLE dataset_state (id INTEGER PRIMARY KEY CHECK(id=1), document TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=0))")
            row = connection.execute("SELECT 1 FROM dataset_state WHERE id=1").fetchone()
            if row is None:
                document = _encode(loader())
                connection.execute("INSERT INTO dataset_state VALUES (1, ?, 0)", (document,))
            result = self._read(connection)
            connection.commit()
            return result

    def read(self) -> tuple[dict, int]:
        """Return a detached copy of the latest persisted dataset and revision."""
        with self._connection() as connection:
            self._check_version(connection)
            return self._read(connection)

    def mutate(self, callback: Callable[[dict], tuple[dict, T]]) -> tuple[dict, int, T]:
        """Atomically run callback(latest) -> (updated dataset, result).

        Callback and JSON errors roll the transaction back. Core validation errors
        propagate unchanged so the application can show its existing explanations.
        """
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._check_version(connection)
            dataset, revision = self._read(connection)
            updated, result = callback(dataset)
            document = _encode(updated)
            revision += 1
            connection.execute("UPDATE dataset_state SET document=?, revision=? WHERE id=1", (document, revision))
            connection.commit()
            return _decode(document), revision, result
