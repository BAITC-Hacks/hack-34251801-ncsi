"""Persistent profile links, upgrade migration and atomic administrator actions."""

import secrets
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from auth.service import (
    AuthError, AuthService, SESSION_IDLE_TIMEOUT, SESSION_MAX_AGE, _derive_key,
)


PASSWORD = "Локальный тест аккаунтов 2026"
CATALOG = {"E0001", "E0002", "IMPORTED_001"}


class ProfileAccountsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "accounts.sqlite3"
        self.service = AuthService(self.path)

    def admin(self):
        user = self.service.create_admin("Администратор", "admin@example.test", PASSWORD, PASSWORD)
        token, _ = self.service.login(user["email"], PASSWORD, "admin")
        return token, user

    def employee(self, address="employee@example.test"):
        return self.service.register("Сотрудник", address, PASSWORD, PASSWORD)

    def configure(self, token, user, employee_id=None, role="employee"):
        return self.service.configure_user(token, user["user_id"], role, employee_id, CATALOG)

    def test_upgrade_preserves_legacy_password_and_account(self):
        legacy_path = self.path.parent / "legacy.sqlite3"
        salt = secrets.token_bytes(32)
        password_hash = _derive_key(PASSWORD, salt)
        with closing(sqlite3.connect(legacy_path)) as conn:
            conn.execute("""CREATE TABLE auth_users (
                user_id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
                password_salt BLOB NOT NULL, password_hash BLOB NOT NULL,
                password_version INTEGER NOT NULL DEFAULT 1, role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL
            )""")
            conn.execute(
                "INSERT INTO auth_users VALUES(?,?,?,?,?,?,?,?,?)",
                ("legacy-id", "Существующий", "old@example.test", salt, password_hash, 1, "employee", 1, 1),
            )
            conn.commit()
        upgraded = AuthService(legacy_path)
        token, user = upgraded.login("old@example.test", PASSWORD)
        self.assertIsNone(user["employee_id"])
        self.assertEqual(user["user_id"], "legacy-id")
        self.assertEqual(AuthService(legacy_path).current_user(token), user)
        with closing(sqlite3.connect(legacy_path)) as conn:
            self.assertEqual(conn.execute("SELECT password_hash FROM auth_users").fetchone()[0], password_hash)
            self.assertIsNotNone(conn.execute("SELECT name FROM sqlite_master WHERE name='auth_users_employee'").fetchone())

    def test_first_admin_bootstrap_is_atomic_and_not_reopened_by_inactivation(self):
        self.assertFalse(self.service.has_admin())

        def bootstrap(number):
            try:
                return AuthService(self.path).create_admin("Администратор", f"admin{number}@example.test", PASSWORD, PASSWORD)
            except AuthError:
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            users = list(executor.map(bootstrap, [1, 2]))
        self.assertEqual(sum(user is not None for user in users), 1)
        self.assertTrue(self.service.has_admin())
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("UPDATE auth_users SET active=0")
            conn.commit()
        self.assertTrue(AuthService(self.path).has_admin())
        with self.assertRaises(AuthError):
            self.service.create_admin("Администратор", "third@example.test", PASSWORD, PASSWORD)

    def test_registration_stays_unbound_and_user_list_has_no_secrets(self):
        token, admin = self.admin()
        employee = self.employee()
        second = self.employee("second@example.test")
        users = self.service.list_users(token)
        self.assertEqual({user["user_id"] for user in users}, {admin["user_id"], employee["user_id"], second["user_id"]})
        expected = {"user_id", "name", "email", "role", "active", "employee_id"}
        for user in users:
            self.assertEqual(set(user), expected)
            self.assertIsNone(user["employee_id"])
        self.assertEqual(employee["role"], "employee")

    def test_employee_hr_and_forged_sessions_cannot_list_or_configure(self):
        admin_token, _ = self.admin()
        employee = self.employee()
        hr = self.employee("hr@example.test")
        self.configure(admin_token, hr, role="hr")
        employee_token, _ = self.service.login(employee["email"], PASSWORD)
        hr_token, _ = self.service.login(hr["email"], PASSWORD, "hr")
        for token in (None, "forged", secrets.token_urlsafe(32), employee_token, hr_token):
            with self.subTest(token=type(token).__name__):
                with self.assertRaises(AuthError):
                    self.service.list_users(token)
                with self.assertRaises(AuthError):
                    self.configure(token, employee, "E0001", "admin")
        self.assertIsNone(self.service.current_user(employee_token)["employee_id"])
        self.assertEqual(self.service.current_user(employee_token)["role"], "employee")

    def test_authorization_rechecks_current_role_and_active_in_database(self):
        token, admin = self.admin()
        employee = self.employee()
        for field, value in (("role", "hr"), ("active", 0)):
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute("UPDATE auth_users SET role='admin',active=1 WHERE user_id=?", (admin["user_id"],))
                conn.execute(f"UPDATE auth_users SET {field}=? WHERE user_id=?", (value, admin["user_id"]))
                conn.commit()
            with self.assertRaises(AuthError):
                self.service.list_users(token)
            with self.assertRaises(AuthError):
                self.configure(token, employee, "E0001")

    def test_admin_actions_reject_idle_absolute_and_revoked_sessions(self):
        _, admin = self.admin()
        employee = self.employee()
        with patch("auth.service.time.time", return_value=100000) as clock:
            for duration in (SESSION_IDLE_TIMEOUT, SESSION_MAX_AGE):
                clock.return_value = 100000
                token, _ = self.service.login(admin["email"], PASSWORD, "admin")
                # For the absolute-expiry case, make last_seen fresh so the test
                # specifically exercises expires_at rather than the idle guard.
                if duration == SESSION_MAX_AGE:
                    with closing(sqlite3.connect(self.path)) as conn:
                        conn.execute("UPDATE auth_sessions SET last_seen=?", (100000 + duration,))
                        conn.commit()
                clock.return_value = 100000 + duration
                with self.assertRaises(AuthError):
                    self.service.list_users(token)
                with self.assertRaises(AuthError):
                    self.configure(token, employee, "E0001")
            clock.return_value = 200000
            token, _ = self.service.login(admin["email"], PASSWORD, "admin")
            self.service.logout(token)
            with self.assertRaises(AuthError):
                self.configure(token, employee, "E0001")

    def test_profile_binding_persists_and_revokes_all_old_sessions(self):
        token, _ = self.admin()
        employee = self.employee()
        old_tokens = [self.service.login(employee["email"], PASSWORD)[0] for _ in range(2)]
        configured = self.configure(token, employee, "E0001")
        self.assertEqual(configured["employee_id"], "E0001")
        restarted = AuthService(self.path)
        for old_token in old_tokens:
            self.assertIsNone(restarted.current_user(old_token))
        fresh_token, fresh_user = restarted.login(employee["email"], PASSWORD)
        self.assertEqual(fresh_user["employee_id"], "E0001")
        self.configure(token, employee, "E0001")
        self.assertIsNotNone(restarted.current_user(fresh_token))
        self.configure(token, employee, "IMPORTED_001")
        self.assertIsNone(restarted.current_user(fresh_token))
        self.assertEqual(restarted.login(employee["email"], PASSWORD)[1]["employee_id"], "IMPORTED_001")

    def test_unknown_profiles_and_invalid_roles_leave_account_and_session_unchanged(self):
        token, _ = self.admin()
        employee = self.employee()
        employee_token, _ = self.service.login(employee["email"], PASSWORD)
        for profile in ("UNKNOWN", "", " E0001 ", 7):
            with self.subTest(profile=profile), self.assertRaises(AuthError):
                self.configure(token, employee, profile)
        for role in ("owner", "", None, []):
            with self.subTest(role=role), self.assertRaises(AuthError):
                self.configure(token, employee, role=role)
        with self.assertRaises(AuthError):
            self.service.configure_user(token, "missing-id", "hr", None, CATALOG)
        self.assertEqual(self.service.current_user(employee_token), employee)

    def test_duplicate_profile_is_rejected_atomically_and_can_be_reassigned_after_unbind(self):
        token, _ = self.admin()
        first = self.employee()
        second = self.employee("second@example.test")
        self.configure(token, first, "E0001")
        second_token, _ = self.service.login(second["email"], PASSWORD)
        with self.assertRaisesRegex(AuthError, "уже привязан"):
            self.configure(token, second, "E0001", "hr")
        self.assertEqual(self.service.current_user(second_token), second)
        self.configure(token, first, None)
        self.assertEqual(self.configure(token, second, "E0001")["employee_id"], "E0001")
        self.assertIsNone(self.service.current_user(second_token))

    def test_concurrent_binding_keeps_one_owner(self):
        token, _ = self.admin()
        employees = [self.employee(), self.employee("second@example.test")]

        def bind(employee):
            try:
                return AuthService(self.path).configure_user(token, employee["user_id"], "employee", "E0001", CATALOG)
            except AuthError:
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(bind, employees))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(sum(user["employee_id"] == "E0001" for user in self.service.list_users(token)), 1)

    def test_role_change_revokes_sessions_and_last_admin_guard_is_retained(self):
        token, admin = self.admin()
        employee = self.employee()
        employee_token, _ = self.service.login(employee["email"], PASSWORD)
        with self.assertRaisesRegex(AuthError, "последнего"):
            self.configure(token, admin, role="hr")
        self.assertIsNotNone(self.service.current_user(token))
        self.configure(token, employee, role="admin")
        self.assertIsNone(self.service.current_user(employee_token))
        self.configure(token, admin, role="hr")
        self.assertIsNone(self.service.current_user(token))
        new_admin_token, _ = self.service.login(employee["email"], PASSWORD, "admin")
        self.assertEqual(len(self.service.list_users(new_admin_token)), 2)


if __name__ == "__main__":
    unittest.main()
