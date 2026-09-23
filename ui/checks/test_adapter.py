import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from ui import demo_adapter
from ui.core_adapter import AdapterError, CoreAdapter

DATA = Path(__file__).resolve().parents[2] / "case/case_1/career_quest_dataset"


class AdapterContractTests(unittest.TestCase):
    def setUp(self):
        self.adapter = CoreAdapter(DATA, module=demo_adapter)
        self.dataset = self.adapter.load_dataset()

    def test_arbitrary_employee_and_real_skill_names(self):
        self.assertEqual(len(self.adapter.list_employees(self.dataset)), 200)
        for employee in self.dataset["employees"]:
            view = self.adapter.get_employee_view(self.dataset, employee["employee_id"])
            self.assertLessEqual(len(view["recommendations"]), 3)
            self.assertTrue(all(not s["name"].startswith("SK_") for s in view["skills"]))
            self.assertTrue(all(len(r["reasons"]) >= 3 for r in view["recommendations"]))

    def test_completion_updates_then_requeries_without_mutating_original(self):
        view = self.adapter.get_employee_view(self.dataset, "E0001")
        rec = view["recommendations"][0]
        old_history = len(self.dataset["history"])
        updated, new_view = self.adapter.complete_activity(self.dataset, "E0001", rec["event_id"])
        self.assertEqual(len(updated["history"]), old_history + 1)
        self.assertEqual(len(self.dataset["history"]), old_history)
        self.assertGreaterEqual(new_view["trajectory"]["progress_pct"], view["trajectory"]["progress_pct"])
        sid = rec["skill_changes"][0]["skill_id"]
        self.assertGreater(new_view["employee"]["skills"][sid], view["employee"]["skills"][sid])
        if rec["event_id"] != "EV_036":
            self.assertNotIn(rec["event_id"], [r["event_id"] for r in new_view["recommendations"]])

    def test_import_new_employee_uses_same_backend(self):
        employee = deepcopy(self.dataset["employees"][0])
        employee["employee_id"] = "JURY_001"
        payload = json.dumps({"employees": [employee]}).encode()
        updated = self.adapter.import_test_data(self.dataset, payload)
        self.assertEqual(len(self.adapter.list_employees(updated)), 201)
        self.assertEqual(self.adapter.get_employee_view(updated, "JURY_001")["employee"]["employee_id"], "JURY_001")
        self.assertEqual(len(self.dataset["employees"]), 200)

    def test_rejected_upload_is_atomic(self):
        original = deepcopy(self.dataset)
        for payload in (b"not json", b'{"employees": []}', json.dumps({"employees": [self.dataset["employees"][0]]}).encode()):
            with self.assertRaises(ValueError):
                self.adapter.import_test_data(self.dataset, payload)
            self.assertEqual(self.dataset, original)

    def test_joint_import_is_atomic_when_history_is_invalid(self):
        employee = deepcopy(self.dataset["employees"][0])
        employee["employee_id"] = "JURY_001"
        history = b"record_id,employee_id,event_id,date,status,completion_pct\nR_JURY,UNKNOWN,EV_010,2026-09-30,completed,100\n"
        with self.assertRaises(ValueError):
            self.adapter.import_test_data(self.dataset, json.dumps([employee]).encode(), history)
        self.assertEqual(len(self.dataset["employees"]), 200)

    def test_real_api_is_delegated_and_errors_are_not_hidden(self):
        api = SimpleNamespace(__name__="core.api", **{name: Mock(wraps=getattr(demo_adapter, name)) for name in
                              ("load_dataset", "list_employees", "get_employee_view", "complete_activity", "import_test_data", "get_hr_view")})
        adapter = CoreAdapter(DATA, module=api)
        self.assertFalse(adapter.is_demo)
        adapter.get_employee_view(self.dataset, "E0001")
        api.get_employee_view.assert_called_once_with(self.dataset, "E0001")
        api.complete_activity.side_effect = ValueError("Недоступно")
        with self.assertRaisesRegex(ValueError, "Недоступно"):
            adapter.complete_activity(self.dataset, "E0001", "EV_001")

    def test_hr_and_top_grade_empty_state(self):
        hr = self.adapter.get_hr_view(self.dataset)
        self.assertTrue(hr["skill_gaps"])
        self.assertEqual(len(hr["participation"]), 40)
        lead = next(e for e in self.dataset["employees"] if e["grade"] == "Lead")
        view = self.adapter.get_employee_view(self.dataset, lead["employee_id"])
        self.assertIsNone(view["next_grade"])
        self.assertEqual(view["recommendations"], [])
        self.assertTrue(view["empty_reason"])


if __name__ == "__main__":
    unittest.main()
