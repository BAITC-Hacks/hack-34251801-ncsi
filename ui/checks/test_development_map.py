"""Map contract checks against the starter-kit engine, without assigning levels in UI."""

import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from ui.core_adapter import CoreAdapter
from ui.development_map import build_map_model, map_svg
from ui.checks.demo_login_helpers import demo_login, isolate_demo_storage, switch_demo_role


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "case/case_1/career_quest_dataset"


class DevelopmentMapTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"CAREER_QUEST_AI_PROVIDER": "none"})
        env.start()
        self.addCleanup(env.stop)
        self.adapter = CoreAdapter(DATA)
        self.dataset = self.adapter.load_dataset()

    def model(self, view, **kwargs):
        return build_map_model(view, self.adapter.catalog, self.adapter.events, **kwargs)

    def imported_profile(self):
        """A valid actual-schema profile with one gap and one skill at the event cap."""
        profile = deepcopy(self.dataset["employees"][0])
        profile.update(employee_id="JURY_MAP_CHECK", full_name="Проверка карты развития",
                       manager_id=None, last_review_date=self.dataset["as_of_date"])
        target = next(p for p in self.adapter.role_profiles
                      if p["role"] == profile["role"] and p["grade"] == "Middle")
        profile["skills"].update(target["required_skills"])
        profile["skills"]["SK_API_DESIGN"] = 3
        profile["skills"]["SK_SYSTEM_DESIGN"] = 1
        return profile

    def test_real_profile_completion_requeries_levels_and_keeps_model_read_only(self):
        view = self.adapter.get_employee_view(self.dataset, "E0001")
        rec = view["recommendations"][0]
        saved = deepcopy(view)
        before = self.model(view, selected_event_id=rec["event_id"])
        self.assertEqual(view, saved)
        self.assertEqual(before["event"]["event_id"], rec["event_id"])
        updated, fresh = self.adapter.complete_activity(self.dataset, "E0001", rec["event_id"])
        completion = {"event_id": rec["event_id"],
                      "before": {s["skill_id"]: s["current"] for s in view["skills"]},
                      "after": {s["skill_id"]: s["current"] for s in fresh["skills"]}}
        after = self.model(fresh, selected_event_id=rec["event_id"], completion=completion)
        self.assertGreater(fresh["trajectory"]["progress_pct"], view["trajectory"]["progress_pct"])
        self.assertEqual(len(updated["history"]), len(self.dataset["history"]) + 1)
        self.assertEqual(after["event"]["event_id"], rec["event_id"])
        levels = {s["skill_id"]: s["current"] for s in fresh["skills"]}
        for skill in after["skills"]:
            self.assertEqual(skill["current"], levels[skill["skill_id"]])

    def test_imported_profile_uses_real_core_and_respects_activity_cap(self):
        profile = self.imported_profile()
        dataset = self.adapter.import_test_data(
            self.dataset, employees_bytes=json.dumps({"employees": [profile]}).encode())
        view = self.adapter.get_employee_view(dataset, profile["employee_id"])
        self.assertFalse(view["history"])
        rec = next(r for r in view["recommendations"] if r["event_id"] == "EV_005")
        self.assertEqual([c["skill_id"] for c in rec["skill_changes"]], ["SK_SYSTEM_DESIGN"])
        model = self.model(view, selected_skill_id="SK_SYSTEM_DESIGN", selected_event_id="EV_005")
        self.assertEqual(model["selected_skill"]["current"], 1)
        self.assertEqual(model["selected_skill"]["required"], 2)
        updated, fresh = self.adapter.complete_activity(dataset, profile["employee_id"], "EV_005")
        skills = {s["skill_id"]: s for s in fresh["skills"]}
        self.assertEqual(skills["SK_API_DESIGN"]["current"], 3)
        self.assertEqual(skills["SK_SYSTEM_DESIGN"]["current"], 2)
        self.assertEqual(fresh["trajectory"]["progress_pct"], 100)
        completion = {"event_id": "EV_005",
                      "before": {s["skill_id"]: s["current"] for s in view["skills"]},
                      "after": {s["skill_id"]: s["current"] for s in fresh["skills"]}}
        after = self.model(fresh, selected_skill_id="SK_SYSTEM_DESIGN",
                           selected_event_id="EV_005", completion=completion)
        self.assertEqual(after["selected_skill"]["current"], 2)
        self.assertEqual(after["selected_skill"]["gap"], 0)
        self.assertFalse(fresh["recommendations"])
        self.assertEqual(updated["history"][-1]["status"], "completed")

    def test_compact_selection_and_expand_use_only_actual_target_skills(self):
        view = self.adapter.get_employee_view(self.dataset, "E0001")
        compact = self.model(view)
        self.assertEqual(len(compact["skills"]), 5)
        hidden = next(s for s in view["skills"] if s["skill_id"] not in
                      {item["skill_id"] for item in compact["skills"]})
        selected = self.model(view, selected_skill_id=hidden["skill_id"])
        self.assertEqual(selected["selected_skill"]["skill_id"], hidden["skill_id"])
        self.assertIn(hidden["skill_id"], {s["skill_id"] for s in selected["skills"]})
        self.assertEqual(len(selected["skills"]), 5)
        expanded = self.model(view, expanded=True)
        self.assertEqual({s["skill_id"] for s in expanded["skills"]},
                         {s["skill_id"] for s in view["skills"]})
        self.assertLess(len(expanded["skills"]), len(self.adapter.catalog))
        stale = self.model(view, selected_skill_id="REMOVED", selected_event_id="REMOVED")
        self.assertIn(stale["selected_skill"]["skill_id"], {s["skill_id"] for s in view["skills"]})
        self.assertEqual(stale["event_id"], view["recommendations"][0]["event_id"])

    def test_every_edge_is_supported_by_events_and_categories_create_no_edges(self):
        view = self.adapter.get_employee_view(self.dataset, "E0001")
        # Exercise a real catalog prerequisite without redefining engine eligibility.
        view["recommendations"] = [{"event_id": "EV_006", "skill_changes": []}]
        model = self.model(view, selected_event_id="EV_006", expanded=True)
        event = self.adapter.events["EV_006"]
        expected = {(d["skill_id"], "develops") for d in event["develops_skills"]}
        expected.update((sid, "prerequisite") for sid in event["prerequisites"])
        actual = {(edge["skill_id"], edge["kind"]) for edge in model["edges"]}
        self.assertEqual(actual, expected)
        self.assertTrue(all(edge["event_id"] == "EV_006" for edge in model["edges"]))
        self.assertEqual(next(edge["required"] for edge in model["edges"]
                              if edge["kind"] == "prerequisite"), 2)
        # Merely sharing a category does not connect Python and Java or any other skills.
        self.assertFalse(any(edge["kind"] not in {"develops", "prerequisite"}
                             for edge in model["edges"]))
        self.assertTrue(all("Разработка" in skill["branch"] for skill in model["skills"]
                            if self.adapter.catalog[skill["skill_id"]]["category"] == "engineering"))

    def test_projections_come_from_core_not_catalog_gain(self):
        profile = self.imported_profile()
        dataset = self.adapter.import_test_data(
            self.dataset, employees_bytes=json.dumps({"employees": [profile]}).encode())
        view = self.adapter.get_employee_view(dataset, profile["employee_id"])
        model = self.model(view, selected_event_id="EV_005", expanded=True)
        self.assertNotIn("SK_API_DESIGN", model["changes"])
        self.assertEqual(model["changes"]["SK_SYSTEM_DESIGN"]["after"], 2)
        self.assertTrue(any(edge["skill_id"] == "SK_API_DESIGN" and edge["max_level"] == 3
                            for edge in model["edges"]))
        # Deliberately contradictory catalog metadata must not change core's projection.
        events = deepcopy(self.adapter.events)
        events["EV_005"]["develops_skills"][0]["gain"] = 5
        same_projection = build_map_model(view, self.adapter.catalog, events,
                                          selected_event_id="EV_005")
        self.assertEqual(same_projection["changes"], model["changes"])

    def test_empty_recommendations_long_titles_and_svg_escaping(self):
        view = self.adapter.get_employee_view(self.dataset, "E0001")
        events = deepcopy(self.adapter.events)
        attack = '<script>alert("unsafe")</script>'
        events["EV_005"]["title"] = attack + " Очень длинное название активности" * 8
        view["skills"][0]["name"] = attack
        model = build_map_model(view, self.adapter.catalog, events,
                                selected_event_id="EV_005", selected_skill_id="SK_API_DESIGN")
        rendered = map_svg(model)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("…", rendered)
        self.assertIn('role="img"', rendered)
        empty = deepcopy(view)
        empty["recommendations"] = []
        model = self.model(empty)
        self.assertIsNone(model["event"])
        self.assertFalse(model["changes"])
        self.assertFalse(model["edges"])
        self.assertIn("Нет рекомендованного шага", map_svg(model))
        empty["skills"] = []
        self.assertIsNone(self.model(empty)["selected_skill"])

    def test_streamlit_map_mount_and_employee_switch_dont_award_progress(self):
        isolate_demo_storage(self)
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        demo_login(app)
        before = deepcopy(app.session_state['dataset'])
        with patch('core.growth_ai._bounded_http') as transport:
            for eid in ['E0001', 'E0002', 'E0001']:
                switch_demo_role(app, 'employee', eid)
                app.session_state['employee_tab'] = 'Карта развития'
                app.run()
                self.assertFalse(app.exception)
                self.assertFalse(app.error)
                self.assertFalse(any(b.key and b.key.startswith('map-complete-') for b in app.button))
            transport.assert_not_called()
        self.assertEqual(app.session_state['dataset'], before)


if __name__ == "__main__":
    unittest.main()
