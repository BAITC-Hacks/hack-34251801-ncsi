"""Real browser HR workflow on an isolated server/database, with a mocked AI plan.

Run: python -m ui.checks.growth_browser_check
No paid API calls; never writes into the running application's database.
"""

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright

from core import api
from core.growth import GrowthService, GrowthStore
from .browser_login_helpers import login_demo, switch_demo_role
from .test_growth import provider_response

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    output = Path(args.output_dir or tempfile.mkdtemp(prefix='career-quest-growth-browser-')).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    # Each run gets a fresh store even when screenshots reuse an output directory.
    store = GrowthStore(Path(tempfile.mkdtemp(prefix='cq-growth-qa-db-')) / 'growth.sqlite3')
    service = GrowthService(store)
    data = api.load_dataset(str(ROOT / 'case/case_1/career_quest_dataset'))
    env = dict(os.environ, CAREER_QUEST_GROWTH_DB=str(store.path), OPENAI_API_KEY='',
               CAREER_QUEST_AI_PROVIDER='none', CAREER_QUEST_GROWTH_BUDGET_USD='5', CAREER_QUEST_GROWTH_REQUEST_USD='.1')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with (output / 'server.log').open('w', encoding='utf-8') as log:
        server = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'app.py', '--server.headless', 'true',
            '--server.address', '127.0.0.1', '--server.port', str(port), '--browser.gatherUsageStats', 'false'],
            cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=flags)
        url = f'http://127.0.0.1:{port}'
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(url + '/_stcore/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    if time.monotonic() >= deadline or server.poll() is not None:
                        raise RuntimeError('QA server did not start; see server.log') from None
                    time.sleep(.2)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                page.set_default_timeout(15000)
                page.goto(url, wait_until='networkidle')
                login_demo(page, 'hr')
                page.get_by_role('tab', name='Оценка сотрудника', exact=True).click()
                start = date.today() - timedelta(days=20)
                for segment, value in [('year', start.year), ('month', start.month), ('day', start.day)]:
                    field = page.get_by_role('spinbutton', name=f'{segment}, Дата начала работы', exact=True)
                    field.focus()
                    field.press_sequentially(str(value))
                    field.press('Tab')
                slider = page.locator('input[type="range"][aria-label="Стрессоустойчивость"]')
                slider.focus()
                slider.press('End')
                page.get_by_role('button', name='Сохранить профиль HR', exact=True).click()
                expect(page.get_by_text('Характеристики и дата выхода сохранены.', exact=True)).to_be_visible()
                assert service.snapshot(data, 'E0001')['xp'] == 200
                assert service.profile(data, 'E0001')['traits']['resilience'] == 5
                switch_demo_role(page, 'employee', 'E0001')
                expect(page.locator('.cq-xp-value')).to_contain_text('200')
                radar = page.locator('[data-testid="stImage"] img').first
                expect(radar).to_be_visible()
                assert radar.evaluate('el => el.naturalWidth > 0')
                page.screenshot(path=str(output / 'profile-radar.png'), full_page=True)
                page.get_by_role('tab', name='Мои сертификаты', exact=True).click()
                for label, value in {
                    'Название пройденного курса': 'SOC foundation (QA fixture)',
                    'Учебный провайдер': 'Microsoft Learn',
                    'Ссылка на курс': 'https://learn.microsoft.com/training/qa-foundation',
                    'Ссылка или номер сертификата': 'QA-CERT-001',
                    'Другие навыки и темы': 'SOC, SIEM',
                }.items():
                    page.get_by_label(label, exact=True).fill(value)
                page.get_by_role('button', name='Отправить сертификат HR', exact=True).click()
                expect(page.get_by_text('Сертификат отправлен HR. До одобрения опыт и навыки не начисляются.', exact=True)).to_be_visible()
                assert service.snapshot(data, 'E0001')['xp'] == 200
                switch_demo_role(page, 'hr')
                page.get_by_role('tab', name='Заявки и решения', exact=True).click()
                page.get_by_role('button', name='Подтвердить сертификат', exact=True).click()
                expect(page.get_by_text('Решение по сертификату сохранено.', exact=True)).to_be_visible()
                assert service.snapshot(data, 'E0001')['xp'] == 300

                # The transport fixture is local to this test process. UI reads the
                # resulting cached plan from the QA store; no fixture enters production.
                with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token',
                     'CAREER_QUEST_GROWTH_BUDGET_USD': '5', 'CAREER_QUEST_GROWTH_REQUEST_USD': '.1'}), \
                     patch('core.growth_ai._bounded_http', return_value=provider_response(service.facts(data, 'E0001'))):
                    assert service.recommend(data, 'E0001', True)['status'] == 'generated'
                switch_demo_role(page, 'employee', 'E0001')
                page.get_by_role('tab', name='Треки и курсы', exact=True).click()
                expect(page.get_by_role('heading', name='SOC: следующий уровень', exact=True)).to_be_visible()
                page.screenshot(path=str(output / 'tracks-mocked-search.png'), full_page=True)
                page.get_by_role('button', name='Хочу на этот курс', exact=True).click()
                expect(page.get_by_text('Запрос на обучение отправлен HR. Оплата не выполнялась.', exact=True)).to_be_visible()
                switch_demo_role(page, 'hr')
                page.get_by_role('tab', name='Заявки и решения', exact=True).click()
                page.get_by_label('Решение по бюджету', exact=True).click()
                page.get_by_role('option', name='Нет бюджета', exact=True).click()
                page.get_by_label('Комментарий сотруднику', exact=True).fill('Вернёмся в следующем квартале')
                page.get_by_role('button', name='Отправить решение сотруднику', exact=True).click()
                expect(page.get_by_text('Решение по обучению отправлено сотруднику.', exact=True)).to_be_visible()
                switch_demo_role(page, 'employee', 'E0001')
                page.get_by_role('tab', name='Треки и курсы', exact=True).click()
                expect(page.get_by_text('Нет бюджета: Вернёмся в следующем квартале', exact=True)).to_be_visible()
                page.screenshot(path=str(output / 'employee-decision.png'), full_page=True)
                assert service.store.rows('training_requests')[0]['status'] == 'rejected'
                assert service.snapshot(data, 'E0001')['xp'] == 300
                page.reload(wait_until='networkidle')
                login_demo(page, 'employee', 'E0001')
                expect(page.locator('.cq-xp-value')).to_contain_text('300')
                expect(page.locator('[data-testid="stException"]')).to_have_count(0)
                browser.close()
            print('PASS: HR date/traits -> visible radar/200 XP -> certificate pending -> HR approval/300 XP')
            print('PASS: cached mocked AI plan -> course request -> HR budget rejection -> employee reason -> reload persistence')
            print('No live API calls. Artifacts:', output)
        finally:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(server.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
            else:
                server.terminate()
            server.wait(timeout=10)


if __name__ == '__main__':
    main()
