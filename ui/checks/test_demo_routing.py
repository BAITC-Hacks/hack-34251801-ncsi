"""Integrated presentation-role routing through real demo-entry widgets."""

import io
import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from streamlit.runtime.state.session_state_proxy import SessionStateProxy
from ui.checks.demo_login_helpers import (
    demo_login, demo_logout, employee_tab, hr_tab,
    isolate_demo_storage, switch_demo_role,
)


ROOT = Path(__file__).resolve().parents[2]


class DemoRoutingTests(unittest.TestCase):
    def setUp(self):
        self.auth_path = isolate_demo_storage(self)

    def app(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        return app

    def test_anonymous_only_sees_demo_entry_and_all_dataset_profiles(self):
        app = self.app()
        self.assertEqual(len(app.selectbox(key="cq_demo_employee").options), 200)
        self.assertEqual(
            {option.rsplit(" · ", 1)[-1] for option in app.selectbox(key="cq_demo_employee").options},
            {person["employee_id"] for person in app.session_state["dataset"]["employees"]},
        )
        self.assertTrue(any(button.key == "cq_demo_enter" for button in app.button))
        self.assertFalse(any(button.key == "cq_demo_logout" for button in app.button))
        self.assertFalse(app.tabs)
        self.assertFalse(app.dataframe)
        self.assertFalse(app.slider)
        self.assertFalse(app.get("file_uploader"))
        self.assertFalse(app.text_input)
        self.assertFalse(any(button.key and button.key.startswith(("complete-", "research-", "map-complete-")) for button in app.button))
        self.assertFalse(self.auth_path.exists())

    def test_employee_is_bound_to_login_profile_not_stale_sidebar_state(self):
        app = self.app()
        demo_login(app, employee_id="E0002")
        self.assertEqual(app.session_state["cq_demo_identity"]["employee_id"], "E0002")
        self.assertFalse(any(widget.key == "employee_id" for widget in app.selectbox))
        self.assertFalse(any(widget.key in {"mode", "admin_page"} for widget in app.radio))
        expected_tabs = {"Профиль и опыт", "Треки и курсы", "Мои сертификаты", "Мой маршрут", "Карта развития", "Навыки и требования", "История участия"}
        self.assertEqual({tab.label for tab in app.tabs}, expected_tabs)
        app.session_state["employee_id"] = "E0003"
        app.session_state["pending_employee"] = "E0004"
        app.session_state["mode"] = "HR"
        app.run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(app.session_state["cq_demo_identity"]["employee_id"], "E0002")
        key = (app.session_state["revision"], "E0002")
        self.assertEqual(app.session_state["views"][key]["employee"]["employee_id"], "E0002")
        self.assertFalse(app.get("file_uploader"))
        self.assertFalse(self.auth_path.exists())

    def test_hr_can_choose_profiles_and_keeps_all_growth_review_tabs(self):
        app = self.app()
        demo_login(app, "hr")
        self.assertEqual(app.selectbox(key="employee_id").value, "E0001")
        self.assertEqual(len(app.selectbox(key="employee_id").options), 200)
        self.assertEqual({tab.label for tab in app.tabs}, {"Заявки и решения", "Оценка сотрудника", "Обзор команды"})
        app.selectbox(key="employee_id").select("E0200").run()
        hr_tab(app, "Оценка сотрудника")
        self.assertEqual(len(app.slider), 6)
        self.assertTrue(any(button.label == "Сохранить профиль HR" for button in app.button))
        self.assertFalse(app.get("file_uploader"))
        self.assertFalse(any(button.key and button.key.startswith(("complete-", "research-")) for button in app.button))
        demo_logout(app)
        self.assertTrue(any(button.key == "cq_demo_enter" for button in app.button))
        self.assertFalse(self.auth_path.exists())

    def test_admin_routes_import_and_status_without_employee_or_hr_actions(self):
        app = self.app()
        demo_login(app, "admin")
        self.assertEqual(app.radio(key="admin_page").options, ["Импорт данных", "Состояние приложения"])
        self.assertEqual(len(app.get("file_uploader")), 2)
        self.assertFalse(app.tabs)
        self.assertFalse(app.slider)
        self.assertFalse(any(widget.key == "employee_id" for widget in app.selectbox))
        app.radio(key="admin_page").set_value("Состояние приложения").run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertFalse(app.get("file_uploader"))
        self.assertFalse(any(button.key and button.key.startswith(("complete-", "research-")) for button in app.button))
        demo_logout(app)
        self.assertFalse(self.auth_path.exists())

    def test_logout_invalidates_views_and_preserves_completed_dataset(self):
        app = self.app()
        demo_login(app, employee_id="E0002")
        employee_tab(app, "Мой маршрут")
        key = (app.session_state["revision"], "E0002")
        before = deepcopy(app.session_state["views"][key])
        self.assertFalse(any(b.key and b.key.startswith('complete-') for b in app.button))
        dataset = deepcopy(app.session_state["dataset"])
        revision = app.session_state["revision"]
        sentinel = (revision, "__stale_test_view__")
        views = dict(app.session_state["views"])
        views[sentinel] = {"stale": True}
        app.session_state["views"] = views
        demo_logout(app)
        self.assertNotIn(sentinel, app.session_state["views"])
        self.assertEqual(app.session_state["dataset"], dataset)
        self.assertNotIn("cq_demo_identity", app.session_state)
        demo_login(app, "hr")
        self.assertEqual(app.session_state["dataset"], dataset)
        switch_demo_role(app, "employee", "E0002")
        after = app.session_state["views"][(revision, "E0002")]
        self.assertEqual(after["trajectory"]["progress_pct"], before["trajectory"]["progress_pct"])
        self.assertEqual(len(after["history"]), len(before["history"]))
        self.assertNotIn(sentinel, app.session_state["views"])
        self.assertFalse(self.auth_path.exists())

    def test_real_imported_profile_is_available_at_next_demo_login(self):
        app = self.app()
        demo_login(app, "admin")
        profile = deepcopy(app.session_state["dataset"]["employees"][1])
        profile.update(employee_id="DEMO_ROUTING_SYNTHETIC", full_name="Synthetic routing import", manager_id=None)
        # AppTest lacks an upload setter. Replace only the file-input boundary;
        # the real submit handler, adapter, import and rerun execute unchanged.
        uploaded = io.BytesIO(json.dumps({"employees": [profile]}).encode("utf-8"))
        uploaded.name = "profile.json"
        original_get = SessionStateProxy.get
        with patch.object(SessionStateProxy, 'get', lambda state, key, default=None:
                          uploaded if key == 'employees_upload' else original_get(state, key, default)):
            next(button for button in app.button if button.label == "Импортировать данные").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(len(app.session_state["dataset"]["employees"]), 201)
        self.assertEqual(app.session_state["pending_employee"], profile["employee_id"])
        self.assertTrue(any("Импорт завершён." in item.value for item in app.success))
        self.assertFalse(self.auth_path.exists())
        demo_logout(app)
        self.assertEqual(len(app.selectbox(key="cq_demo_employee").options), 201)
        self.assertEqual(app.selectbox(key="cq_demo_employee").value, profile["employee_id"])
        demo_login(app, employee_id=profile["employee_id"])
        key = (app.session_state["revision"], profile["employee_id"])
        view = app.session_state["views"][key]
        self.assertEqual(view["employee"]["employee_id"], profile["employee_id"])
        self.assertFalse(view["history"])
        self.assertTrue(view["recommendations"])
        self.assertFalse(self.auth_path.exists())

    def test_invalid_json_import_form_keeps_dataset_and_shows_clear_error(self):
        app = self.app()
        demo_login(app, "admin")
        before = deepcopy(app.session_state["dataset"])
        revision = app.session_state["revision"]
        uploaded = io.BytesIO(b'{"employees": [invalid JSON')
        uploaded.name = "invalid-profile.json"
        original_get = SessionStateProxy.get
        with patch.object(SessionStateProxy, 'get', lambda state, key, default=None:
                          uploaded if key == 'employees_upload' else original_get(state, key, default)):
            next(button for button in app.button if button.label == "Импортировать данные").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 1)
        self.assertIn("Не удалось прочитать файл", app.error[0].value)
        self.assertIn("JSON/CSV", app.error[0].value)
        self.assertEqual(app.session_state["dataset"], before)
        self.assertEqual(app.session_state["revision"], revision)
        self.assertNotIn("pending_employee", app.session_state)
        self.assertEqual(app.session_state["cq_demo_identity"]["role"], "admin")
        self.assertFalse(self.auth_path.exists())


if __name__ == "__main__":
    unittest.main()
