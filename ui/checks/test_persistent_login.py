"""Real first-run/login forms and SQLite persistence across independent sessions."""

import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from auth.service import AuthService
from auth.ui import TOKEN_KEY


ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "Локальная проверочная фраза 2026"
ADMIN_EMAIL = "admin@local.example"
EMPLOYEE_EMAIL = "employee@local.example"


class PersistentLoginTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.data_home = Path(directory.name)
        self.auth_path = self.data_home / "accounts.sqlite3"
        self.environment = patch.dict(os.environ, {
            "CAREER_QUEST_DEMO_MODE": "0",
            "CAREER_QUEST_DATA_HOME": str(self.data_home),
            "CAREER_QUEST_AUTH_DB": str(self.auth_path),
            "CAREER_QUEST_DATASET_DB": str(self.data_home / "dataset.sqlite3"),
            "CAREER_QUEST_GROWTH_DB": str(self.data_home / "growth.sqlite3"),
            "CAREER_QUEST_DATA_DIR": str(ROOT / "case/case_1/career_quest_dataset"),
            "CAREER_QUEST_AI_PROVIDER": "none", "OPENAI_API_KEY": "", "NVIDIA_API_KEY": "",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def clean(self, app):
        self.assertFalse(app.exception, [item.value for item in app.exception])
        self.assertFalse(app.error, [item.value for item in app.error])
        return app

    def app(self):
        return self.clean(AppTest.from_file(str(ROOT / "app.py"), default_timeout=40).run())

    @staticmethod
    def field(app, label):
        return next(widget for widget in app.text_input if widget.label == label)

    @staticmethod
    def button(app, label):
        return next(widget for widget in app.button if widget.label == label)

    @staticmethod
    def group(app, key):
        return next(widget for widget in app.get("button_group") if widget.key == key)

    @staticmethod
    def select(app, label):
        return next(widget for widget in app.selectbox if widget.label == label)

    def bootstrap(self):
        app = self.app()
        self.assertFalse((self.data_home / "dataset.sqlite3").exists())
        self.field(app, "Имя и фамилия").set_value("Локальный администратор")
        self.field(app, "Рабочая почта").set_value(ADMIN_EMAIL)
        self.field(app, "Пароль").set_value(PASSWORD)
        self.field(app, "Повторите пароль").set_value(PASSWORD)
        self.button(app, "Создать пространство →").click().run()
        self.clean(app)
        self.assertTrue(AuthService(self.auth_path).has_admin())
        return app

    def logout(self, app):
        token = app.session_state[TOKEN_KEY]
        app.button(key="cq_auth_logout").click().run()
        self.clean(app)
        self.assertIsNone(AuthService(self.auth_path).current_user(token))
        self.assertNotIn(TOKEN_KEY, app.session_state)

    def login(self, app, email=EMPLOYEE_EMAIL, role="employee"):
        self.assertFalse(any(widget.key == "cq_auth_role" for widget in app.get("button_group")))
        self.field(app, "Рабочая почта").set_value(email)
        self.field(app, "Пароль").set_value(PASSWORD)
        self.button(app, "Войти в Career Quest →").click().run()
        self.clean(app)
        user = AuthService(self.auth_path).current_user(app.session_state[TOKEN_KEY])
        self.assertEqual(user["role"], role)
        return app

    def register(self, app, email=EMPLOYEE_EMAIL):
        self.group(app, "cq_auth_mode").set_value("Регистрация").run()
        self.field(app, "Имя и фамилия").set_value("Локальный сотрудник")
        self.field(app, "Рабочая почта").set_value(email)
        self.field(app, "Пароль").set_value(PASSWORD)
        self.field(app, "Повторите пароль").set_value(PASSWORD)
        self.button(app, "Создать аккаунт →").click().run()
        self.clean(app)
        self.assertTrue(any("Аккаунт создан" in item.value for item in app.success))

    def configure_in_ui(self, app, user_id, role="employee", profile=None):
        app.radio(key="admin_page").set_value("Пользователи").run()
        app.selectbox(key="account_to_manage").select(user_id).run()
        self.select(app, "Роль аккаунта").select(role)
        self.select(app, "Профиль сотрудника").select(profile)
        self.button(app, "Сохранить доступ").click().run()
        self.clean(app)

    def test_first_run_creates_local_admin_and_admin_sections(self):
        app = self.bootstrap()
        user = AuthService(self.auth_path).current_user(app.session_state[TOKEN_KEY])
        self.assertEqual(user["email"], ADMIN_EMAIL)
        self.assertEqual(user["role"], "admin")
        self.assertIsNone(user["employee_id"])
        self.assertEqual(app.radio(key="admin_page").options,
                         ["Пользователи", "Импорт данных", "Состояние приложения"])
        self.assertEqual(len(app.selectbox(key="account_to_manage").options), 1)
        self.assertTrue((self.data_home / "dataset.sqlite3").exists())
        app.radio(key="admin_page").set_value("Импорт данных").run()
        self.clean(app)
        self.assertEqual(len(app.get("file_uploader")), 2)
        app.radio(key="admin_page").set_value("Состояние приложения").run()
        self.clean(app)
        self.assertFalse(app.tabs)
        self.assertFalse(app.slider)
        self.logout(app)
        fresh = self.app()
        self.assertFalse(any(button.label == "Создать пространство →" for button in fresh.button))
        self.login(fresh, ADMIN_EMAIL, "admin")
        self.assertEqual(len(fresh.selectbox(key="account_to_manage").options), 1)

    def test_admin_logout_stays_outside_sidebar_in_every_section_and_clears_session(self):
        app = self.bootstrap()
        token = app.session_state[TOKEN_KEY]
        for section in ("Пользователи", "Импорт данных", "Состояние приложения"):
            with self.subTest(section=section):
                app.radio(key="admin_page").set_value(section).run()
                self.clean(app)
                self.assertFalse(any(button.key == "cq_auth_logout" for button in app.sidebar.button))
                self.assertEqual(app.button(key="cq_auth_logout").label, "Выйти из аккаунта")
                self.assertFalse(app.button(key="cq_auth_logout").disabled)
        # Session-only state must disappear alongside the revoked token, while
        # persistent data is already covered by the restart regression below.
        self.assertIn("dataset", app.session_state)
        self.assertIn("views", app.session_state)
        app.session_state["employee_id"] = "E0002"
        app.session_state["pending_employee"] = "E0003"
        app.session_state["cq_auth_role"] = "admin"
        app.button(key="cq_auth_logout").click().run()
        self.clean(app)
        self.assertIsNone(AuthService(self.auth_path).current_user(token))
        for key in (TOKEN_KEY, "dataset", "views", "revision", "cq_account_context",
                    "employee_id", "pending_employee", "cq_auth_role"):
            self.assertNotIn(key, app.session_state)
        self.assertFalse(app.sidebar.button)
        self.assertFalse(any(button.key == "cq_auth_logout" for button in app.button))
        self.assertFalse(any(widget.key == "cq_auth_role" for widget in app.get("button_group")))
        self.assertEqual({field.label for field in app.text_input}, {"Рабочая почта", "Пароль"})
        self.assertTrue(any(button.label == "Войти в Career Quest →" for button in app.button))

    def test_registration_waits_for_admin_profile_assignment_and_enforces_ownership(self):
        admin_app = self.bootstrap()
        employee_app = self.app()
        self.register(employee_app)
        employee_app.session_state["cq_auth_role"] = "admin"
        self.login(employee_app)
        service = AuthService(self.auth_path)
        old_token = employee_app.session_state[TOKEN_KEY]
        user = service.current_user(old_token)
        self.assertEqual(user["role"], "employee")
        self.assertIsNone(user["employee_id"])
        self.assertTrue(any("Пока профиль не назначен" in item.value for item in employee_app.info))
        self.assertFalse(employee_app.tabs)
        self.assertFalse(employee_app.dataframe)
        self.assertFalse(employee_app.get("file_uploader"))
        employee_app.session_state["employee_id"] = "E0001"
        employee_app.run()
        self.clean(employee_app)
        self.assertFalse(employee_app.tabs)
        self.configure_in_ui(admin_app, user["user_id"], profile="E0002")
        self.assertIsNone(service.current_user(old_token))
        employee_app.run()
        self.clean(employee_app)
        self.assertNotIn(TOKEN_KEY, employee_app.session_state)
        self.login(employee_app)
        self.assertEqual(service.current_user(employee_app.session_state[TOKEN_KEY])["employee_id"], "E0002")
        self.assertEqual({tab.label for tab in employee_app.tabs}, {
            "Профиль и опыт", "Треки и курсы", "Мои сертификаты", "Мой маршрут",
            "Карта развития", "Навыки и требования", "История участия",
        })
        self.assertFalse(any(widget.key == "employee_id" for widget in employee_app.selectbox))
        employee_app.session_state["employee_id"] = "E0003"
        employee_app.session_state["pending_employee"] = "E0004"
        employee_app.session_state["mode"] = "HR"
        employee_app.run()
        self.clean(employee_app)
        view = employee_app.session_state["views"][(employee_app.session_state["revision"], "E0002")]
        self.assertEqual(view["employee"]["employee_id"], "E0002")
        self.assertFalse(employee_app.get("file_uploader"))
        self.assertFalse(any(widget.key == "admin_page" for widget in employee_app.radio))

    def test_admin_assigns_hr_role_and_hr_sees_team_sections(self):
        admin_app = self.bootstrap()
        hr_app = self.app()
        hr_email = "hr@local.example"
        self.register(hr_app, hr_email)
        service = AuthService(self.auth_path)
        users = service.list_users(admin_app.session_state[TOKEN_KEY])
        user = next(user for user in users if user["email"] == hr_email)
        self.configure_in_ui(admin_app, user["user_id"], role="hr")
        self.login(hr_app, hr_email, "hr")
        self.assertEqual({tab.label for tab in hr_app.tabs}, {"Заявки и решения", "Оценка сотрудника", "Обзор команды"})
        self.assertEqual(len(hr_app.selectbox(key="employee_id").options), 200)
        hr_app.selectbox(key="employee_id").select("E0200").run()
        # AppTest does not yet expose stateful tab clicks; set only the tab key.
        hr_app.session_state["hr_tab"] = "Оценка сотрудника"
        hr_app.run()
        self.clean(hr_app)
        self.assertEqual(len(hr_app.slider), 6)
        self.assertTrue(any(button.label == "Сохранить профиль HR" for button in hr_app.button))
        self.assertFalse(hr_app.get("file_uploader"))
        self.assertFalse(any(widget.key == "admin_page" for widget in hr_app.radio))
        self.logout(hr_app)

    def test_completed_activity_and_binding_survive_new_app_session(self):
        admin_app = self.bootstrap()
        service = AuthService(self.auth_path)
        employee = service.register("Сотрудник", EMPLOYEE_EMAIL, PASSWORD, PASSWORD)
        self.configure_in_ui(admin_app, employee["user_id"], profile="E0002")
        employee_app = self.login(self.app())
        employee_app.session_state["employee_tab"] = "Мой маршрут"
        employee_app.run()
        before = deepcopy(employee_app.session_state["views"][(employee_app.session_state["revision"], "E0002")])
        event_id = before["recommendations"][0]["event_id"]
        employee_app.button(key=f"complete-E0002-{event_id}").click().run()
        self.clean(employee_app)
        after = deepcopy(employee_app.session_state["views"][(employee_app.session_state["revision"], "E0002")])
        self.assertGreater(after["trajectory"]["progress_pct"], before["trajectory"]["progress_pct"])
        self.logout(employee_app)
        restarted = self.app()
        self.assertNotIn(TOKEN_KEY, restarted.session_state)
        self.login(restarted)
        restored = restarted.session_state["views"][(restarted.session_state["revision"], "E0002")]
        self.assertEqual(restored["trajectory"], after["trajectory"])
        self.assertEqual(restored["history"], after["history"])
        self.assertEqual(service.current_user(restarted.session_state[TOKEN_KEY])["employee_id"], "E0002")


if __name__ == "__main__":
    unittest.main()
