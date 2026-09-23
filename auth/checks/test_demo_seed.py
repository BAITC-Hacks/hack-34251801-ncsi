"""Explicit public demo accounts: atomic creation without overwriting local users."""

import json
import os
import secrets
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from auth.demo_seed import DEMO_ACCOUNTS, DEMO_PASSWORD, seed_demo_accounts
from auth.service import AuthError, AuthService, _derive_key
from ui.persistent_adapter import PersistentAdapter


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "case/case_1/career_quest_dataset"
PRIVATE_PASSWORD = "Only a private local test password 2026"
EXPECTED_ACCOUNTS = {
    "employee1@careerquest.test": ("employee", "E0001"),
    "employee2@careerquest.test": ("employee", "E0002"),
    "hr@careerquest.test": ("hr", None),
    "admin@careerquest.test": ("admin", None),
}


class DemoSeedTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        self.path = self.folder / "accounts.sqlite3"
        environment = patch.dict(os.environ, {
            "CAREER_QUEST_DATA_HOME": str(self.folder),
            "CAREER_QUEST_AUTH_DB": str(self.path),
            "CAREER_QUEST_DATASET_DB": str(self.folder / "dataset.sqlite3"),
            "CAREER_QUEST_GROWTH_DB": str(self.folder / "growth.sqlite3"),
            "CAREER_QUEST_AI_PROVIDER": "none", "OPENAI_API_KEY": "", "NVIDIA_API_KEY": "",
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.service = AuthService(self.path)
        self.employees = json.loads((DATA_DIR / "employees.json").read_text(encoding="utf-8-sig"))["employees"]

    def rows(self, sql):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql)]

    def test_explicit_seed_creates_four_login_accounts_with_expected_ownership(self):
        self.assertFalse(self.service.has_admin())
        self.assertEqual(self.rows("SELECT * FROM auth_users"), [])
        self.assertEqual(DEMO_PASSWORD, "CareerQuest2026!")
        self.assertEqual({account["email"] for account in DEMO_ACCOUNTS}, set(EXPECTED_ACCOUNTS))
        result = seed_demo_accounts(self.service, self.employees)
        self.assertEqual({user["email"] for user in result["created"]}, set(EXPECTED_ACCOUNTS))
        self.assertEqual(result["existing"], [])
        self.assertTrue(self.service.has_admin())
        safe_fields = {"user_id", "name", "email", "role", "active", "employee_id"}
        hashes = set()
        salts = set()
        for row in self.rows("SELECT * FROM auth_users"):
            hashes.add(row["password_hash"])
            salts.add(row["password_salt"])
        self.assertEqual(len(hashes), 4)
        self.assertEqual(len(salts), 4)
        for email, (role, profile) in EXPECTED_ACCOUNTS.items():
            with self.subTest(email=email):
                token, user = self.service.login(email, DEMO_PASSWORD, role)
                self.assertEqual(set(user), safe_fields)
                self.assertEqual(user["employee_id"], profile)
                self.assertEqual(user["role"], role)
                adapter = PersistentAdapter(DATA_DIR, self.service, token)
                dataset = adapter.load_dataset()
                visible = adapter.list_employees(dataset)
                if role == "employee":
                    self.assertEqual([employee["employee_id"] for employee in visible], [profile])
                    other = "E0002" if profile == "E0001" else "E0001"
                    with self.assertRaises(PermissionError):
                        adapter.get_employee_view(dataset, other)
                    with self.assertRaises(PermissionError):
                        adapter.get_hr_view(dataset)
                else:
                    self.assertEqual(len(visible), len(self.employees))
        self.assertNotIn(DEMO_PASSWORD.encode(), self.path.read_bytes())

    def test_repeat_preserves_ids_hashes_sessions_and_edited_role_password(self):
        seed_demo_accounts(self.service, self.employees)
        changed = self.service.assign_role("employee1@careerquest.test", "hr")
        salt = secrets.token_bytes(32)
        password_hash = _derive_key(PRIVATE_PASSWORD, salt)
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                "UPDATE auth_users SET password_salt=?,password_hash=?,name=? WHERE user_id=?",
                (salt, password_hash, "Изменённое имя", changed["user_id"]),
            )
            conn.commit()
        token, _ = self.service.login(changed["email"], PRIVATE_PASSWORD, "hr")
        before_users = self.rows("SELECT * FROM auth_users ORDER BY user_id")
        before_sessions = self.rows("SELECT * FROM auth_sessions ORDER BY user_id")
        result = seed_demo_accounts(AuthService(self.path), self.employees)
        self.assertEqual(result["created"], [])
        self.assertEqual({user["email"] for user in result["existing"]}, set(EXPECTED_ACCOUNTS))
        self.assertEqual(self.rows("SELECT * FROM auth_users ORDER BY user_id"), before_users)
        self.assertEqual(self.rows("SELECT * FROM auth_sessions ORDER BY user_id"), before_sessions)
        current = self.service.current_user(token)
        self.assertEqual(current["role"], "hr")
        self.assertEqual(current["name"], "Изменённое имя")
        self.assertEqual(self.service.login(changed["email"], PRIVATE_PASSWORD, "hr")[1]["role"], "hr")

    def test_unmarked_email_conflict_does_not_replace_account_or_seed_partial_rows(self):
        existing = self.service.register("Чужой локальный аккаунт", "employee2@careerquest.test", PRIVATE_PASSWORD, PRIVATE_PASSWORD)
        token, _ = self.service.login(existing["email"], PRIVATE_PASSWORD)
        before = self.rows("SELECT * FROM auth_users")
        with self.assertRaises(AuthError):
            seed_demo_accounts(self.service, self.employees)
        self.assertEqual(self.rows("SELECT * FROM auth_users"), before)
        self.assertEqual(self.service.current_user(token), existing)
        self.assertFalse(self.service.has_admin())

    def test_profile_conflict_does_not_take_an_existing_binding_or_add_accounts(self):
        admin = self.service.create_admin("Локальный администратор", "local-admin@example.test", PRIVATE_PASSWORD, PRIVATE_PASSWORD)
        token, _ = self.service.login(admin["email"], PRIVATE_PASSWORD, "admin")
        owner = self.service.register("Владелец профиля", "owner@example.test", PRIVATE_PASSWORD, PRIVATE_PASSWORD)
        self.service.configure_user(token, owner["user_id"], "employee", "E0002", {"E0001", "E0002"})
        before = self.rows("SELECT * FROM auth_users ORDER BY user_id")
        with self.assertRaises(AuthError):
            seed_demo_accounts(self.service, self.employees)
        self.assertEqual(self.rows("SELECT * FROM auth_users ORDER BY user_id"), before)
        self.assertEqual(self.service.login(owner["email"], PRIVATE_PASSWORD)[1]["employee_id"], "E0002")

    def test_missing_required_profile_leaves_database_without_accounts(self):
        for employees in ([], [employee for employee in self.employees if employee["employee_id"] != "E0002"]):
            with self.subTest(profiles=len(employees)), self.assertRaises(AuthError):
                seed_demo_accounts(self.service, employees)
            self.assertEqual(self.rows("SELECT * FROM auth_users"), [])
            self.assertFalse(self.service.has_admin())

    def test_storage_failure_rolls_back_all_accounts_and_all_seed_markers(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("""CREATE TRIGGER reject_demo_hr BEFORE INSERT ON auth_users
                WHEN NEW.email='hr@careerquest.test'
                BEGIN SELECT RAISE(ABORT, 'synthetic seed failure'); END""")
            conn.commit()
        with self.assertRaises(AuthError):
            seed_demo_accounts(self.service, self.employees)
        self.assertEqual(self.rows("SELECT * FROM auth_users"), [])
        marker_table = self.rows("SELECT name FROM sqlite_master WHERE type='table' AND name='auth_demo_accounts'")
        if marker_table:
            self.assertEqual(self.rows("SELECT * FROM auth_demo_accounts"), [])
        # A clean retry after recovery must still create every demo account.
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("DROP TRIGGER reject_demo_hr")
            conn.commit()
        self.assertEqual(len(seed_demo_accounts(self.service, self.employees)["created"]), 4)


if __name__ == "__main__":
    unittest.main()
