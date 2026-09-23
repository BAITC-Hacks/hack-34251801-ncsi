"""Local, self-contained persistence for Career Quest."""

from .config import StoragePaths, configure_storage
from .dataset import DatasetStorageError, DatasetStore

__all__ = ["DatasetStorageError", "DatasetStore", "StoragePaths", "configure_storage"]
