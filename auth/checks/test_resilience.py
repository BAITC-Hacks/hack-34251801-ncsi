"""Cooldown cost and graceful hashing failures, using isolated local databases."""

import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from auth.service import AuthError, AuthService, LOGIN_MAX_FAILURES, LOGIN_WINDOW


PASSWORD = "Тестовая длинная фраза resilience"
EMAIL = "resilience@example.test"


class AuthResilienceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "auth.sqlite3"
        self.service = AuthService(self.path)

    def register(self):
        return self.service.register("Тест устойчивости", EMAIL, PASSWORD, PASSWORD)

    def count(self, table):
        self.assertIn(table, {"auth_users", "auth_sessions", "auth_login_limits"})
        with closing(sqlite3.connect(self.path)) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def lock_with_failed_attempts(self, email):
        message = None
        for _ in range(LOGIN_MAX_FAILURES):
            with self.assertRaises(AuthError) as caught:
                self.service.login(email, "incorrect", "employee")
            message = str(caught.exception)
        return message

    def test_known_cooldown_skips_hash_after_restart_and_expires(self):
        self.register()
        with patch("auth.service.time.time", return_value=100000) as now:
            expected_error = self.lock_with_failed_attempts(EMAIL)
            restarted = AuthService(self.path)
            with patch("auth.service.hashlib.scrypt") as costly_hash:
                for _ in range(3):
                    with self.assertRaises(AuthError) as caught:
                        restarted.login(" RESILIENCE@EXAMPLE.TEST ", PASSWORD, "employee")
                    self.assertEqual(str(caught.exception), expected_error)
                costly_hash.assert_not_called()
            self.assertEqual(self.count("auth_sessions"), 0)
            now.return_value += LOGIN_WINDOW
            token, user = restarted.login(EMAIL, PASSWORD, "employee")
            self.assertEqual(restarted.current_user(token), user)

    def test_unknown_email_cooldown_also_skips_hash(self):
        with patch("auth.service.time.time", return_value=100000):
            expected_error = self.lock_with_failed_attempts(EMAIL)
            with patch("auth.service.hashlib.scrypt") as costly_hash:
                with self.assertRaises(AuthError) as caught:
                    AuthService(self.path).login(EMAIL, PASSWORD, "employee")
                self.assertEqual(str(caught.exception), expected_error)
                costly_hash.assert_not_called()
        self.assertEqual(self.count("auth_users"), 0)
        self.assertEqual(self.count("auth_sessions"), 0)

    def test_cooldown_started_during_hash_is_rechecked_before_session_creation(self):
        self.register()
        original_scrypt = hashlib.scrypt

        def hash_then_concurrently_lock(*args, **kwargs):
            result = original_scrypt(*args, **kwargs)
            # Another request reaches the limit after this login's cheap check.
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute(
                    "INSERT INTO auth_login_limits(identifier_hash,failures,window_started,locked_until) VALUES(?,?,?,?)",
                    (hashlib.sha256(EMAIL.encode()).digest(), LOGIN_MAX_FAILURES, 100000, 100000 + LOGIN_WINDOW),
                )
                conn.commit()
            return result

        with patch("auth.service.time.time", return_value=100000), \
             patch("auth.service.hashlib.scrypt", side_effect=hash_then_concurrently_lock):
            with self.assertRaises(AuthError):
                self.service.login(EMAIL, PASSWORD, "employee")
        self.assertEqual(self.count("auth_sessions"), 0)
        self.assertEqual(self.count("auth_login_limits"), 1)

    def test_registration_hash_failures_are_safe_and_leave_no_partial_account(self):
        for error_type in (ValueError, MemoryError, OSError):
            with self.subTest(error=error_type.__name__):
                with patch("auth.service.hashlib.scrypt", side_effect=error_type("internal hashing diagnostic")):
                    with self.assertRaises(AuthError) as caught:
                        self.register()
                self.assertNotIn("internal hashing diagnostic", str(caught.exception))
                self.assertTrue(caught.exception.__suppress_context__)
                self.assertEqual(self.count("auth_users"), 0)
                self.assertEqual(self.count("auth_sessions"), 0)
        # Failure must release the shared slot so normal work can continue.
        self.assertEqual(self.register()["role"], "employee")

    def test_login_hash_failures_are_safe_without_creating_sessions_or_penalties(self):
        self.register()
        for error_type in (ValueError, MemoryError, OSError):
            with self.subTest(error=error_type.__name__):
                with patch("auth.service.hashlib.scrypt", side_effect=error_type("internal hashing diagnostic")):
                    with self.assertRaises(AuthError) as caught:
                        self.service.login(EMAIL, PASSWORD, "employee")
                self.assertNotIn("internal hashing diagnostic", str(caught.exception))
                self.assertTrue(caught.exception.__suppress_context__)
                self.assertEqual(self.count("auth_sessions"), 0)
                self.assertEqual(self.count("auth_login_limits"), 0)
        token, user = self.service.login(EMAIL, PASSWORD, "employee")
        self.assertEqual(self.service.current_user(token), user)


if __name__ == "__main__":
    unittest.main()
