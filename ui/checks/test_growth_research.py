"""Metered research contracts; all transports mocked, all storage temporary."""

import io
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.growth import GrowthStore, dump, now_iso
from core.growth_ai import GrowthAdvisor, ResearchError, _http, request_payload


FACTS = {'role': 'SOC analyst', 'grade': 'Junior', 'goal': 'Middle', 'traits': {},
         'skills': [{'ref': 'skill:siem', 'name': 'SIEM', 'level': 2}], 'certificates': []}
URLS = ['https://learn.microsoft.com/en-us/training/paths/sc-200-mitigate-threats/',
        'https://learn.microsoft.com/en-us/training/paths/sc-200-utilize-kql-for-azure-sentinel/']


def response(facts=FACTS, urls=URLS):
    plan = {'summary': 'Продолжите изучать расследование инцидентов.', 'tracks': [{
        'title': 'SOC: расследование', 'kind': 'specialization', 'explanation': 'Основа — подтверждённый SIEM.',
        'basis_refs': [facts['skills'][0]['ref']], 'next_skills': ['KQL'],
        'courses': [{'title': f'Практикум {index}', 'provider': 'Microsoft Learn', 'url': url,
                     'level': 'Intermediate', 'price_text': 'Уточнить у провайдера', 'why': 'Практика расследования.'}
                    for index, url in enumerate(urls)]}]}
    return {'status': 'completed', '_request_id': 'req_test_123',
            'usage': {'input_tokens': 1800, 'output_tokens': 700,
                      'output_tokens_details': {'reasoning_tokens': 500}},
            'output': [{'type': 'web_search_call', 'action': {'sources': [{'url': u} for u in urls]}},
                       {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(plan), 'annotations': []}]}]}


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = GrowthStore(Path(self.directory.name) / 'research.sqlite3')
        self.advisor = GrowthAdvisor(self.store)
        self.env = patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token',
                                           'CAREER_QUEST_GROWTH_BUDGET_USD': '5',
                                           'CAREER_QUEST_GROWTH_REQUEST_USD': '.10'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def settled(self, employee='E1', facts=FACTS):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = self.advisor.read(employee, facts)
            if result['status'] != 'running':
                return result
            time.sleep(.01)
        self.fail('Mocked background research did not finish')

    def age_attempt(self, days=0, seconds=0, plans=False):
        stamp = (datetime.now(timezone.utc) - timedelta(days=days, seconds=seconds)).isoformat()
        with self.store.connection() as db:
            db.execute('UPDATE ai_jobs SET created_at=?', (stamp,))
            if plans:
                db.execute('UPDATE plans SET created_at=?', (stamp,))

    def test_gpt5_low_reasoning_output_and_search_estimate(self):
        payload, estimate = request_payload(FACTS)
        self.assertEqual(payload['model'], 'gpt-5')
        self.assertEqual(payload['reasoning'], {'effort': 'low'})
        self.assertEqual(payload['max_output_tokens'], 3000)
        self.assertEqual(payload['max_tool_calls'], 1)
        self.assertLess(estimate, 100000)
        self.assertNotIn('return_token_budget', payload['tools'][0])

    def test_first_map_starts_once_background_navigation_reads_are_free(self):
        entered, release = threading.Event(), threading.Event()
        def transport(*args):
            entered.set()
            release.wait(4)
            return response()
        with patch('core.growth_ai._bounded_http', side_effect=transport) as mocked:
            first = self.advisor.start('E1', FACTS, trigger='auto')
            self.assertTrue(entered.wait(1))
            try:
                self.assertEqual(first['status'], 'running')
                for _ in range(3):
                    self.assertEqual(self.advisor.start('E1', FACTS, 'auto')['job_id'], first['job_id'])
                    self.advisor.read('E1', FACTS)
                self.assertEqual(mocked.call_count, 1)
            finally:
                release.set()
            done = self.settled()
        self.assertEqual(done['status'], 'cached')
        self.assertFalse(done['auto_due'])
        self.assertEqual(done['request_id'], 'req_test_123')
        self.assertEqual(len(done['tracks'][0]['courses']), 2)
        self.assertAlmostEqual(done['budget']['used'], .01925)

    def test_weekly_cache_stale_portfolio_and_explicit_refresh(self):
        with patch('core.growth_ai._bounded_http', return_value=response()) as mocked:
            self.advisor.start('E1', FACTS, 'auto')
            old = self.settled()
            changed = deepcopy(FACTS)
            changed['skills'][0]['level'] = 3
            stale = self.advisor.start('E1', changed, 'auto')
            self.assertEqual(stale['status'], 'stale')
            self.assertEqual(stale['plan_id'], old['plan_id'])
            self.assertTrue(stale['tracks'])
            self.assertEqual(mocked.call_count, 1)
            self.age_attempt(seconds=61)
            self.advisor.start('E1', changed, 'manual')
            new = self.settled(facts=changed)
            self.assertNotEqual(new['plan_id'], old['plan_id'])
            self.assertFalse(new['is_stale'])
            self.assertEqual(mocked.call_count, 2)
            self.age_attempt(days=8, plans=True)
            self.assertTrue(self.advisor.read('E1', changed)['auto_due'])
            self.advisor.start('E1', changed, 'auto')
            self.settled(facts=changed)
            self.assertEqual(mocked.call_count, 3)

    def test_manual_refresh_bypasses_fresh_cache_and_obeys_cooldown(self):
        with patch('core.growth_ai._bounded_http', return_value=response()) as mocked:
            self.advisor.start('E1', FACTS)
            first = self.settled()
            self.advisor.start('E1', FACTS)
            self.assertEqual(mocked.call_count, 1)
            self.age_attempt(seconds=61)
            self.advisor.start('E1', FACTS)
            second = self.settled()
        self.assertEqual(mocked.call_count, 2)
        self.assertNotEqual(first['plan_id'], second['plan_id'])

    def test_failure_never_retries_automatically_even_after_week(self):
        with patch('core.growth_ai._bounded_http', side_effect=TimeoutError) as mocked:
            self.advisor.start('E1', FACTS, 'auto')
            failed = self.settled()
            self.age_attempt(days=8)
            self.advisor.start('E1', FACTS, 'auto')
            result = self.advisor.read('E1', FACTS)
        self.assertEqual(failed['error_code'], 'timeout')
        self.assertEqual(result['job_id'], failed['job_id'])
        self.assertFalse(result['auto_due'])
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(GrowthAdvisor(GrowthStore(self.store.path)).budget()['used'], .1)

    def test_no_key_attempt_persists_without_cost_or_repeat(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}), patch('core.growth_ai._bounded_http') as mocked:
            first = self.advisor.start('E1', FACTS, 'auto')
            second = self.advisor.start('E1', FACTS, 'auto')
        self.assertEqual(first['status'], 'unavailable')
        self.assertEqual(first['error_code'], 'no_key')
        self.assertEqual(first['job_id'], second['job_id'])
        self.assertEqual(first['budget']['used'], 0)
        mocked.assert_not_called()

    def test_oversized_estimate_never_contacts_provider(self):
        large = deepcopy(FACTS)
        large['goal'] = 'a' * 25000
        with patch('core.growth_ai._bounded_http') as mocked:
            result = self.advisor.start('E1', large)
        self.assertEqual(result['error_code'], 'estimate_over_cap')
        self.assertEqual(result['budget']['used'], 0)
        mocked.assert_not_called()

    def test_existing_unknown_charge_remains_after_restart(self):
        with self.store.connection() as db:
            db.execute('INSERT INTO ai_calls VALUES (?,?,?,?,?,?,?,?)',
                       ('legacy', 'legacy-fp', 'gpt-4.1-mini', 'unknown', 100000, 100000, '{}', now_iso()))
        with patch('core.growth_ai._bounded_http', return_value=response()):
            self.advisor.start('E1', FACTS)
            self.settled()
        fresh = GrowthAdvisor(GrowthStore(self.store.path))
        self.assertAlmostEqual(fresh.budget()['used'], .11925)

    def test_crashed_running_reservation_becomes_unknown_after_restart(self):
        stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with self.store.connection() as db:
            db.execute('INSERT INTO ai_calls VALUES (?,?,?,?,?,?,?,?)',
                       ('crashed', 'fp', 'gpt-5', 'running', 100000, 0, '{}', stale))
            db.execute('INSERT INTO ai_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       ('job', 'E1', 'fp', 'auto', 'running', 'crashed', None, '', '', 80000, stale, stale))
        result = GrowthAdvisor(GrowthStore(self.store.path)).read('E1', FACTS)
        self.assertEqual(result['error_code'], 'interrupted')
        self.assertEqual(result['budget']['used'], .1)
        self.assertFalse(result['auto_due'])

    def test_parallel_start_same_employee_has_one_reservation(self):
        entered, release = threading.Event(), threading.Event()
        barrier = threading.Barrier(2)
        def transport(*args):
            entered.set()
            release.wait(4)
            return response()
        def start(_):
            barrier.wait(2)
            return GrowthAdvisor(GrowthStore(self.store.path)).start('E1', FACTS, 'auto')
        with patch('core.growth_ai._bounded_http', side_effect=transport) as mocked:
            try:
                with ThreadPoolExecutor(2) as pool:
                    results = list(pool.map(start, range(2)))
                self.assertTrue(entered.wait(1))
                self.assertEqual(results[0]['job_id'], results[1]['job_id'])
                self.assertEqual(mocked.call_count, 1)
                self.assertEqual(self.advisor.budget()['used'], .1)
            finally:
                release.set()
            self.settled()

    def test_safe_error_codes_request_ids_and_known_unbilled_errors(self):
        for index, code in enumerate(('authentication', 'model_access', 'invalid_request', 'quota', 'rate_limit')):
            with self.subTest(code=code), patch('core.growth_ai._bounded_http',
                    side_effect=ResearchError(code, 'req_safe', known_unbilled=True)):
                self.advisor.start(f'E{index}', FACTS)
                result = self.settled(f'E{index}')
            self.assertEqual(result['error_code'], code)
            self.assertEqual(result['request_id'], 'req_safe')
            self.assertEqual(result['budget']['used'], 0)

    def test_invalid_response_records_known_usage_and_preserves_previous_plan(self):
        with patch('core.growth_ai._bounded_http', return_value=response()):
            self.advisor.start('E1', FACTS)
            first = self.settled()
        self.age_attempt(seconds=61)
        malformed = response()
        malformed['output'][1]['content'][0]['text'] = 'not JSON'
        with patch('core.growth_ai._bounded_http', return_value=malformed):
            self.advisor.start('E1', FACTS)
            result = self.settled()
        self.assertEqual(result['error_code'], 'response_validation')
        self.assertEqual(result['plan_id'], first['plan_id'])
        self.assertEqual(result['tracks'], first['tracks'])
        self.assertAlmostEqual(result['budget']['used'], .0385)

    def test_provider_overage_recorded_in_full_never_clipped(self):
        expensive = response()
        expensive['usage']['input_tokens'] = 100000
        with patch('core.growth_ai._bounded_http', return_value=expensive):
            self.advisor.start('E1', FACTS)
            result = self.settled()
        self.assertEqual(result['error_code'], 'usage_over_cap')
        self.assertAlmostEqual(result['budget']['used'], .142)
        self.assertIsNone(result['plan_id'])

    def test_incomplete_reasoning_response_preserves_safe_diagnostics_and_known_cost(self):
        incomplete = response()
        incomplete.update(status='incomplete', incomplete_details={'reason': 'max_output_tokens'})
        incomplete['usage']['output_tokens'] = 3000
        incomplete['usage']['output_tokens_details']['reasoning_tokens'] = 2990
        incomplete['output'] = incomplete['output'][:1]
        with patch('core.growth_ai._bounded_http', return_value=incomplete):
            self.advisor.start('E1', FACTS)
            result = self.settled()
        self.assertEqual(result['error_code'], 'response_incomplete')
        self.assertAlmostEqual(result['budget']['used'], .04225)
        with self.store.connection() as db:
            usage = json.loads(db.execute('SELECT usage FROM ai_calls').fetchone()[0])
        self.assertEqual(usage['diagnostics'], {'response_id': '', 'response_status': 'incomplete', 'incomplete_reason': 'max_output_tokens',
                                              'search_calls': 1, 'output_text_bytes': 0, 'validation_reason': 'response_incomplete',
                                              'search_actions': [{'id': '', 'type': 'web_search_call', 'action': 'unknown', 'status': 'unknown'}]})
        self.assertEqual(usage['output_tokens_details']['reasoning_tokens'], 2990)
        self.assertNotIn('SOC', dump(usage))

    def test_invalid_json_diagnostics_never_store_provider_text(self):
        malformed = response()
        malformed['output'][1]['content'][0]['text'] = 'private-provider-prose'
        with patch('core.growth_ai._bounded_http', return_value=malformed):
            self.advisor.start('E1', FACTS)
            self.settled()
        with self.store.connection() as db:
            usage_text = db.execute('SELECT usage FROM ai_calls').fetchone()[0]
        usage = json.loads(usage_text)
        self.assertEqual(usage['diagnostics']['validation_reason'], 'invalid_json')
        self.assertEqual(usage['diagnostics']['output_text_bytes'], 22)
        self.assertNotIn('private-provider-prose', usage_text)

    def test_extra_search_item_records_safe_action_diagnostics(self):
        extra = response()
        extra['id'] = 'resp_safe_123'
        extra['output'][0].update(id='ws_first', status='completed')
        extra['output'][0]['action']['type'] = 'search'
        extra['output'].insert(1, {'type': 'web_search_call', 'id': 'ws_second', 'status': 'searching',
                                   'action': {'type': 'open_page', 'url': 'https://example.com/private-data'}})
        with patch('core.growth_ai._bounded_http', return_value=extra):
            self.advisor.start('E1', FACTS)
            result = self.settled()
        self.assertEqual(result['error_code'], 'response_validation')
        with self.store.connection() as db:
            usage_text = db.execute('SELECT usage FROM ai_calls').fetchone()[0]
        diagnostics = json.loads(usage_text)['diagnostics']
        self.assertEqual(diagnostics['validation_reason'], 'search_count')
        self.assertEqual(diagnostics['response_id'], 'resp_safe_123')
        self.assertEqual(diagnostics['search_calls'], 2)
        self.assertEqual(diagnostics['search_actions'][1], {'id': 'ws_second', 'type': 'web_search_call',
                                                          'action': 'open_page', 'status': 'searching'})
        self.assertNotIn('private-data', usage_text)

    def test_http_error_payload_cannot_leak_key_or_provider_message(self):
        for status, api_code, safe_code in ((401, 'invalid_api_key', 'authentication'),
                                          (404, 'model_not_found', 'model_access'),
                                          (400, 'unknown_parameter', 'invalid_request'),
                                          (429, 'insufficient_quota', 'quota'),
                                          (429, 'rate_limit_exceeded', 'rate_limit')):
            body = io.BytesIO(json.dumps({'error': {'code': api_code, 'message': 'secret synthetic-key'}}).encode())
            error = urllib.error.HTTPError('https://api.openai.com/v1/responses', status, 'secret synthetic-key',
                                           {'x-request-id': 'req_http'}, body)
            with self.subTest(status=status, code=api_code), patch('urllib.request.urlopen', side_effect=error):
                with self.assertRaises(ResearchError) as raised:
                    _http({}, 'synthetic-key')
            self.assertEqual(raised.exception.code, safe_code)
            self.assertEqual(raised.exception.request_id, 'req_http')
            self.assertNotIn('synthetic-key', str(raised.exception))
            self.assertTrue(raised.exception.known_unbilled)


if __name__ == '__main__':
    unittest.main()
