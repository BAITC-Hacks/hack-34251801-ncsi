"""Resolve local storage without opening or creating any database."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class StoragePaths:
    data_home: Path
    auth_db: Path
    dataset_db: Path
    growth_db: Path


def _absolute_path(value: str | Path) -> Path:
    # Relative configuration belongs to this checkout, independent of the shell cwd.
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def configure_storage() -> StoragePaths:
    """Load optional .env and set stable absolute paths for all local stores.

    Explicit process environment wins over .env. Interpolation is disabled so
    values containing dollar signs (including API credentials) stay unchanged.
    Existing installations retain the previous account database under the default
    data home. An explicit different data home creates an independent workspace.
    """
    load_dotenv(ROOT / ".env", override=False, interpolate=False)
    data_home = _absolute_path(os.environ.get("CAREER_QUEST_DATA_HOME") or ROOT / ".career-quest")
    os.environ["CAREER_QUEST_DATA_HOME"] = str(data_home)
    legacy_accounts = ROOT / "auth" / ".local" / "auth.sqlite3"
    reuse_legacy = data_home == (ROOT / ".career-quest").resolve() and legacy_accounts.is_file()
    defaults = {
        "CAREER_QUEST_AUTH_DB": legacy_accounts if reuse_legacy else data_home / "accounts.sqlite3",
        "CAREER_QUEST_DATASET_DB": data_home / "dataset.sqlite3",
        "CAREER_QUEST_GROWTH_DB": data_home / "growth.sqlite3",
    }
    resolved = {}
    for name, default in defaults.items():
        resolved[name] = _absolute_path(os.environ.get(name) or default)
        os.environ[name] = str(resolved[name])
    return StoragePaths(
        data_home=data_home,
        auth_db=resolved["CAREER_QUEST_AUTH_DB"],
        dataset_db=resolved["CAREER_QUEST_DATASET_DB"],
        growth_db=resolved["CAREER_QUEST_GROWTH_DB"],
    )
