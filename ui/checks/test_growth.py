import json
import os
import tempfile
import unittest
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from unittest.mock import patch

from core import api
from core.growth import GrowthService, GrowthStore, TRAITS
from core.growth_ai import GrowthAdvisor, request_payload

DATA = Path(__file__).resolve().parents[2] / 'case/case_1/career_quest_dataset'


def provider_response(facts, url='https://learn.microsoft.com/en-us/training/paths/sc-200-mitigate-threats/'):
    plan = {'summary': 'Подтверждённые навыки дают базу для углубления.', 'tracks': [{
        'title': 'SOC: следующий уровень', 'kind': 'specialization', 'explanation': 'Развивайте анализ угроз.',
        'basis_refs': [facts['skills'][0]['ref']], 'next_skills': ['Анализ инцидентов'],
        'courses': [{'title': 'Mitigate threats using Microsoft Defender XDR', 'provider': 'Microsoft Learn',
                     'url': url, 'level': 'Intermediate', 'price_text': 'Уточнить у провайдера', 'why': 'Практика расследования угроз.'}]}]}
    return {'status': 'completed', 'usage': {'input_tokens': 1800, 'output_tokens': 700}, 'output': [
        {'type': 'web_search_call', 'action': {'sources': [{'url': url}]}},
        {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(plan), 'annotations': []}]}]}


