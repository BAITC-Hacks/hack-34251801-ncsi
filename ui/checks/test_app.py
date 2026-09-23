"""Exercise Streamlit's actual reruns and session state, without a web server."""

import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from ui import demo_adapter
from ui.core_adapter import CoreAdapter
from ui.checks.demo_login_helpers import demo_login, isolate_demo_storage, switch_demo_role

APP = Path(__file__).resolve().parents[2] / "app.py"


class AppInteractionTests(unittest.TestCase):
    def setUp(self):
        isolate_demo_storage(self)
        backend = patch("ui.core_adapter.CoreAdapter", side_effect=lambda data_dir: CoreAdapter(data_dir, module=demo_adapter))
        backend.start()
        self.addCleanup(backend.stop)

    def app(self, login=True):
        app = AppTest.from_file(str(APP), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        return demo_login(app) if login else app

    def test_select_any_profile_and_empty_state(self):
        app = self.app(login=False)
        self.assertEqual(len(app.selectbox(key="cq_demo_employee").options), 200)
        demo_login(app, employee_id="E0002")
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertEqual("E0002", app.session_state["cq_demo_identity"]["employee_id"])

    def test_completion_survives_screen_switch(self):
        app = self.app()
        old_history_count = len(app.session_state["dataset"]["history"])
        app.button(key="complete-E0001-EV_005").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertEqual(len(app.success), 1)
        self.assertEqual(len(app.session_state["dataset"]["history"]), old_history_count + 1)
        switch_demo_role(app, "hr")
        self.assertEqual(len(app.error), 0)
        self.assertGreater(len(app.dataframe), 0)
        switch_demo_role(app, "employee")
        self.assertEqual(len(app.session_state["dataset"]["history"]), old_history_count + 1)
        self.assertEqual(len(app.exception), 0)

    def test_import_form_and_missing_files_error(self):
        app = self.app()
        switch_demo_role(app, "admin")
        app.radio(key="admin_page").set_value("Импорт данных").run()
        self.assertEqual(len(app.get("file_uploader")), 2)
        next(button for button in app.button if button.label == "Импортировать данные").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertIn("Выберите файл", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
