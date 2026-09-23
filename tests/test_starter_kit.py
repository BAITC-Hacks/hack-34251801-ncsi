"""Real starter-kit validation; synthetic extra profile uses its actual schema."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from core import api
from core.engine import current_levels

DATA = Path(__file__).resolve().parents[1] / 'case/case_1/career_quest_dataset'

class StarterKitTests(unittest.TestCase):
    def setUp(self):
        self.d = api.load_dataset(str(DATA))

    def test_all_profiles_and_eligibility(self):
        self.assertEqual((len(self.d['employees']), len(self.d['events']), len(self.d['history'])), (200, 40, 2743))
        events = {e['event_id']: e for e in self.d['events']}
        for e in self.d['employees']:
            view = api.get_employee_view(self.d, e['employee_id'])
            self.assertLessEqual(len(view['recommendations']), 3)
            self.assertTrue(0 <= view['trajectory']['progress_percent'] <= 100)
            history = [h for h in self.d['history'] if h['employee_id'] == e['employee_id']]
            levels = current_levels(self.d, e, history)
            for rec in view['recommendations']:
                event = events[rec['event_id']]
                self.assertFalse(event['mandatory'])
                self.assertIn(e['role'], event['target_roles'])
                self.assertIn(e['grade'], event['target_grades'])
                self.assertTrue(all(levels.get(s, 0) >= r for s, r in event['prerequisites'].items()))
                for change in rec['skill_changes']:
                    gain = next(g for g in event['develops_skills'] if g['skill_id'] == change['skill_id'])
                    self.assertEqual(change['after'], min(gain['max_level'], change['before'] + gain['gain']))

    def test_complete_replays_once_and_changes_hr(self):
        before = api.get_employee_view(self.d, 'E0002')
        rec = before['recommendations'][0]
        after = api.complete_activity(self.d, 'E0002', rec['event_id'])
        self.assertGreater(after['trajectory']['progress_percent'], before['trajectory']['progress_percent'])
        self.assertEqual(after, api.get_employee_view(self.d, 'E0002'))
        with self.assertRaises(ValueError):
            api.complete_activity(self.d, 'E0002', rec['event_id'])
        self.assertEqual(sum(r['participations'] for r in api.get_hr_view(self.d)['activity_participation']), 2744)

    def test_history_only_after_review_and_max_does_not_decrease(self):
        e = copy.deepcopy(self.d['employees'][0])
        ev = next(x for x in self.d['events'] if x['event_id'] == 'EV_005')
        e['skills'] = {g['skill_id']: 5 for g in ev['develops_skills']}
        row = {'event_id': 'EV_005', 'status': 'completed', 'date': '2026-09-30', 'record_id': 'DEMO-TEST'}
        e['last_review_date'] = '2026-09-01'
        self.assertEqual(current_levels(self.d, e, [row]), e['skills'])
        e['skills'] = {}
        e['last_review_date'] = '2026-09-30'
        self.assertEqual(current_levels(self.d, e, [row]), {})

    def test_real_schema_import_and_atomic_failure(self):
        profile = copy.deepcopy(self.d['employees'][1])
        profile['employee_id'] = 'CHECK-NEW'
        profile['full_name'] = 'Synthetic verification profile'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'employees.json'
            path.write_text(json.dumps({'employees': [profile]}), encoding='utf-8')
            new = api.import_test_data(self.d, str(path))
            self.assertEqual(len(new['employees']), 201)
            rec = api.get_employee_view(new, 'CHECK-NEW')['recommendations'][0]
            api.complete_activity(new, 'CHECK-NEW', rec['event_id'])
            self.assertEqual(len(api.get_employee_view(new, 'CHECK-NEW')['history']), 1)
            snapshot = copy.deepcopy(new)
            with self.assertRaises(ValueError):
                api.import_test_data(new, str(path))
            self.assertEqual(new, snapshot)
            self.assertEqual(len(self.d['employees']), 200)

    def test_history_import_real_columns(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.csv'
            path.write_text('record_id,employee_id,event_id,date,due_date,status,completion_pct,score,feedback_rating,assigned_by\nCHECK-H,E0002,EV_005,2026-09-30,,no_show,0,,,self\n', encoding='utf-8')
            new = api.import_test_data(self.d, history_file=str(path))
            self.assertEqual(len(new['history']), 2744)
            self.assertNotEqual(api.get_employee_view(new, 'E0002')['recommendations'][0]['score'], api.get_employee_view(self.d, 'E0002')['recommendations'][0]['score'])

if __name__ == '__main__':
    unittest.main()