class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = GrowthStore(Path(self.temp.name) / 'growth.sqlite3')
        self.service = GrowthService(self.store)
        self.data = api.load_dataset(str(DATA))
        self.eid = 'E0001'
        self.env = patch.dict(os.environ, {'OPENAI_API_KEY': '', 'CAREER_QUEST_GROWTH_BUDGET_USD': '5', 'CAREER_QUEST_GROWTH_REQUEST_USD': '.10', 'CAREER_QUEST_AI_PROVIDER': 'none'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def submit(self, suffix='one'):
        return self.service.submit_certificate(self.data, self.eid, 'SOC analyst course', 'Microsoft',
            'https://learn.microsoft.com/training/' + suffix, date.today(), 'Certificate CQ-001', ['SK_API_DESIGN'], 'SOC, SIEM')

    def test_hr_traits_and_elapsed_days_xp_survive_new_connection(self):
        started = date.today() - timedelta(days=17)
        with self.assertRaises(PermissionError):
            self.service.save_profile(self.data, self.eid, started, dict.fromkeys(TRAITS, 4))
        self.service.save_profile(self.data, self.eid, started, dict.fromkeys(TRAITS, 4), actor='hr')
        fresh = GrowthService(GrowthStore(self.store.path))
        current = fresh.snapshot(self.data, self.eid)
        self.assertEqual(current['xp'], 170)
        self.assertEqual(current['profile']['traits'], dict.fromkeys(TRAITS, 4))
        self.assertEqual(fresh.snapshot(self.data, self.eid, date.today()+timedelta(days=1))['xp'], 180)

    def test_approval_changes_skills_xp_once_and_never_mutates_kit(self):
        original = deepcopy(self.data)
        before = self.service.snapshot(self.data, self.eid)
        cid = self.submit()
        self.assertEqual(self.service.snapshot(self.data, self.eid)['xp'], before['xp'])
        self.assertEqual(self.service.facts(self.data, self.eid)['certificates'], [])
        with self.assertRaises(PermissionError):
            self.service.review_certificate(self.data, cid, True, {'SK_API_DESIGN': 1})
        self.service.review_certificate(self.data, cid, True, {'SK_API_DESIGN': 1}, actor='hr')
        after = self.service.snapshot(self.data, self.eid)
        self.assertEqual(after['xp'], before['xp'] + 100)
        self.assertEqual(after['skills']['SK_API_DESIGN'], min(5, before['skills']['SK_API_DESIGN'] + 1))
        self.assertEqual(self.service.facts(self.data, self.eid)['certificates'][0]['tags'], 'SOC, SIEM')
        with self.assertRaises(ValueError):
            self.service.review_certificate(self.data, cid, True, {'SK_API_DESIGN': 1}, actor='hr')
        self.assertEqual(self.data, original)

    def test_rejection_duplicate_and_invalid_awards(self):
        cid = self.submit()
        with self.assertRaises(ValueError):
            self.submit()
        with self.assertRaises(ValueError):
            self.service.review_certificate(self.data, cid, False, actor='hr')
        with self.assertRaises(ValueError):
            self.service.review_certificate(self.data, cid, True, {'SK_API_DESIGN': 7}, actor='hr')
        self.service.review_certificate(self.data, cid, False, reason='Нужен проверяемый сертификат', actor='hr')
        self.assertEqual(self.service.snapshot(self.data, self.eid)['learning_xp'], 0)
        self.assertEqual(self.store.rows('certificates')[0]['reason'], 'Нужен проверяемый сертификат')

    def test_future_start_never_gives_negative_xp(self):
        self.service.save_profile(self.data, self.eid, date.today()+timedelta(days=30), dict.fromkeys(TRAITS, 0), actor='hr')
        self.assertEqual(self.service.snapshot(self.data, self.eid)['xp'], 0)

    def test_missing_key_never_calls_provider_or_reserves_money(self):
        with patch('core.growth_ai._bounded_http') as transport:
            result = self.service.recommend(self.data, self.eid, generate=True)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['budget']['used'], 0)
        transport.assert_not_called()

    def test_request_search_bound_and_no_private_identity(self):
        facts = self.service.facts(self.data, self.eid)
        payload, bound = request_payload(facts)
        self.assertLess(bound, 100000)
        self.assertEqual(payload['max_tool_calls'], 1)
        self.assertEqual(payload['tool_choice'], 'required')
        self.assertFalse(payload['store'])
        self.assertNotIn('Marat', payload['input'])
        self.assertNotIn(self.eid, payload['input'])

    def test_verified_course_cache_request_and_hr_budget_rejection(self):
        facts = self.service.facts(self.data, self.eid)
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token'}), \
             patch('core.growth_ai._bounded_http', return_value=provider_response(facts)) as transport:
            plan = self.service.recommend(self.data, self.eid, True)
            cached = self.service.recommend(self.data, self.eid, True)
        self.assertEqual(plan['status'], 'generated')
        self.assertEqual(cached['status'], 'cached')
        self.assertEqual(transport.call_count, 1)
        self.assertLess(plan['budget']['used'], .10)
        rid = self.service.request_training(self.data, self.eid, plan['plan_id'], 0, 0)
        with self.assertRaises(PermissionError):
            self.service.decide_training(rid, False, 'Нет бюджета')
        self.service.decide_training(rid, False, 'Нет бюджета в этом квартале', actor='hr')
        decision = GrowthService(GrowthStore(self.store.path)).snapshot(self.data, self.eid)['requests'][0]
        self.assertEqual(decision['status'], 'rejected')
        self.assertIn('Нет бюджета', decision['reason'])
        with self.assertRaises(ValueError):
            self.service.request_training(self.data, self.eid, plan['plan_id'], 0, 0)

    def test_uncited_course_is_omitted(self):
        body = provider_response(self.service.facts(self.data, self.eid))
        body['output'][0]['action']['sources'] = [{'url': 'https://learn.microsoft.com/training/something-else'}]
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token'}), patch('core.growth_ai._bounded_http', return_value=body):
            result = self.service.recommend(self.data, self.eid, True)
        self.assertEqual(result['tracks'][0]['courses'], [])

    def test_timeout_reserves_full_cap_and_prevents_overspending(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token', 'CAREER_QUEST_GROWTH_BUDGET_USD': '.1'}), \
             patch('core.growth_ai._bounded_http', side_effect=TimeoutError) as transport:
            first = self.service.recommend(self.data, self.eid, True)
            second = self.service.recommend(self.data, 'E0002', True)
        self.assertEqual(first['status'], 'fallback')
        self.assertEqual(second['status'], 'budget')
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(first['budget']['used'], .1)

    def test_changed_portfolio_invalidates_plan(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token'}), \
             patch('core.growth_ai._bounded_http', return_value=provider_response(self.service.facts(self.data, self.eid))):
            plan = self.service.recommend(self.data, self.eid, True)
        self.service.review_certificate(self.data, self.submit(), True, {'SK_API_DESIGN': 1}, actor='hr')
        self.assertEqual(self.service.recommend(self.data, self.eid)['status'], 'ready')
        with self.assertRaises(ValueError):
            self.service.request_training(self.data, self.eid, plan['plan_id'], 0, 0)

    def test_plan_expiry_and_training_approval_never_awards_completion_xp(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token'}), \
             patch('core.growth_ai._bounded_http', return_value=provider_response(self.service.facts(self.data, self.eid))):
            plan = self.service.recommend(self.data, self.eid, True)
        for track, course in [(-1, 0), (0, -1), (False, 0)]:
            with self.assertRaises(ValueError):
                self.service.request_training(self.data, self.eid, plan['plan_id'], track, course)
        before = self.service.snapshot(self.data, self.eid)['xp']
        rid = self.service.request_training(self.data, self.eid, plan['plan_id'], 0, 0)
        self.service.decide_training(rid, True, 'Бюджет согласован', actor='hr')
        self.assertEqual(self.service.snapshot(self.data, self.eid)['xp'], before)
        with self.assertRaises(ValueError):
            self.service.decide_training(rid, True, 'Повторное решение', actor='hr')
        with self.store.connection() as db:
            db.execute('UPDATE plans SET created_at=?', ((datetime.now(timezone.utc)-timedelta(days=8)).isoformat(),))
        with self.assertRaisesRegex(ValueError, 'устарел'):
            self.service.request_training(self.data, self.eid, plan['plan_id'], 0, 0)

    def test_simultaneous_employees_cannot_reserve_more_than_total_budget(self):
        barrier = Barrier(2)
        facts = [self.service.facts(self.data, eid) for eid in (self.eid, 'E0002')]
        def request(index):
            barrier.wait(timeout=10)
            return GrowthAdvisor(GrowthStore(self.store.path)).recommend(('E0001', 'E0002')[index], facts[index], True)
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token', 'CAREER_QUEST_GROWTH_BUDGET_USD': '.1'}), \
             patch('core.growth_ai._bounded_http', side_effect=TimeoutError) as transport, ThreadPoolExecutor(2) as pool:
            results = list(pool.map(request, range(2)))
            budget = GrowthAdvisor(self.store).budget()
        self.assertCountEqual([r['status'] for r in results], ['fallback', 'budget'])
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(budget['used'], .1)


if __name__ == '__main__':
    unittest.main()
