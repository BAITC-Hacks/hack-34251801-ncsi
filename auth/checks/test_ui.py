"""Streamlit form/session integration against isolated SQLite and real scrypt."""

import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from auth.service import AuthService, SESSION_IDLE_TIMEOUT

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "Проверочная фраза для входа 2026"
EMAIL = "ui.employee@example.test"
TOKEN_KEY = "cq_auth_token"


class AuthUITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / "accounts.sqlite3"
        self.environment = patch.dict(os.environ, {"CAREER_QUEST_AUTH_DB": str(self.db_path)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.service = AuthService()

    def app(self):
        app = AppTest.from_file(str(ROOT / "auth_app.py"), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        return app

    @staticmethod
    def group(app, key):
        return next(widget for widget in app.get("button_group") if widget.key == key)

    @staticmethod
    def field(app, label):
        return next(widget for widget in app.text_input if widget.label == label)

    @staticmethod
    def button(app, label):
        return next(widget for widget in app.button if widget.label == label)

    def signup_form(self, app, email=EMAIL, password=PASSWORD, confirmation=PASSWORD):
        self.group(app, "cq_auth_mode").set_value("Регистрация").run()
        self.field(app, "Имя и фамилия").set_value("Тестовый сотрудник")
        self.field(app, "Рабочая почта").set_value(email)
        self.field(app, "Пароль").set_value(password)
        self.field(app, "Повторите пароль").set_value(confirmation)
        self.button(app, "Создать аккаунт →").click().run()
        self.assertEqual(len(app.exception), 0)

    def login_form(self, app, email=EMAIL, password=PASSWORD, role="employee"):
        self.group(app, "cq_auth_role").set_value(role).run()
        self.field(app, "Рабочая почта").set_value(email)
        self.field(app, "Пароль").set_value(password)
        self.button(app, "Войти в Career Quest →").click().run()
        self.assertEqual(len(app.exception), 0)

    def seed_user(self, role="employee", email=EMAIL):
        self.service.register("Тестовый сотрудник", email, PASSWORD, PASSWORD)
        if role != "employee":
            self.service.assign_role(email, role)

    def test_signup_then_login_then_logout(self):
        app = self.app()
        self.signup_form(app)
        self.assertTrue(any("Аккаунт создан" in item.value for item in app.success))
        self.assertEqual(self.group(app, "cq_auth_mode").value, "Вход")
        self.assertEqual(self.group(app, "cq_auth_role").value, "employee")
        self.assertNotIn(TOKEN_KEY, app.session_state)
        self.login_form(app)
        token = app.session_state[TOKEN_KEY]
        user = self.service.current_user(token)
        self.assertEqual(user["email"], EMAIL)
        self.assertEqual(user["role"], "employee")
        self.assertEqual(len(app.text_input), 0)
        app.button(key="cq_auth_logout").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIsNone(self.service.current_user(token))
        self.assertNotIn(TOKEN_KEY, app.session_state)
        self.assertEqual(self.group(app, "cq_auth_mode").value, "Вход")

    def test_incorrect_password_and_selected_role_are_rejected(self):
        self.seed_user()
        app = self.app()
        self.login_form(app, password="Это неверный пароль")
        self.assertEqual(len(app.error), 1)
        password_message = app.error[0].value
        self.assertNotIn(TOKEN_KEY, app.session_state)
        self.login_form(app, role="admin")
        self.assertEqual(len(app.error), 1)
        self.assertEqual(app.error[0].value, password_message)
        self.assertNotIn(TOKEN_KEY, app.session_state)
        self.assertFalse(any(button.key == "cq_auth_logout" for button in app.button))

    def test_all_three_assigned_roles_can_sign_in(self):
        for role in ("employee", "hr", "admin"):
            with self.subTest(role=role):
                email = f"ui.{role}@example.test"
                self.seed_user(role, email)
                app = self.app()
                self.login_form(app, email=email, role=role)
                self.assertEqual(len(app.error), 0)
                token = app.session_state[TOKEN_KEY]
                self.assertEqual(self.service.current_user(token)["role"], role)
                self.assertTrue(any(button.key == "cq_auth_logout" for button in app.button))

    def test_expired_session_returns_to_login(self):
        self.seed_user()
        app = self.app()
        self.login_form(app)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("UPDATE auth_sessions SET last_seen=?", (time.time() - SESSION_IDLE_TIMEOUT - 1,))
            conn.commit()
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertNotIn(TOKEN_KEY, app.session_state)
        self.assertTrue(any("Сессия завершена" in item.value for item in app.info))
        self.assertEqual(self.group(app, "cq_auth_mode").value, "Вход")
        self.assertFalse(any(button.key == "cq_auth_logout" for button in app.button))

    def test_revoked_session_returns_to_login(self):
        self.seed_user()
        app = self.app()
        self.login_form(app)
        self.service.assign_role(EMAIL, "hr")
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertNotIn(TOKEN_KEY, app.session_state)
        self.assertTrue(any("Сессия завершена" in item.value for item in app.info))
        self.assertEqual(self.group(app, "cq_auth_mode").value, "Вход")
        self.login_form(app, role="hr")
        self.assertEqual(self.service.current_user(app.session_state[TOKEN_KEY])["role"], "hr")

    def test_mismatched_registration_passwords_show_validation(self):
        app = self.app()
        self.signup_form(app, confirmation="Другая фраза для проверки")
        self.assertEqual(len(app.error), 1)
        self.assertIn("Пароли не совпадают", app.error[0].value)
        self.assertEqual(self.group(app, "cq_auth_mode").value, "Регистрация")
        self.assertNotIn(TOKEN_KEY, app.session_state)
        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM auth_users").fetchone()[0], 0)

    def test_initialization_failure_shows_friendly_error(self):
        invalid_parent = Path(self.directory.name) / "not_a_directory"
        invalid_parent.write_text("test", encoding="utf-8")
        with patch.dict(os.environ, {"CAREER_QUEST_AUTH_DB": str(invalid_parent / "auth.sqlite3")}):
            app = self.app()
        self.assertEqual(len(app.error), 1)
        self.assertIn("Сервис входа временно недоступен", app.error[0].value)
        self.assertNotIn(str(invalid_parent), app.error[0].value)
        self.assertEqual(len(app.text_input), 0)

    def test_storage_failure_during_session_validation_hides_account(self):
        self.seed_user()
        app = self.app()
        self.login_form(app)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("ALTER TABLE auth_sessions RENAME COLUMN token_hash TO broken_token_hash")
            conn.commit()
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertIn("Сервис входа временно недоступен", app.error[0].value)
        self.assertFalse(any(button.key == "cq_auth_logout" for button in app.button))


if __name__ == "__main__":
    unittest.main()
