"""Persistence and state transitions of the shared map/course/route workflow."""

import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core import api
from core.growth import GrowthService, GrowthStore, course_id, dump, now_iso


DATA = Path(__file__).resolve().parents[2] / 'case/case_1/career_quest_dataset'
URL = 'https://learn.microsoft.com/en-us/training/paths/sc-200-mitigate-threats/'


class GrowthWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = GrowthStore(Path(self.temp.name) / 'growth.sqlite3')
        self.service = GrowthService(self.store)
        self.data = api.load_dataset(str(DATA))
        self.original = deepcopy(self.data)
        self.eid = 'E0001'
        self.env = patch.dict(os.environ, {'OPENAI_API_KEY': '', 'CAREER_QUEST_AI_PROVIDER': 'none'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.plan = {'summary': 'Следующий шаг', 'tracks': [{
            'title': 'Расследование угроз', 'kind': 'specialization', 'explanation': 'Продолжить практику.',
            'basis_refs': ['SK_API_DESIGN'], 'next_skills': ['Анализ угроз'], 'courses': [
                {'title': 'Расследование инцидентов', 'provider': 'Microsoft Learn', 'url': URL,
                 'why': 'Практика анализа', 'price_text': 'Уточнить', 'level': 'Intermediate'},
                {'title': 'Другой курс', 'provider': 'Microsoft Learn', 'url': URL + 'alternative',
                 'why': 'Ещё один вариант', 'price_text': 'Уточнить', 'level': 'Intermediate'}]}]}
        self.add_plan('first')

    def add_plan(self, pid, plan=None, employee_id=None, created_at=None):
        with self.store.connection() as db:
            db.execute('INSERT INTO plans(id,employee_id,fingerprint,payload,created_at) VALUES (?,?,?,?,?)',
                       (pid, employee_id or self.eid, 'test-fingerprint', dump(plan or self.plan), created_at or now_iso()))

    def read(self, pid='first', plan=None):
        with patch('core.growth_ai.GrowthAdvisor.read', create=True, return_value={
                **deepcopy(plan or self.plan), 'status': 'cached', 'plan_id': pid, 'budget': {'used': 0}}):
            return self.service.development_plan(self.data, self.eid)

    def choose(self, pid='first'):
        return self.service.choose_course(self.data, self.eid, pid, course_id(URL))

    def request(self, rid):
        return next(row for row in self.store.rows('training_requests', self.eid) if row['id'] == rid)

    def ready_to_complete(self):
        rid = self.choose()
        self.service.decide_training(rid, True, 'Бюджет согласован', actor='hr')
        self.service.start_training(self.data, self.eid, rid)
        return rid

    def complete(self, rid, evidence='Certificate CQ-verified'):
        return self.service.submit_training_completion(self.data, self.eid, rid, date.today(), evidence,
                                                       ['SK_API_DESIGN'], 'Анализ угроз')

    def test_multiple_choices_idempotence_and_restart(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: self.choose(), range(2)))
        self.assertEqual(ids[0], ids[1])
        other = self.service.choose_course(self.data, self.eid, 'first', course_id(URL + 'alternative'))
        self.assertNotEqual(ids[0], other)
        fresh = GrowthService(GrowthStore(self.store.path))
        self.assertEqual(fresh.choose_course(self.data, self.eid, 'first', course_id(URL)), ids[0])
        self.assertEqual(len(fresh.snapshot(self.data, self.eid)['requests']), 2)
        course = self.read()['tracks'][0]['courses'][0]
        self.assertEqual((course['id'], course['status'], course['request_id']), (course_id(URL), 'pending', ids[0]))
        self.assertEqual(course['reason'], 'Практика анализа')
        self.assertEqual(self.data, self.original)

    def test_hr_projection_matches_confirmed_employee_skills_without_mutating_kit(self):
        rid = self.ready_to_complete()
        cid = self.complete(rid)
        self.service.review_certificate(self.data, cid, True, {'SK_API_DESIGN': 1}, actor='hr')
        candidate = self.service.approved_dataset(self.data)
        state = self.service.snapshot(self.data, self.eid)
        person = next(p for p in candidate['employees'] if p['employee_id'] == self.eid)
        self.assertEqual(person['skills'], state['skills'])
        self.assertEqual(api.get_employee_view(candidate, self.eid)['skills'], state['view']['skills'])
        self.assertEqual(self.data, self.original)

    def test_hide_restore_persists_across_refresh_without_xp_or_cancelling(self):
        before = self.service.snapshot(self.data, self.eid)['xp']
        rid = self.choose()
        self.service.hide_course(self.data, self.eid, 'first', course_id(URL))
        self.add_plan('second')
        self.service = GrowthService(GrowthStore(self.store.path))
        model = self.read('second')
        self.assertTrue(model['tracks'][0]['courses'][0]['hidden'])
        self.assertEqual(model['hidden_count'], 1)
        self.assertEqual(self.request(rid)['status'], 'pending')
        self.service.hide_course(self.data, self.eid, 'second', course_id(URL), hidden=False)
        self.assertFalse(self.read('second')['tracks'][0]['courses'][0]['hidden'])
        self.assertEqual(self.service.snapshot(self.data, self.eid)['xp'], before)

    def test_new_plan_cannot_remove_route_or_hr_decision(self):
        rid = self.choose()
        self.service.decide_training(rid, False, 'В этом месяце нет бюджета', actor='hr')
        new = deepcopy(self.plan)
        new['tracks'][0]['courses'] = [new['tracks'][0]['courses'][1]]
        self.add_plan('second', new)
        route = self.read('second', new)['requests']
        self.assertEqual(len(route), 1)
        self.assertEqual((route[0]['id'], route[0]['status']), (rid, 'rejected'))
        self.assertIn('нет бюджета', route[0]['reason'])
        self.assertEqual(self.choose(), rid)
        self.assertEqual(self.request(rid)['status'], 'rejected')

    def test_expired_plan_is_explicitly_selectable_by_stable_identifier(self):
        old = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()
        self.add_plan('old', created_at=old)
        self.assertEqual(self.request(self.choose('old'))['status'], 'pending')

    def test_custom_url_is_employee_proposal_and_deduplicates_tracking(self):
        rid = self.service.add_custom_course(self.data, self.eid, 'Свой курс',
                                             'https://example.org/courses/analysis?utm_source=one', 'Нужен для проекта')
        again = self.service.add_custom_course(self.data, self.eid, 'Свой курс',
                                               'https://example.org/courses/analysis?utm_source=two', 'Нужен для проекта')
        self.assertEqual(rid, again)
        row = self.request(rid)
        self.assertEqual(row['payload']['source'], 'employee')
        self.assertEqual(row['status'], 'pending')
        for url in ['http://example.org/course', 'https://127.0.0.1/course', 'https://user:pass@example.org/course']:
            with self.assertRaises(ValueError):
                self.service.add_custom_course(self.data, self.eid, 'Курс', url, 'Для проекта')

    def test_ownership_and_unknown_ids_cannot_change_workflow(self):
        rid = self.choose()
        with self.assertRaises(ValueError):
            self.service.choose_course(self.data, 'E0002', 'first', course_id(URL))
        with self.assertRaises(ValueError):
            self.service.hide_course(self.data, 'E0002', 'first', course_id(URL))
        for method in [self.service.cancel_training, self.service.start_training]:
            with self.assertRaises(ValueError):
                method(self.data, 'E0002', rid)
        with self.assertRaises(ValueError):
            self.service.submit_training_completion(self.data, 'E0002', rid, date.today(), 'evidence', [])
        with self.assertRaises(ValueError):
            self.service.choose_course(self.data, self.eid, 'first', 'invented-course')
        self.assertEqual(self.request(rid)['status'], 'pending')

    def test_cancel_is_idempotent_and_has_no_xp_effect(self):
        before = self.service.snapshot(self.data, self.eid)['xp']
        rid = self.choose()
        self.service.cancel_training(self.data, self.eid, rid)
        self.service.cancel_training(self.data, self.eid, rid)
        self.assertEqual(self.request(rid)['status'], 'cancelled')
        with self.assertRaises(ValueError):
            self.service.decide_training(rid, True, 'Одобрено', actor='hr')
        with self.assertRaises(ValueError):
            self.service.start_training(self.data, self.eid, rid)
        self.assertEqual(self.service.snapshot(self.data, self.eid)['xp'], before)

    def test_completion_requires_started_approved_training(self):
        rid = self.choose()
        with self.assertRaises(ValueError):
            self.service.start_training(self.data, self.eid, rid)
        with self.assertRaises(ValueError):
            self.complete(rid)
        self.service.decide_training(rid, True, 'Одобрено', actor='hr')
        with self.assertRaises(ValueError):
            self.complete(rid)
        self.service.start_training(self.data, self.eid, rid)
        self.service.start_training(self.data, self.eid, rid)
        with self.assertRaises(ValueError):
            self.service.submit_training_completion(self.data, self.eid, rid,
                date.today()+timedelta(days=1), 'evidence', [])
        self.assertEqual(self.request(rid)['status'], 'in_progress')

    def test_hr_certificate_approval_grants_once_then_completes_route(self):
        before = self.service.snapshot(self.data, self.eid)
        rid = self.ready_to_complete()
        with ThreadPoolExecutor(max_workers=2) as pool:
            certificates = list(pool.map(lambda _: self.complete(rid), range(2)))
        self.assertEqual(certificates[0], certificates[1])
        self.assertEqual(self.request(rid)['status'], 'completion_pending')
        self.assertEqual(self.service.snapshot(self.data, self.eid)['xp'], before['xp'])
        with self.assertRaises(ValueError):
            self.service.cancel_training(self.data, self.eid, rid)
        self.service.review_certificate(self.data, certificates[0], True, {'SK_API_DESIGN': 1}, actor='hr')
        after = self.service.snapshot(self.data, self.eid)
        self.assertEqual(after['xp'], before['xp'] + 100)
        self.assertEqual(after['skills']['SK_API_DESIGN'], min(5, before['skills']['SK_API_DESIGN'] + 1))
        self.assertEqual(self.request(rid)['status'], 'completed')
        self.assertEqual(self.complete(rid), certificates[0])
        with self.assertRaises(ValueError):
            self.service.review_certificate(self.data, certificates[0], True, actor='hr')
        self.assertEqual(self.service.snapshot(self.data, self.eid)['xp'], after['xp'])

    def test_rejected_evidence_can_be_corrected_without_new_certificate_or_xp(self):
        before = self.service.snapshot(self.data, self.eid)['xp']
        rid = self.ready_to_complete()
        cid = self.complete(rid)
        self.service.review_certificate(self.data, cid, False, reason='Укажите проверяемый номер', actor='hr')
        self.assertEqual(self.request(rid)['status'], 'in_progress')
        self.assertEqual(self.service.snapshot(self.data, self.eid)['xp'], before)
        self.assertEqual(self.complete(rid, 'corrected-evidence'), cid)
        certificate = self.store.rows('certificates', self.eid)[0]
        self.assertEqual(certificate['status'], 'pending')
        self.assertEqual(certificate['payload']['evidence'], 'corrected-evidence')
        self.service.review_certificate(self.data, cid, True, actor='hr')
        self.assertEqual(self.service.snapshot(self.data, self.eid)['xp'], before + 100)
        self.assertEqual(len(self.store.rows('certificates', self.eid)), 1)

    def test_existing_approved_certificate_is_not_awarded_again(self):
        cid = self.service.submit_certificate(self.data, self.eid, 'Пройденный курс', 'Microsoft', URL,
                                              date.today(), 'original-evidence', ['SK_API_DESIGN'])
        self.service.review_certificate(self.data, cid, True, {'SK_API_DESIGN': 1}, actor='hr')
        xp = self.service.snapshot(self.data, self.eid)['xp']
        rid = self.ready_to_complete()
        self.assertEqual(self.complete(rid), cid)
        self.assertEqual(self.request(rid)['status'], 'completed')
        self.assertEqual(self.service.snapshot(self.data, self.eid)['xp'], xp)


if __name__ == '__main__':
    unittest.main()
