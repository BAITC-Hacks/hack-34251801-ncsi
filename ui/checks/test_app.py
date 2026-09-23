"""Exercise Streamlit's actual reruns and session state, without a web server."""

import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from ui import demo_adapter
from ui.core_adapter import CoreAdapter

APP = Path(__file__).resolve().parents[2] / "app.py"


class AppInteractionTests(unittest.TestCase):
    def setUp(self):
        backend = patch("ui.core_adapter.CoreAdapter", side_effect=lambda data_dir: CoreAdapter(data_dir, module=demo_adapter))
        backend.start()
        self.addCleanup(backend.stop)

    def app(self):
        app = AppTest.from_file(str(APP), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        return app

    def test_select_any_profile_and_empty_state(self):
        app = self.app()
        self.assertEqual(len(app.selectbox(key="employee_id").options), 200)
        app.selectbox(key="employee_id").select("E0002").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertIn("E0002", app.session_state["employee_id"])

    def test_completion_survives_screen_switch(self):
        app = self.app()
        old_history_count = len(app.session_state["dataset"]["history"])
        app.button(key="complete-E0001-EV_005").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertEqual(len(app.success), 1)
        self.assertEqual(len(app.session_state["dataset"]["history"]), old_history_count + 1)
        app.radio(key="mode").set_value("HR").run()
        self.assertEqual(len(app.error), 0)
        self.assertGreater(len(app.dataframe), 0)
        app.radio(key="mode").set_value("Сотрудник").run()
        self.assertEqual(len(app.session_state["dataset"]["history"]), old_history_count + 1)
        self.assertEqual(len(app.exception), 0)

    def test_import_form_and_missing_files_error(self):
        app = self.app()
        app.radio(key="mode").set_value("Импорт данных").run()
        self.assertEqual(len(app.get("file_uploader")), 2)
        next(button for button in app.button if button.label == "Импортировать данные").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertIn("Выберите файл", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
