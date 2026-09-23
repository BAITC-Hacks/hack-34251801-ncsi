"""The map displays backend facts and joins only supported references."""

from copy import deepcopy
import unittest

from ui.map_component import build_map_model


class InteractiveMapModelTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {"skills": {"python": 2, "security": 0}, "skill_labels": {"python": "Python"},
                         "certificates": [{"id": "approved", "status": "approved", "payload": {"title": "Verified course"}},
                                          {"id": "pending", "status": "pending", "payload": {"title": "Unverified course"}}]}
        self.plan = {"plan_id": "plan1", "tracks": [{"id": "track1", "title": "Backend", "basis_refs": ["python", "approved", "pending", "unknown"],
                      "next_skills": ["Architecture"], "courses": [{"id": "course1", "title": "Advanced Python", "url": "https://example.com/python"},
                                                                       {"id": "course2", "title": "Hidden course", "url": "https://example.com/hidden", "hidden": True}]}]}

    def test_only_approved_facts_and_valid_edges(self):
        model = build_map_model(self.plan, self.snapshot)
        facts = [node for node in model["nodes"] if node["kind"] in {"skill", "certificate"}]
        self.assertEqual({node["ref"] for node in facts}, {"python", "approved"})
        self.assertEqual(len([edge for edge in model["edges"] if edge["kind"] == "basis"]), 2)
        ids = {node["id"] for node in model["nodes"]}
        self.assertTrue(all(edge["source"] in ids and edge["target"] in ids for edge in model["edges"]))

    def test_future_skills_are_suggestions_not_level_increases(self):
        model = build_map_model(self.plan, self.snapshot)
        future = next(node for node in model["nodes"] if node["kind"] == "future_skill")
        self.assertTrue(future["payload"]["suggested"])
        self.assertNotIn("level", future["payload"])
        self.assertNotIn("gain", future["payload"])
        course = next(node for node in model["nodes"] if node["kind"] == "course")
        self.assertEqual(course["course_id"], "course1")
        self.assertEqual(course["track_id"], "track1")
        self.assertEqual(course["payload"]["url"], "https://example.com/python")

    def test_decisions_not_mutated_and_selection_stable_on_refresh(self):
        original = deepcopy((self.plan, self.snapshot))
        before = build_map_model(self.plan, self.snapshot)
        self.assertEqual((self.plan, self.snapshot), original)
        refreshed = deepcopy(self.plan)
        refreshed["plan_id"] = "plan2"
        after = build_map_model(refreshed, self.snapshot)
        self.assertEqual([node["id"] for node in before["nodes"]], [node["id"] for node in after["nodes"]])
        self.assertNotIn("Hidden course", [node["label"] for node in after["nodes"]])

    def test_same_course_in_two_tracks_has_unique_map_nodes(self):
        other = deepcopy(self.plan["tracks"][0])
        other["id"] = "track2"
        self.plan["tracks"].append(other)
        model = build_map_model(self.plan, self.snapshot)
        ids = [node["id"] for node in model["nodes"]]
        self.assertEqual(len(ids), len(set(ids)))
        courses = [node for node in model["nodes"] if node["kind"] == "course"]
        self.assertEqual([node["course_id"] for node in courses], ["course1", "course1"])

    def test_labels_remain_plain_data_for_javascript_text_content(self):
        self.plan["tracks"][0]["title"] = '<img src=x onerror="alert(1)">'
        model = build_map_model(self.plan, self.snapshot)
        self.assertEqual(next(node for node in model["nodes"] if node["kind"] == "track")["label"], self.plan["tracks"][0]["title"])
        self.assertEqual(build_map_model({}, {})["nodes"], [])


if __name__ == "__main__":
    unittest.main()
