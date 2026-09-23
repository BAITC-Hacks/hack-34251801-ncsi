"""Real SQLite/scrypt checks; test users live only in temporary directories."""

import hashlib
import io
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from auth.manage import main
from auth.service import AuthError, AuthService, LOGIN_WINDOW, SESSION_IDLE_TIMEOUT, SESSION_MAX_AGE

PASSWORD = "Только тестовая фраза 2026"


class AuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "auth.sqlite3"
        self.service = AuthService(self.path)

    def register(self, email="employee@example.test", password=PASSWORD):
        return self.service.register("Тестовый сотрудник", email, password, password)

    def rows(self, sql, parameters=()):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(sql, parameters).fetchall()

    def test_salted_passwords_and_only_token_digest_are_stored(self):
        first = self.register()
        self.register("second@example.test")
        rows = self.rows("SELECT * FROM auth_users ORDER BY email")
        self.assertNotEqual(rows[0]["password_salt"], rows[1]["password_salt"])
        self.assertNotEqual(rows[0]["password_hash"], rows[1]["password_hash"])
        self.assertEqual(len(rows[0]["password_hash"]), 64)
        token, user = self.service.login(first["email"], PASSWORD, "employee")
        self.assertEqual(user, first)
        self.assertEqual(set(user), {"user_id", "name", "email", "role", "active", "employee_id"})
        self.assertIsNone(user["employee_id"])
        session = self.rows("SELECT * FROM auth_sessions")[0]
        self.assertEqual(session["token_hash"], hashlib.sha256(token.encode()).digest())
        database = self.path.read_bytes()
        self.assertNotIn(PASSWORD.encode(), database)
        self.assertNotIn(token.encode(), database)
        self.assertEqual(self.service.current_user(token), user)

    def test_email_normalization_and_unique_registration(self):
        user = self.register(" Employee@Example.Test ")
        self.assertEqual(user["email"], "employee@example.test")
        with self.assertRaises(AuthError):
            self.register("EMPLOYEE@example.test")
        self.assertEqual(len(self.rows("SELECT * FROM auth_users")), 1)
        _, authenticated = self.service.login(" EMPLOYEE@EXAMPLE.TEST ", PASSWORD, "employee")
        self.assertEqual(authenticated["user_id"], user["user_id"])

    def test_validation_does_not_create_partial_accounts(self):
        cases = [
            ("A", "test@example.test", PASSWORD, PASSWORD),
            ("Иван", "bad-email", PASSWORD, PASSWORD),
            ("Иван", "x..x@example.test", PASSWORD, PASSWORD),
            ("Иван", "x@-example.test", PASSWORD, PASSWORD),
            ("Иван", "x@example.test", "short", "short"),
            ("Иван", "x@example.test", "x" * 129, "x" * 129),
            ("Иван", "x@example.test", PASSWORD, "different"),
            ("Иван\nСкрытый", "x@example.test", PASSWORD, PASSWORD),
        ]
        for args in cases:
            with self.subTest(args=args[:2]), self.assertRaises(AuthError):
                self.service.register(*args)
        self.assertEqual(self.rows("SELECT * FROM auth_users"), [])

    def test_unicode_passphrase_preserves_spaces(self):
        password = "  Қазақша құпия сөйлем 🔑  "
        self.register(password=password)
        token, _ = self.service.login("employee@example.test", password, "employee")
        self.assertIsNotNone(self.service.current_user(token))
        with self.assertRaises(AuthError):
            self.service.login("employee@example.test", password.strip(), "employee")

    def test_role_selection_cannot_grant_access(self):
        self.register()
        with self.assertRaises(AuthError) as wrong_role:
            self.service.login("employee@example.test", PASSWORD, "admin")
        with self.assertRaises(AuthError) as wrong_password:
            self.service.login("employee@example.test", "incorrect", "employee")
        self.assertEqual(str(wrong_role.exception), str(wrong_password.exception))
        self.assertEqual(self.rows("SELECT role FROM auth_users")[0]["role"], "employee")
        self.assertEqual(self.rows("SELECT * FROM auth_sessions"), [])
        with self.assertRaises(TypeError):
            self.service.register("Имя", "other@example.test", PASSWORD, PASSWORD, role="admin")

    def test_default_login_automatically_uses_stored_role_for_all_account_types(self):
        for role in ("employee", "hr", "admin"):
            with self.subTest(role=role):
                email = f"auto.{role}@example.test"
                self.register(email)
                if role != "employee":
                    self.service.assign_role(email, role)
                token, user = self.service.login(email, PASSWORD)
                self.assertEqual(user["role"], role)
                self.assertEqual(self.service.current_user(token)["role"], role)

    def test_automatic_login_returns_latest_role_changed_while_hashing(self):
        self.register()
        original_scrypt = hashlib.scrypt

        def hash_then_change_role(*args, **kwargs):
            result = original_scrypt(*args, **kwargs)
            self.service.assign_role("employee@example.test", "hr")
            return result

        with patch("auth.service.hashlib.scrypt", side_effect=hash_then_change_role):
            token, user = self.service.login("employee@example.test", PASSWORD)
        self.assertEqual(user["role"], "hr")
        self.assertEqual(self.service.current_user(token)["role"], "hr")

    def test_unknown_and_inactive_account_have_same_generic_error(self):
        self.register()
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("UPDATE auth_users SET active=0")
            conn.commit()
        messages = []
        for email in ["employee@example.test", "unknown@example.test", "invalid email"]:
            with self.assertRaises(AuthError) as error:
                self.service.login(email, PASSWORD, "employee")
            messages.append(str(error.exception))
        self.assertEqual(len(set(messages)), 1)

    def test_login_cooldown_persists_across_service_instances_and_expires(self):
        self.register()
        with patch("auth.service.time.time", return_value=100000) as now:
            for _ in range(5):
                with self.assertRaises(AuthError):
                    self.service.login("EMPLOYEE@example.test", "wrong", "employee")
            second_service = AuthService(self.path)
            with self.assertRaises(AuthError):
                second_service.login("employee@example.test", PASSWORD, "employee")
            now.return_value += LOGIN_WINDOW + 1
            token, _ = second_service.login("employee@example.test", PASSWORD, "employee")
            self.assertIsNotNone(second_service.current_user(token))
        self.assertEqual(self.rows("SELECT * FROM auth_login_limits"), [])

    def test_unknown_email_uses_same_persistent_failure_counter(self):
        with self.assertRaises(AuthError):
            self.service.login("unknown@example.test", PASSWORD, "employee")
        counter = self.rows("SELECT * FROM auth_login_limits")[0]
        self.assertEqual(counter["failures"], 1)
        self.assertEqual(counter["identifier_hash"], hashlib.sha256(b"unknown@example.test").digest())

    def test_success_clears_failed_attempts(self):
        self.register()
        with self.assertRaises(AuthError):
            self.service.login("employee@example.test", "wrong", "employee")
        self.service.login("employee@example.test", PASSWORD, "employee")
        self.assertEqual(self.rows("SELECT * FROM auth_login_limits"), [])

    def test_session_expires_after_inactivity(self):
        self.register()
        with patch("auth.service.time.time", return_value=200000) as now:
            token, _ = self.service.login("employee@example.test", PASSWORD, "employee")
            now.return_value += SESSION_IDLE_TIMEOUT - 1
            self.assertIsNotNone(self.service.current_user(token))
            now.return_value += SESSION_IDLE_TIMEOUT + 1
            self.assertIsNone(self.service.current_user(token))
        self.assertEqual(self.rows("SELECT * FROM auth_sessions"), [])

    def test_absolute_session_expiry_even_with_continuous_use(self):
        self.register()
        with patch("auth.service.time.time", return_value=200000) as now:
            token, _ = self.service.login("employee@example.test", PASSWORD, "employee")
            for moment in range(200000 + 900, 200000 + SESSION_MAX_AGE, 900):
                now.return_value = moment
                self.assertIsNotNone(self.service.current_user(token))
            now.return_value = 200000 + SESSION_MAX_AGE
            self.assertIsNone(self.service.current_user(token))

    def test_logout_revokes_token_and_repeated_logout_is_safe(self):
        self.register()
        token, _ = self.service.login("employee@example.test", PASSWORD, "employee")
        self.service.logout(token)
        self.assertIsNone(AuthService(self.path).current_user(token))
        self.service.logout(token)
        self.service.logout("forged")
        for value in ["", "forged", None, "x" * 100000]:
            self.assertIsNone(self.service.current_user(value))

    def test_role_change_revokes_all_existing_sessions_and_uses_new_role(self):
        self.register()
        token1, _ = self.service.login("employee@example.test", PASSWORD, "employee")
        token2, _ = self.service.login("employee@example.test", PASSWORD, "employee")
        updated = self.service.assign_role("employee@example.test", "hr")
        self.assertEqual(updated["role"], "hr")
        self.assertIsNone(self.service.current_user(token1))
        self.assertIsNone(self.service.current_user(token2))
        with self.assertRaises(AuthError):
            self.service.login("employee@example.test", PASSWORD, "employee")
        token, user = self.service.login("employee@example.test", PASSWORD, "hr")
        self.assertEqual(user["role"], "hr")
        self.assertEqual(self.service.current_user(token)["role"], "hr")

    def test_inactive_account_invalidates_session(self):
        self.register()
        token, _ = self.service.login("employee@example.test", PASSWORD, "employee")
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("UPDATE auth_users SET active=0")
            conn.commit()
        self.assertIsNone(self.service.current_user(token))
        self.assertEqual(self.rows("SELECT * FROM auth_sessions"), [])

    def test_first_admin_bootstrap_and_last_admin_protection(self):
        admin = self.service.create_admin("Администратор", "admin@example.test", PASSWORD, PASSWORD)
        self.assertEqual(admin["role"], "admin")
        with self.assertRaises(AuthError):
            self.service.create_admin("Второй", "second@example.test", PASSWORD, PASSWORD)
        with self.assertRaises(AuthError):
            self.service.assign_role("admin@example.test", "employee")
        self.register()
        self.service.assign_role("employee@example.test", "admin")
        self.service.assign_role("admin@example.test", "employee")
        token, user = self.service.login("employee@example.test", PASSWORD, "admin")
        self.assertEqual(self.service.current_user(token), user)

    def test_concurrent_duplicate_signup_creates_exactly_one_account(self):
        def attempt(_):
            try:
                return AuthService(self.path).register("Имя", "same@example.test", PASSWORD, PASSWORD)
            except AuthError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(len(self.rows("SELECT * FROM auth_users")), 1)

    def test_input_cannot_inject_sql(self):
        self.register()
        with self.assertRaises(AuthError):
            self.service.login("' OR 1=1;--@example.test", PASSWORD, "admin")
        self.assertEqual(len(self.rows("SELECT * FROM auth_users")), 1)
        self.assertEqual(self.rows("SELECT * FROM auth_sessions"), [])

    def test_cli_bootstrap_uses_hidden_input_and_role_change(self):
        output = io.StringIO()
        with patch("builtins.input", side_effect=["Админ", "admin@example.test"]), \
             patch("auth.manage.getpass.getpass", side_effect=[PASSWORD, PASSWORD]) as hidden, \
             redirect_stdout(output):
            result = main(["--db", str(self.path), "create-admin"])
        self.assertEqual(result, 0)
        self.assertEqual(hidden.call_count, 2)
        self.assertNotIn(PASSWORD, output.getvalue())
        self.register()
        with redirect_stdout(output):
            self.assertEqual(main(["--db", str(self.path), "set-role", "--email", "employee@example.test", "--role", "hr"]), 0)
        self.assertEqual(self.rows("SELECT role FROM auth_users WHERE email='employee@example.test'")[0]["role"], "hr")
        with redirect_stderr(output):
            self.assertEqual(main(["--db", str(self.path), "set-role", "--email", "missing@example.test", "--role", "hr"]), 1)


if __name__ == "__main__":
    unittest.main()
