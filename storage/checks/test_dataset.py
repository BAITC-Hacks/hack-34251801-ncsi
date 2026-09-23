"""Durability, concurrent writes and actual starter-kit core persistence."""

import copy
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from core import api
from storage import DatasetStorageError, DatasetStore

ROOT = Path(__file__).resolve().parents[2]
STARTER_KIT = ROOT / "case/case_1/career_quest_dataset"


class DatasetStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "nested/dataset.sqlite3"
        self.store = DatasetStore(self.path)
        self.seed = {"employees": [], "history": [], "as_of_date": "2026-09-30", "custom": {"label": "Данные", "values": [None, True, 1, 1.5]}}

    def test_constructor_and_read_do_not_create_unrequested_database(self):
        self.assertFalse(self.path.exists())
        with self.assertRaisesRegex(DatasetStorageError, "ещё не создана"):
            self.store.read()
        self.assertFalse(self.path.parent.exists())

    def test_seed_once_and_reload_preserves_full_native_document(self):
        loader = Mock(return_value=self.seed)
        initial, revision = self.store.load_or_initialize(loader)
        self.assertEqual((initial, revision), (self.seed, 0))
        initial["custom"]["label"] = "Detached read must not mutate saved state"
        restarted = DatasetStore(self.path)
        never = Mock(side_effect=AssertionError("must not reseed after restart"))
        self.assertEqual(restarted.load_or_initialize(never), (self.seed, 0))
        self.assertEqual(loader.call_count, 1)
        never.assert_not_called()

    def test_failed_seed_rolls_back_then_initialization_can_retry(self):
        with self.assertRaisesRegex(ValueError, "broken loader"):
            self.store.load_or_initialize(Mock(side_effect=ValueError("broken loader")))
        self.assertEqual(self.store.load_or_initialize(lambda: self.seed), (self.seed, 0))

    def test_concurrent_initializers_seed_only_once(self):
        barrier = threading.Barrier(2)
        loader = Mock(return_value=self.seed)

        def initialize():
            barrier.wait(timeout=5)
            return DatasetStore(self.path).load_or_initialize(loader)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(initialize)
            second = pool.submit(initialize)
            self.assertEqual(first.result(timeout=10), (self.seed, 0))
            self.assertEqual(second.result(timeout=10), (self.seed, 0))
        self.assertEqual(loader.call_count, 1)

    def test_concurrent_instances_do_not_lose_updates(self):
        self.store.load_or_initialize(lambda: self.seed)
        barrier = threading.Barrier(2)

        def append_employee(prefix):
            store = DatasetStore(self.path)
            barrier.wait(timeout=5)
            for index in range(8):
                def update(latest):
                    latest["employees"].append({"employee_id": f"{prefix}-{index}"})
                    return latest, len(latest["employees"])
                store.mutate(update)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(append_employee, prefix) for prefix in ("A", "B")]
            for future in futures:
                future.result(timeout=20)
        persisted, revision = self.store.read()
        self.assertEqual(revision, 16)
        self.assertEqual(len({e["employee_id"] for e in persisted["employees"]}), 16)

    def test_callback_exception_does_not_commit_partial_mutation(self):
        self.store.load_or_initialize(lambda: self.seed)

        def fail(dataset):
            dataset["employees"].append({"employee_id": "UNSAVED"})
            raise ValueError("validation failed")

        with self.assertRaisesRegex(ValueError, "validation failed"):
            self.store.mutate(fail)
        self.assertEqual(self.store.read(), (self.seed, 0))
        self.store.mutate(lambda d: (d, "connection lock released"))
        self.assertEqual(self.store.read(), (self.seed, 1))

    def test_invalid_json_values_and_missing_employees_do_not_commit(self):
        self.store.load_or_initialize(lambda: self.seed)
        for bad in (float("nan"), float("inf"), set(), object(), {1: "non-string-key"}, ("tuple",), "\ud800"):
            with self.subTest(value_type=type(bad).__name__):
                def update(dataset):
                    dataset["bad"] = bad
                    return dataset, None
                with self.assertRaises(DatasetStorageError):
                    self.store.mutate(update)
                self.assertEqual(self.store.read(), (self.seed, 0))
        with self.assertRaises(DatasetStorageError):
            self.store.mutate(lambda dataset: ({"history": []}, None))
        self.assertEqual(self.store.read(), (self.seed, 0))

    def test_mutate_requires_existing_initialized_store(self):
        with self.assertRaises(DatasetStorageError):
            self.store.mutate(lambda dataset: (dataset, None))
        self.assertFalse(self.path.exists())

    def test_future_schema_is_refused_and_never_modified(self):
        self.store.load_or_initialize(lambda: self.seed)
        with closing(sqlite3.connect(self.path, isolation_level=None)) as connection:
            connection.execute("UPDATE storage_metadata SET schema_version=999 WHERE id=1")
        loader = Mock(side_effect=AssertionError("must not run loader"))
        for call in (lambda: self.store.load_or_initialize(loader), self.store.read, lambda: self.store.mutate(lambda dataset: (dataset, None))):
            with self.assertRaisesRegex(DatasetStorageError, "Версия"):
                call()
        loader.assert_not_called()
        with closing(sqlite3.connect(self.path, isolation_level=None)) as connection:
            self.assertEqual(connection.execute("SELECT schema_version FROM storage_metadata").fetchone()[0], 999)
            self.assertEqual(json.loads(connection.execute("SELECT document FROM dataset_state").fetchone()[0]), self.seed)

    def test_wrong_database_does_not_gain_dataset_tables(self):
        self.path.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.path, isolation_level=None)) as connection:
            connection.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY)")
        with self.assertRaisesRegex(DatasetStorageError, "другую базу"):
            self.store.load_or_initialize(lambda: self.seed)
        with closing(sqlite3.connect(self.path, isolation_level=None)) as connection:
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [("accounts",)])

    def test_corrupt_document_is_reported_without_reseeding(self):
        self.store.load_or_initialize(lambda: self.seed)
        with closing(sqlite3.connect(self.path, isolation_level=None)) as connection:
            connection.execute("UPDATE dataset_state SET document='not json'")
        with self.assertRaisesRegex(DatasetStorageError, "повреждённые данные"):
            self.store.load_or_initialize(lambda: self.seed)

    def test_real_core_import_completion_restart_and_duplicate_rollback(self):
        with patch.dict(os.environ, {"CAREER_QUEST_AI_PROVIDER": "none"}):
            loaded, revision = self.store.load_or_initialize(lambda: api.load_dataset(str(STARTER_KIT)))
            self.assertEqual(revision, 0)
            profile = copy.deepcopy(loaded["employees"][1])
            profile.update(employee_id="PERSISTENCE-CHECK", full_name="Synthetic persistence verification profile")
            # Same-day baseline changes are particularly important to preserve.
            profile["last_review_date"] = loaded["as_of_date"]
            import_path = Path(self.temp.name) / "employees.json"
            import_path.write_text(json.dumps({"employees": [profile]}), encoding="utf-8")
            updated, revision, result = self.store.mutate(lambda latest: (api.import_test_data(latest, str(import_path)), "imported"))
            self.assertEqual((len(updated["employees"]), revision, result), (201, 1, "imported"))
            before = api.get_employee_view(updated, profile["employee_id"])
            event_id = before["recommendations"][0]["event_id"]

            def complete(latest):
                view = api.complete_activity(latest, profile["employee_id"], event_id)
                return latest, view

            completed, revision, after = self.store.mutate(complete)
            self.assertEqual(revision, 2)
            self.assertGreater(after["trajectory"]["progress_percent"], before["trajectory"]["progress_percent"])
            reloaded, revision = DatasetStore(self.path).load_or_initialize(Mock(side_effect=AssertionError("no reseed")))
            self.assertEqual(reloaded, completed)
            self.assertEqual(api.get_employee_view(reloaded, profile["employee_id"]), after)
            self.assertEqual(reloaded["as_of_date"], loaded["as_of_date"])
            self.assertNotEqual(next(e for e in reloaded["employees"] if e["employee_id"] == profile["employee_id"])["skills"], profile["skills"])
            with self.assertRaises(ValueError):
                self.store.mutate(complete)
            self.assertEqual(self.store.read(), (reloaded, revision))


if __name__ == "__main__":
    unittest.main()
