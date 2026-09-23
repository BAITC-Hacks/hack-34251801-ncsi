import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from core import api
from core.growth import GrowthService, GrowthStore
from ui.checks.test_growth import provider_response
from ui.checks.demo_login_helpers import demo_login, isolate_demo_storage, switch_demo_role

ROOT = Path(__file__).resolve().parents[2]


class GrowthUIFlowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / 'growth.sqlite3'
        isolate_demo_storage(self, growth_path=self.db)
        env = patch.dict(os.environ, {'CAREER_QUEST_GROWTH_DB': str(self.db), 'OPENAI_API_KEY': '', 'CAREER_QUEST_AI_PROVIDER': 'none'})
        env.start()
        self.addCleanup(env.stop)
        self.service = GrowthService(GrowthStore(self.db))
        self.data = api.load_dataset(str(ROOT / 'case/case_1/career_quest_dataset'))

    def app(self):
        app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        return demo_login(app)

    def tab(self, app, value, hr=False):
        switch_demo_role(app, 'hr' if hr else 'employee')
        app.session_state['hr_tab' if hr else 'employee_tab'] = value
        app.run()
        self.assertFalse(app.exception)
        return app

    def button(self, app, label):
        return next(b for b in app.button if b.label == label)

    def test_hr_date_traits_then_employee_certificate_and_approval(self):
        app = self.app()
        self.tab(app, 'Оценка сотрудника', hr=True)
        started = date.today() - timedelta(days=20)
        app.date_input[0].set_value(started)
        app.slider(key='trait-E0001-resilience').set_value(5)
        app.session_state['hr_tab'] = 'Оценка сотрудника'
        self.button(app, 'Сохранить профиль HR').click().run()
        self.assertFalse(app.error)
        self.assertEqual(self.service.snapshot(self.data, 'E0001')['xp'], 200)
        self.assertEqual(self.service.profile(self.data, 'E0001')['traits']['resilience'], 5)
        self.tab(app, 'Мои сертификаты')
        values = {'Название пройденного курса': 'SOC foundation', 'Учебный провайдер': 'Microsoft',
                  'Ссылка на курс': 'https://learn.microsoft.com/training/soc-foundation',
                  'Ссылка или номер сертификата': 'CERT-123', 'Другие навыки и темы': 'SOC, SIEM'}
        for widget in app.text_input:
            if widget.label in values:
                widget.set_value(values[widget.label])
        app.multiselect[0].set_value(['SK_API_DESIGN'])
        app.session_state['employee_tab'] = 'Мои сертификаты'
        self.button(app, 'Отправить сертификат HR').click().run()
        self.assertFalse(app.error)
        self.assertEqual(self.service.snapshot(self.data, 'E0001')['xp'], 200)
        self.tab(app, 'Заявки и решения', hr=True)
        app.session_state['hr_tab'] = 'Заявки и решения'
        self.button(app, 'Подтвердить сертификат').click().run()
        self.assertFalse(app.error)
        self.assertEqual(self.service.snapshot(self.data, 'E0001')['xp'], 300)
        self.assertEqual(self.service.store.rows('certificates')[0]['status'], 'approved')
        fresh = self.app()
        self.assertFalse(fresh.error)
        self.assertEqual(GrowthService(GrowthStore(self.db)).snapshot(self.data, 'E0001')['xp'], 300)

    def test_research_want_course_then_hr_no_budget_and_employee_sees_reason(self):
        app = self.app()
        self.tab(app, 'Треки и курсы')
        facts = self.service.facts(self.data, 'E0001')
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token'}), \
             patch('core.growth_ai._bounded_http', return_value=provider_response(facts)) as transport:
            app.session_state['employee_tab'] = 'Треки и курсы'
            app.button(key='research-E0001').click().run()
        self.assertFalse(app.error)
        self.assertFalse(app.exception)
        self.assertEqual(transport.call_count, 1)
        app.session_state['employee_tab'] = 'Треки и курсы'
        self.button(app, 'Хочу на этот курс').click().run()
        self.assertFalse(app.error)
        request = self.service.store.rows('training_requests')[0]
        self.tab(app, 'Заявки и решения', hr=True)
        app.selectbox(key=f"decision-{request['id']}").select('Нет бюджета')
        app.text_input(key=f"budget-reason-{request['id']}").set_value('Вернёмся в следующем квартале')
        app.session_state['hr_tab'] = 'Заявки и решения'
        self.button(app, 'Отправить решение сотруднику').click().run()
        self.assertFalse(app.error)
        self.tab(app, 'Треки и курсы')
        self.assertTrue(any('Нет бюджета' in m.value for m in app.markdown))
        self.assertEqual(self.service.store.rows('training_requests')[0]['status'], 'rejected')

    def test_explicit_ai_timeout_has_core_fallback_and_no_retry(self):
        app = self.app()
        self.tab(app, 'Треки и курсы')
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token'}), \
             patch('core.growth_ai._bounded_http', side_effect=TimeoutError) as transport:
            app.session_state['employee_tab'] = 'Треки и курсы'
            app.button(key='research-E0001').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('AI не ответил' in m.value for m in app.info))
        self.assertEqual(transport.call_count, 1)
        self.tab(app, 'Мой маршрут')
        self.assertTrue(app.session_state['views'][(0, 'E0001')]['recommendations'][0]['reasons'])
        self.assertEqual(self.service.budget()['used'], .1)


if __name__ == '__main__':
    unittest.main()
