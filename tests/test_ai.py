import copy
import os
import time
import unittest
from unittest.mock import patch
from core import ai

class AIProviderTests(unittest.TestCase):
    def setUp(self):
        ai._CACHE.clear()
        ai._FAILURES.clear()
        self.recs = [{'event_id': 'A', 'score': 20., 'reasons': ['role', 'gap', 'history', 'format'], 'skill_changes': [{'before': 1, 'after': 2}]},
                     {'event_id': 'B', 'score': 19., 'reasons': ['roleB', 'gapB', 'historyB', 'formatB'], 'skill_changes': []},
                     {'event_id': 'C', 'score': 5., 'reasons': ['roleC', 'gapC', 'historyC'], 'skill_changes': []}]
        self.e = {'role': 'Backend Engineer', 'grade': 'Middle', 'full_name': 'PRIVATE NAME', 'employee_id': 'PRIVATE ID'}
        self.events = {k: {'description': k} for k in 'ABC'}
        self.env = patch.dict(os.environ, {'CAREER_QUEST_AI_PROVIDER': 'openai', 'CAREER_QUEST_AI_MODEL': 'test-model', 'OPENAI_API_KEY': 'synthetic-test-token'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_valid_choice_keeps_facts_and_gains(self):
        original = copy.deepcopy(self.recs)
        with patch.object(ai, '_bounded_request', return_value={'event_id': 'B', 'reason_indices': [2, 0, 1]}) as request:
            result = ai.refine(self.recs, self.e, self.events)
            self.assertEqual(result[0]['event_id'], 'B')
            self.assertEqual(result[1]['skill_changes'], self.recs[0]['skill_changes'])
            facts = request.call_args.args[3]
            self.assertNotIn('PRIVATE', str(facts))
            ai.refine(self.recs, self.e, self.events)
            self.assertEqual(request.call_count, 1)
        self.assertEqual(self.recs, original)

    def test_invalid_choice_falls_back(self):
        for response in [{'event_id': 'C', 'reason_indices': [0, 1, 2]}, {'event_id': 'A', 'reason_indices': [0, 1, 99]}, {'event_id': 'A', 'reason_indices': [0, 0, 0]}, {'event_id': 'invented', 'reason_indices': [0, 1, 2]}]:
            ai._FAILURES.clear()
            with patch.object(ai, '_bounded_request', return_value=response):
                self.assertEqual(ai.refine(self.recs, self.e, self.events), self.recs)

    def test_no_key_and_error(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}), patch.object(ai, '_bounded_request') as request:
            self.assertEqual(ai.refine(self.recs, self.e, self.events), self.recs)
            request.assert_not_called()
        with patch.object(ai, '_bounded_request', side_effect=TimeoutError) as request:
            self.assertEqual(ai.refine(self.recs, self.e, self.events), self.recs)
            self.assertEqual(ai.refine(self.recs, self.e, self.events), self.recs)
            self.assertEqual(request.call_count, 1)

    def test_hard_wait_limit(self):
        with patch.object(ai, '_request', side_effect=lambda *args: time.sleep(.3)):
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                ai._bounded_request('openai', 'test', 'synthetic', {}, .05)
            self.assertLess(time.monotonic() - started, .2)

    def test_timeout_clamp(self):
        with patch.dict(os.environ, {'CAREER_QUEST_AI_TIMEOUT': '100'}):
            self.assertEqual(ai.settings()[3], 9.)
