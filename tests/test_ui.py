"""End-to-end Streamlit session against actual starter-kit engine, no API calls."""
import copy
import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from ui.adapter import Engine
from ui.checks.demo_login_helpers import demo_login, employee_tab, hr_tab, isolate_demo_storage, switch_demo_role

ROOT = Path(__file__).resolve().parents[1]

class UIFlowTests(unittest.TestCase):
    @patch.dict(os.environ, {'CAREER_QUEST_AI_PROVIDER': 'none'})
    def test_starter_kit_flow(self):
        isolate_demo_storage(self)
        app = AppTest.from_file(str(ROOT / 'app.py')).run()
        self.assertFalse(app.exception)
        engine = Engine()
        demo_login(app, employee_id='E0002')
        employee_tab(app, 'Мой маршрут')
        before = engine.employee(app.session_state['dataset'], 'E0002')
        event = before['recommendations'][0]['event_id']
        app.button(key=f'complete-E0002-{event}').click().run()
        self.assertFalse(app.exception)
        after = engine.employee(app.session_state['dataset'], 'E0002')
        self.assertGreater(after['trajectory']['progress_percent'], before['trajectory']['progress_percent'])
        self.assertEqual(len(after['history']), len(before['history']) + 1)
        switch_demo_role(app, 'hr')
        hr_tab(app, 'Обзор команды')
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe), 3)
        profile = copy.deepcopy(app.session_state['dataset']['employees'][1])
        profile['employee_id'] = 'UI-CHECK'
        profile['full_name'] = 'Synthetic UI check'
        candidate = engine.import_files(app.session_state['dataset'], io.BytesIO(json.dumps({'employees': [profile]}).encode()), None)
        app.session_state['dataset'] = candidate
        switch_demo_role(app, 'employee', 'UI-CHECK')
        employee_tab(app, 'Мой маршрут')
        self.assertFalse(app.exception)
        self.assertEqual(len(engine.employee(candidate, 'UI-CHECK')['history']), 0)
        rec = engine.employee(candidate, 'UI-CHECK')['recommendations'][0]
        app.button(key='complete-UI-CHECK-' + rec['event_id']).click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(engine.employee(app.session_state['dataset'], 'UI-CHECK')['history']), 1)
        switch_demo_role(app, 'admin')
        app.radio(key='admin_page').set_value('Импорт данных').run()
        next(button for button in app.button if button.label == 'Импортировать данные').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
