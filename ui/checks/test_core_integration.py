"""Real core and UI boundary, including provider outcomes without network calls."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from core import ai, api
from streamlit.testing.v1 import AppTest
from ui.core_adapter import AdapterError, CoreAdapter
from ui.checks.demo_login_helpers import demo_login, isolate_demo_storage

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "case/case_1/career_quest_dataset"


class CoreIntegrationTests(unittest.TestCase):
    def setUp(self):
        isolate_demo_storage(self)
        ai._CACHE.clear()
        ai._FAILURES.clear()
        env = patch.dict(os.environ, {"CAREER_QUEST_AI_PROVIDER": "none"})
        env.start()
        self.addCleanup(env.stop)
        self.adapter = CoreAdapter(DATA)
        self.dataset = self.adapter.load_dataset()

    def test_actual_core_fields_preserve_names_progress_and_hr_counts(self):
        self.assertFalse(self.adapter.is_demo)
        people = self.adapter.list_employees(self.dataset)
        self.assertEqual(people[0]["full_name"], "Marat Yessenov")
        raw = api.get_employee_view(self.dataset, "E0001")
        view = self.adapter.get_employee_view(self.dataset, "E0001")
        self.assertEqual(view["trajectory"]["progress_pct"], raw["trajectory"]["progress_percent"])
        self.assertEqual([r["event_id"] for r in view["recommendations"]], [r["event_id"] for r in raw["recommendations"]])
        self.assertTrue(next(s for s in view["skills"] if s["skill_id"] == "SK_API_DESIGN")["critical"])
        hr = self.adapter.get_hr_view(self.dataset)
        self.assertEqual(sum(r["records"] for r in hr["participation"]), 2743)
        self.assertTrue(all(row["name"] for row in hr["skill_gaps"]))

    def test_missing_core_is_an_error_instead_of_silent_preview(self):
        with patch("ui.core_adapter.importlib.import_module", side_effect=ModuleNotFoundError("missing", name="core")):
            with self.assertRaisesRegex(AdapterError, "Не найден core/api.py"):
                CoreAdapter(DATA)

    def test_ui_render_uses_core_without_unmetered_legacy_ai(self):
        expected = api.get_employee_view(self.dataset, "E0001")
        with patch.dict(os.environ, {"CAREER_QUEST_AI_PROVIDER": "openai", "CAREER_QUEST_AI_MODEL": "synthetic-model", "OPENAI_API_KEY": "synthetic-test-token"}), \
             patch.object(ai, "_bounded_request", side_effect=TimeoutError) as provider:
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
            demo_login(app)
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        view = app.session_state["views"][(0, "E0001")]
        provider.assert_not_called()
        self.assertIn("Подтверждённый прогресс core", view["ai_status"])
        rec = view["recommendations"][0]
        self.assertFalse(rec["ai_fallback"])
        self.assertEqual(rec["reasons"], expected["recommendations"][0]["reasons"])
        self.assertEqual(rec["display_explanation"], rec["reasons"][0])

    def test_successful_ai_selection_keeps_facts_and_labels_its_actual_role(self):
        def response(*args):
            return {"event_id": args[3]["candidates"][0]["event_id"], "reason_indices": [2, 1, 0]}
        baseline = api.get_employee_view(self.dataset, "E0001")
        with patch.dict(os.environ, {"CAREER_QUEST_AI_PROVIDER": "nvidia", "CAREER_QUEST_AI_MODEL": "synthetic-model", "NVIDIA_API_KEY": "synthetic-test-token"}), \
             patch.object(ai, "_bounded_request", side_effect=response):
            view = self.adapter.get_employee_view(self.dataset, "E0001")
        self.assertTrue(view["ai_status"].startswith("AI · nvidia"))
        rec = view["recommendations"][0]
        self.assertEqual(rec["display_explanation"], baseline["recommendations"][0]["reasons"][2])
        self.assertEqual(set(rec["reasons"]), set(baseline["recommendations"][0]["reasons"]))
        self.assertFalse(rec["ai_fallback"])
        # Core supplied factual reasons, not free model prose; preserve that distinction.
        self.assertEqual(rec["display_explanation_source"], "rules")


if __name__ == "__main__":
    unittest.main()
