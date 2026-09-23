"""Mandatory HR courses reuse the shared plan, route and approval lifecycle."""

import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from core import api
from core.growth import GrowthService, GrowthStore, course_id, dump, now_iso
from core.growth_ai import fingerprint
from storage.dataset import DatasetStore
from ui.persistent_adapter import PersistentAdapter

DATA = Path(__file__).resolve().parents[2] / 'case/case_1/career_quest_dataset'


class MandatoryTrainingTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        environment = patch.dict(os.environ, {'OPENAI_API_KEY': '', 'NVIDIA_API_KEY': '',
                                              'CAREER_QUEST_AI_PROVIDER': 'none'})
        environment.start()
        self.addCleanup(environment.stop)
        self.store = GrowthStore(self.root / 'growth.sqlite3')
        self.service = GrowthService(self.store)
        self.data = api.load_dataset(str(DATA))
        self.plan_id, self.course_id = self.plan()

    def plan(self, suffix='mandatory'):
        course = {'title': 'SOC learning ' + suffix, 'provider': 'Microsoft Learn',
                  'url': 'https://learn.microsoft.com/training/paths/' + suffix,
                  'why': 'Practice approved skills', 'price_text': 'Уточнить у провайдера', 'level': 'Intermediate'}
        payload = {'summary': 'Test shared plan', 'tracks': [{'title': 'SOC', 'kind': 'specialization',
                   'explanation': 'Based on approved portfolio', 'basis_refs': ['role'],
                   'next_skills': ['SIEM'], 'courses': [course]}]}
        plan_id = uuid4().hex
        with self.store.connection() as db:
            db.execute('INSERT INTO plans VALUES (?,?,?,?,?)',
                       (plan_id, 'E0001', fingerprint(self.service.facts(self.data, 'E0001')), dump(payload), now_iso()))
        return plan_id, course_id(course['url'])

    def request(self, rid):
        return next(row for row in self.store.rows('training_requests', 'E0001') if row['id'] == rid)

    def assign(self, reason='Mandatory incident response practice'):
        return self.service.assign_course(self.data, 'E0001', self.plan_id, self.course_id, reason, actor='hr')

    def test_hr_assignment_is_approved_persistent_and_does_not_award_xp(self):
        xp = self.service.snapshot(self.data, 'E0001')['xp']
        rid = self.assign()
        row = self.request(rid)
        self.assertEqual(row['status'], 'approved')
        self.assertTrue(row['payload']['mandatory'])
        self.assertEqual(row['payload']['assigned_by'], 'hr')
        self.assertEqual(row['payload']['assignment_reason'], 'Mandatory incident response practice')
        self.assertEqual(self.service.snapshot(self.data, 'E0001')['xp'], xp)
        fresh = GrowthService(GrowthStore(self.store.path)).development_plan(self.data, 'E0001')
        self.assertTrue(fresh['requests'][0]['mandatory'])
        self.assertTrue(fresh['tracks'][0]['courses'][0]['mandatory'])
        self.assertEqual(fresh['tracks'][0]['courses'][0]['request_id'], rid)

    def test_invalid_owner_course_and_non_hr_are_denied(self):
        for role in ('employee', 'admin', None):
            with self.subTest(role=role), self.assertRaises(PermissionError):
                self.service.assign_course(self.data, 'E0001', self.plan_id, self.course_id, actor=role)
        for employee, plan, course in [('E0002', self.plan_id, self.course_id),
                                       ('E0001', 'missing-plan', self.course_id),
                                       ('E0001', self.plan_id, 'missing-course'),
                                       ('MISSING', self.plan_id, self.course_id)]:
            with self.subTest(employee=employee, plan=plan), self.assertRaises(ValueError):
                self.service.assign_course(self.data, employee, plan, course, actor='hr')
        self.assertEqual(self.store.rows('training_requests'), [])

    def test_pending_rejected_and_cancelled_become_approved_same_request(self):
        for status in ('pending', 'rejected', 'cancelled'):
            plan, cid = self.plan(status)
            rid = self.service.choose_course(self.data, 'E0001', plan, cid)
            if status == 'rejected':
                self.service.decide_training(rid, False, 'Earlier budget refusal', actor='hr')
            elif status == 'cancelled':
                self.service.cancel_training(self.data, 'E0001', rid)
            self.assertEqual(self.request(rid)['status'], status)
            assigned = self.service.assign_course(self.data, 'E0001', plan, cid, 'Now required by HR', actor='hr')
            self.assertEqual(assigned, rid)
            self.assertEqual(self.request(rid)['status'], 'approved')
            self.assertEqual(self.request(rid)['reason'], 'Now required by HR')

    def test_employee_cannot_cancel_and_regular_choice_preserves_assignment(self):
        rid = self.assign()
        with self.assertRaisesRegex(ValueError, 'Обязательное обучение'):
            self.service.cancel_training(self.data, 'E0001', rid)
        repeated = self.service.choose_course(self.data, 'E0001', self.plan_id, self.course_id)
        self.assertEqual(repeated, rid)
        self.assertEqual(self.request(rid)['status'], 'approved')
        self.assertTrue(self.request(rid)['payload']['mandatory'])
        self.service.start_training(self.data, 'E0001', rid)
        with self.assertRaisesRegex(ValueError, 'Обязательное обучение'):
            self.service.cancel_training(self.data, 'E0001', rid)

    def test_reassignment_preserves_active_and_completed_status_and_certificate(self):
        rid = self.assign()
        before = self.service.snapshot(self.data, 'E0001')['xp']
        self.service.start_training(self.data, 'E0001', rid)
        self.assertEqual(self.assign(), rid)
        self.assertEqual(self.request(rid)['status'], 'in_progress')
        cert = self.service.submit_training_completion(self.data, 'E0001', rid, date.today(),
                                                        'MANDATORY-CERT-001', ['SK_API_DESIGN'])
        self.assertEqual(self.assign(), rid)
        self.assertEqual(self.request(rid)['status'], 'completion_pending')
        self.assertEqual(self.request(rid)['certificate_id'], cert)
        self.service.review_certificate(self.data, cert, True, {'SK_API_DESIGN': 1}, actor='hr')
        self.assertEqual(self.service.snapshot(self.data, 'E0001')['xp'], before + 100)
        self.assertEqual(self.assign(), rid)
        self.assertEqual(self.service.choose_course(self.data, 'E0001', self.plan_id, self.course_id), rid)
        self.assertEqual(self.request(rid)['status'], 'completed')
        self.assertEqual(self.request(rid)['certificate_id'], cert)
        self.assertEqual(self.service.snapshot(self.data, 'E0001')['xp'], before + 100)
        self.assertEqual(len(self.store.rows('certificates', 'E0001')), 1)

    def test_custom_assignment_checks_https_and_non_hr(self):
        with self.assertRaises(PermissionError):
            self.service.assign_custom_course(self.data, 'E0001', 'Course', 'https://example.org/course')
        with self.assertRaises(ValueError):
            self.service.assign_custom_course(self.data, 'E0001', 'Course', 'http://example.org/course', actor='hr')
        rid = self.service.assign_custom_course(self.data, 'E0001', 'Course', 'https://example.org/course', actor='hr')
        row = self.request(rid)
        self.assertEqual(row['status'], 'approved')
        self.assertEqual(row['payload']['source'], 'hr')
        self.assertTrue(row['payload']['assignment_reason'])

    def test_parallel_assignment_is_idempotent(self):
        barrier = Barrier(2)
        def assign(_):
            barrier.wait(2)
            return self.assign()
        with ThreadPoolExecutor(2) as pool:
            assigned = list(pool.map(assign, range(2)))
        self.assertEqual(assigned[0], assigned[1])
        self.assertEqual(len(self.store.rows('training_requests', 'E0001')), 1)

    def test_persistent_boundary_hr_research_assignment_and_employee_ownership(self):
        class Session:
            user = {'role': 'hr', 'employee_id': None}
            def current_user(self, token):
                return dict(self.user)
        session = Session()
        dataset_store = DatasetStore(self.root / 'dataset.sqlite3')
        dataset_store.load_or_initialize(lambda: self.data)
        adapter = PersistentAdapter(DATA, session, 'synthetic-session', dataset_store)
        adapter._growth = self.service
        wrapper = adapter.growth
        with patch.object(self.service, 'start_research', return_value={'status': 'running'}) as research:
            wrapper.start_research({}, 'E0001')
            self.assertEqual(research.call_args.args[0]['employees'], self.data['employees'])
            self.assertEqual(research.call_args.args[1], 'E0001')
        with patch.object(self.service, 'recommend', return_value={'status': 'cached'}) as recommend:
            wrapper.recommend({}, 'E0001', generate=True)
            self.assertEqual(recommend.call_args.args[2], True)
        rid = wrapper.assign_course({}, 'E0001', self.plan_id, self.course_id)
        self.assertTrue(self.request(rid)['payload']['mandatory'])
        forged = deepcopy(self.data)
        forged['employees'].append(dict(self.data['employees'][0], employee_id='FORGED'))
        with self.assertRaises(ValueError):
            wrapper.assign_custom_course(forged, 'FORGED', 'Injected profile', 'https://example.org/forged')
        session.user = {'role': 'employee', 'employee_id': 'E0001'}
        with self.assertRaises(PermissionError):
            wrapper.assign_course(self.data, 'E0001', self.plan_id, self.course_id, actor='hr')
        with self.assertRaises(PermissionError):
            wrapper.assign_custom_course(self.data, 'E0001', 'Course', 'https://example.org/course', actor='hr')
        with self.assertRaises(PermissionError):
            wrapper.start_research(self.data, 'E0002')
        session.user = {'role': 'admin', 'employee_id': None}
        with self.assertRaises(PermissionError):
            wrapper.start_research(self.data, 'E0001')
        with self.assertRaises(PermissionError):
            wrapper.assign_course(self.data, 'E0001', self.plan_id, self.course_id, actor='hr')


if __name__ == '__main__':
    unittest.main()
