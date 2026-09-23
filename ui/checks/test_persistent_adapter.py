"""Real account permissions and persistent core/growth workflows."""

import json
import os
import tempfile
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest.mock import patch

from auth.service import AuthError, AuthService
from storage.dataset import DatasetStore
from ui.persistent_adapter import PersistentAdapter

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'case/case_1/career_quest_dataset'
PASSWORD = 'Only test accounts use this phrase 2026'


class PersistentAdapterTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        environment = patch.dict(os.environ, {
            'CAREER_QUEST_AUTH_DB': str(self.folder / 'accounts.sqlite3'),
            'CAREER_QUEST_DATASET_DB': str(self.folder / 'dataset.sqlite3'),
            'CAREER_QUEST_GROWTH_DB': str(self.folder / 'growth.sqlite3'),
            'OPENAI_API_KEY': '', 'NVIDIA_API_KEY': '', 'CAREER_QUEST_AI_PROVIDER': 'none',
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.service = AuthService()
        self.service.create_admin('Local administrator', 'admin@example.test', PASSWORD, PASSWORD)
        self.admin_token, _ = self.service.login('admin@example.test', PASSWORD, 'admin')
        self.admin = PersistentAdapter(DATA, self.service, self.admin_token)
        self.dataset = self.admin.load_dataset()
        user = self.service.register('Local employee', 'employee@example.test', PASSWORD, PASSWORD)
        self.user = user
        self.service.configure_user(self.admin_token, user['user_id'], 'employee', 'E0001', {'E0001', 'E0002'})
        self.employee_token, _ = self.service.login(user['email'], PASSWORD)
        self.employee = PersistentAdapter(DATA, self.service, self.employee_token)

    def test_employee_cannot_read_or_write_another_profile_or_administer(self):
        self.assertEqual([p['employee_id'] for p in self.employee.list_employees(self.dataset)], ['E0001'])
        calls = [
            lambda: self.employee.get_employee_view(self.dataset, 'E0002'),
            lambda: self.employee.complete_activity(self.dataset, 'E0002', 'EVT_TEST'),
            lambda: self.employee.get_hr_view(self.dataset),
            lambda: self.employee.import_test_data(self.dataset, b'{}'),
            lambda: self.employee.growth.snapshot(self.dataset, 'E0002'),
            lambda: self.employee.growth.store.rows('certificates'),
            lambda: self.employee.growth.store.rows('certificates', 'E0002'),
            lambda: self.employee.growth.save_profile(self.dataset, 'E0001', date.today(), {}, actor='hr'),
            lambda: self.employee.growth.review_certificate(self.dataset, 'fake', True, actor='hr'),
            lambda: self.employee.growth.decide_training('fake', True, 'ok', actor='hr'),
        ]
        for call in calls:
            with self.subTest(call=call), self.assertRaises(PermissionError):
                call()
        self.assertEqual(self.admin.dataset_store.read()[1], 0)

    def test_completion_and_import_survive_restart_without_lost_updates(self):
        before = self.employee.get_employee_view(self.dataset, 'E0001')
        rec = before['recommendations'][0]
        profile = deepcopy(self.dataset['employees'][0])
        profile.update(employee_id='PERSIST_001', full_name='Explicit storage test')
        uploaded = json.dumps({'employees': [profile]}).encode('utf-8')
        self.admin.import_test_data(self.dataset, uploaded)
        updated, after = self.employee.complete_activity(self.dataset, 'E0001', rec['event_id'])
        self.assertGreater(after['trajectory']['progress_pct'], before['trajectory']['progress_pct'])
        self.assertIn('PERSIST_001', {p['employee_id'] for p in updated['employees']})
        restarted = PersistentAdapter(DATA, AuthService(), self.employee_token)
        loaded = restarted.load_dataset()
        self.assertEqual(restarted.dataset_revision, 2)
        self.assertEqual(restarted.get_employee_view(loaded, 'E0001')['trajectory'], after['trajectory'])
        self.assertEqual(loaded['_growth_baselines'], updated['_growth_baselines'])
        with self.assertRaises(ValueError):
            restarted.complete_activity(loaded, 'E0001', rec['event_id'])
        self.assertEqual(restarted.dataset_store.read()[1], 2)

    def test_invalid_import_rolls_back(self):
        saved = self.admin.dataset_store.read()
        with self.assertRaises(ValueError):
            self.admin.import_test_data(self.dataset, b'{invalid')
        self.assertEqual(self.admin.dataset_store.read(), saved)

    def test_persisted_catalogue_wins_over_changed_seed_files(self):
        source = self.folder / 'new-starter-kit'
        source.mkdir()
        skills = json.loads((DATA / 'skills.json').read_text(encoding='utf-8-sig'))
        skills['skills'][0]['name'] = 'Changed seed must not replace stored catalogue'
        skills['role_profiles'] = []
        (source / 'skills.json').write_text(json.dumps(skills), encoding='utf-8')
        events = json.loads((DATA / 'events.json').read_text(encoding='utf-8-sig'))
        events['events'][0]['title'] = 'Changed event seed'
        (source / 'events.json').write_text(json.dumps(events), encoding='utf-8')
        adapter = PersistentAdapter(source, self.service, self.employee_token)
        stored = adapter.load_dataset()
        self.assertEqual(adapter.catalog, {s['skill_id']: s for s in stored['skills']})
        self.assertEqual(adapter.events, {e['event_id']: e for e in stored['events']})
        self.assertEqual(adapter.role_profiles, stored['role_profiles'])
        self.assertEqual(adapter.as_of_date, stored['as_of_date'])

    def test_role_change_revokes_existing_adapter_and_fragment_access(self):
        self.employee.growth.snapshot(self.dataset, 'E0001')
        self.service.configure_user(self.admin_token, self.user['user_id'], 'employee', 'E0002', {'E0001', 'E0002'})
        for action in [lambda: self.employee.load_dataset(),
                       lambda: self.employee.growth.snapshot(self.dataset, 'E0001'),
                       lambda: self.employee.get_employee_view(self.dataset, 'E0001')]:
            with self.assertRaises(AuthError):
                action()
        token, _ = self.service.login(self.user['email'], PASSWORD)
        new_adapter = PersistentAdapter(DATA, self.service, token)
        self.assertEqual([p['employee_id'] for p in new_adapter.list_employees(self.dataset)], ['E0002'])

    def test_certificate_review_and_xp_persist_across_accounts(self):
        hr_user = self.service.register('HR reviewer', 'hr@example.test', PASSWORD, PASSWORD)
        self.service.configure_user(self.admin_token, hr_user['user_id'], 'hr', None, {'E0001'})
        token, _ = self.service.login(hr_user['email'], PASSWORD, 'hr')
        hr = PersistentAdapter(DATA, self.service, token)
        before = self.employee.growth.snapshot(self.dataset, 'E0001')['learning_xp']
        certificate = self.employee.growth.submit_certificate(
            self.dataset, 'E0001', 'Explicit test course', 'Test provider',
            'https://example.org/test/course', date.today(), 'TEST-CERTIFICATE', [])
        hr.growth.review_certificate(self.dataset, certificate, True, {}, 'Test approval', actor='hr')
        restarted = PersistentAdapter(DATA, AuthService(), self.employee_token)
        state = restarted.growth.snapshot(restarted.load_dataset(), 'E0001')
        self.assertEqual(state['learning_xp'], before + 100)
        self.assertEqual(next(c for c in state['certificates'] if c['id'] == certificate)['status'], 'approved')
        with self.assertRaises(PermissionError):
            hr.complete_activity(self.dataset, 'E0001', 'fake')


if __name__ == '__main__':
    unittest.main()
