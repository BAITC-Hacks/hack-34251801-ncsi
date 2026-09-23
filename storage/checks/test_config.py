"""Paths are checkout-relative and configuration alone never creates a DB."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from storage import configure_storage


class StorageConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.root_patch = patch("storage.config.ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def test_defaults_do_not_create_directory_or_database(self):
        paths = configure_storage()
        self.assertEqual(paths.data_home, self.root / ".career-quest")
        self.assertEqual(paths.auth_db, paths.data_home / "accounts.sqlite3")
        self.assertEqual(paths.dataset_db, paths.data_home / "dataset.sqlite3")
        self.assertEqual(paths.growth_db, paths.data_home / "growth.sqlite3")
        self.assertFalse(paths.data_home.exists())

    def test_existing_accounts_reused_without_copying(self):
        legacy = self.root / "auth/.local/auth.sqlite3"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"existing-account-database")
        self.assertEqual(configure_storage().auth_db, legacy)
        self.assertFalse((self.root / ".career-quest").exists())

    def test_relative_paths_resolve_against_checkout(self):
        os.environ.update(CAREER_QUEST_DATA_HOME="local-state", CAREER_QUEST_AUTH_DB="custom/accounts.db")
        paths = configure_storage()
        self.assertEqual(paths.auth_db, self.root / "custom/accounts.db")
        self.assertEqual(paths.dataset_db, self.root / "local-state/dataset.sqlite3")
        self.assertEqual(os.environ["CAREER_QUEST_GROWTH_DB"], str(self.root / "local-state/growth.sqlite3"))

    def test_custom_data_home_is_independent_of_legacy_accounts(self):
        legacy = self.root / "auth/.local/auth.sqlite3"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"existing-account-database")
        os.environ["CAREER_QUEST_DATA_HOME"] = "independent-state"
        paths = configure_storage()
        self.assertEqual(paths.auth_db, self.root / "independent-state/accounts.sqlite3")
        self.assertEqual(legacy.read_bytes(), b"existing-account-database")
        self.assertFalse(paths.data_home.exists())

    def test_dotenv_does_not_override_environment_or_interpolate_credentials(self):
        (self.root / ".env").write_text(
            "CAREER_QUEST_DATA_HOME=dotenv-data\nCAREER_QUEST_AUTH_DB=dotenv-auth.db\n"
            "EXAMPLE_CREDENTIAL=literal${OTHER_VALUE}$tail\nOTHER_VALUE=replaced\n", encoding="utf-8"
        )
        os.environ["CAREER_QUEST_AUTH_DB"] = "explicit.db"
        paths = configure_storage()
        self.assertEqual(paths.auth_db, self.root / "explicit.db")
        self.assertEqual(paths.data_home, self.root / "dotenv-data")
        self.assertEqual(os.environ["EXAMPLE_CREDENTIAL"], "literal${OTHER_VALUE}$tail")


if __name__ == "__main__":
    unittest.main()
