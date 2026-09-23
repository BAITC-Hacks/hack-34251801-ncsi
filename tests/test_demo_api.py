"""Tests of a synthetic demo, NOT the official starter-kit schema."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from core import api

class DemoContractTests(unittest.TestCase):
    def setUp(self):
        self.dataset = api.load_dataset('__demo__')

    def test_missing_folder_and_invalid_dataset_rejected(self):
        with self.assertRaises((ValueError, FileNotFoundError)):
            api.load_dataset('data')
        with self.assertRaises(ValueError):
            api.list_employees({})

    def test_employee_contract_and_isolation(self):
        view = api.get_employee_view(self.dataset, 'DEMO-01')
        self.assertEqual(set(view), {'employee', 'next_grade', 'skills', 'history', 'recommendations', 'trajectory'})
        self.assertEqual(set(view['employee']), {'employee_id', 'name', 'role', 'grade', 'tenure_months'})
        self.assertTrue(1 <= len(view['recommendations']) <= 3)
        for rec in view['recommendations']:
            self.assertEqual(set(rec), {'event_id', 'title', 'score', 'reasons', 'skill_changes'})
            self.assertGreaterEqual(len(rec['reasons']), 3)
        view['employee']['name'] = 'changed'
        self.assertNotEqual(api.list_employees(self.dataset)[0]['name'], 'changed')

    def test_completion_changes_progress_once(self):
        before = api.get_employee_view(self.dataset, 'DEMO-01')
        after = api.complete_activity(self.dataset, 'DEMO-01', 'DEMO-E1')
        self.assertGreater(after['trajectory']['progress_percent'], before['trajectory']['progress_percent'])
        self.assertEqual(len(after['history']), 1)
        snapshot = copy.deepcopy(self.dataset)
        with self.assertRaises(ValueError):
            api.complete_activity(self.dataset, 'DEMO-01', 'DEMO-E1')
        self.assertEqual(self.dataset, snapshot)
        self.assertTrue(all(r['event_id'] != 'DEMO-E1' for r in after['recommendations']))

    def test_empty_states_and_hr(self):
        self.assertEqual(api.get_employee_view(self.dataset, 'DEMO-02')['history'], [])
        self.assertEqual(api.get_employee_view(self.dataset, 'DEMO-03')['recommendations'], [])
        api.complete_activity(self.dataset, 'DEMO-01', 'DEMO-E1')
        hr = api.get_hr_view(self.dataset)
        self.assertEqual(hr['activity_participation'][0]['participations'], 1)
        self.assertEqual(hr['employees_without_recommendations'][0]['employee_id'], 'DEMO-03')

    def test_demo_import_uses_same_api_and_is_atomic(self):
        profile = {'employee_id': 'DEMO-NEW', 'role': 'Backend Engineer', 'grade': 'Middle', 'tenure_months': 12, 'skills': {'SK_PYTHON': 2}}
        with tempfile.TemporaryDirectory() as folder:
            profiles = Path(folder) / 'employees.json'
            history = Path(folder) / 'activity_history.csv'
            profiles.write_text(json.dumps([profile]), encoding='utf-8')
            history.write_text('employee_id,event_id,status,date\nDEMO-NEW,DEMO-E3,skipped,2026-01-01\n', encoding='utf-8')
            imported = api.import_test_data(self.dataset, str(profiles), str(history))
            self.assertEqual(len(api.list_employees(imported)), 4)
            self.assertEqual(len(api.list_employees(self.dataset)), 3)
            self.assertTrue(api.get_employee_view(imported, 'DEMO-NEW')['recommendations'])
            api.complete_activity(imported, 'DEMO-NEW', 'DEMO-E1')
            snapshot = copy.deepcopy(self.dataset)
            history.write_text('bad,column\n1,2', encoding='utf-8')
            with self.assertRaises(ValueError):
                api.import_test_data(self.dataset, str(profiles), str(history))
            self.assertEqual(self.dataset, snapshot)

    def test_unknown_employee(self):
        with self.assertRaises(ValueError):
            api.get_employee_view(self.dataset, 'missing')

if __name__ == '__main__':
    unittest.main()
