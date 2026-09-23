"""Two-direction visual/filter regression check using an isolated mocked plan.

Run: python -m ui.checks.track_filter_browser_check
No live API calls, production profiles, or production SQLite writes.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright

from core import api
from core.growth import GrowthService, GrowthStore
from .browser_login_helpers import login_demo
from .interactive_browser_check import settle, tab
from .test_growth import provider_response

ROOT = Path(__file__).resolve().parents[2]
FIRST = 'SOC: следующий уровень'
SECOND = 'Инженерия облачной платформы'


def seed_plan(service, dataset):
    response = provider_response(service.facts(dataset, 'E0001'))
    plan = json.loads(response['output'][1]['content'][0]['text'])
    second_course = deepcopy(plan['tracks'][0]['courses'][0])
    second_course.update(title='Практика расследования инцидентов · QA',
        url='https://learn.microsoft.com/en-us/training/paths/sc-200-configure-microsoft-sentinel-environment/')
    plan['tracks'][0]['courses'].append(second_course)
    other = deepcopy(plan['tracks'][0])
    other.update(title=SECOND, kind='exploration', explanation='Примените подтверждённую инженерную базу в облачной инфраструктуре.',
                 next_skills=['Облачная архитектура', 'Наблюдаемость сервисов'])
    for course, title, suffix in zip(other['courses'], ['Основы облачной архитектуры · QA', 'Практика облачного разработчика · QA'],
                                     ['azure-fundamentals-describe-cloud-concepts', 'create-azure-app-service-web-apps']):
        course.update(title=title, url='https://learn.microsoft.com/en-us/training/paths/'+suffix+'/',
                      why='Вариант развития инженерных навыков.')
    plan['tracks'].append(other)
    response['output'][1]['content'][0]['text'] = json.dumps(plan)
    response['output'][0]['action']['sources'] = [{'url': course['url']} for track in plan['tracks'] for course in track['courses']]
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token',
            'CAREER_QUEST_GROWTH_BUDGET_USD': '5', 'CAREER_QUEST_GROWTH_REQUEST_USD': '.1'}), \
            patch('core.growth_ai._bounded_http', return_value=response):
        result = service.recommend(dataset, 'E0001', True)
    assert result['status'] == 'generated', result


def filter_to(page, title):
    field = page.get_by_role('combobox', name='Фильтр по направлению', exact=True)
    field.click()
    page.get_by_role('option', name=title, exact=True).click()
    settle(page)
    expect(field).to_have_value(title)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    output = Path(args.output_dir or tempfile.mkdtemp(prefix='cq-track-filter-browser-')).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with tempfile.TemporaryDirectory(prefix='cq-track-filter-db-') as directory:
        store = GrowthStore(Path(directory)/'growth.sqlite3')
        service = GrowthService(store)
        dataset = api.load_dataset(str(ROOT/'case/case_1/career_quest_dataset'))
        seed_plan(service, dataset)
        budget = service.budget()['used']
        with store.connection() as db:
            calls = db.execute('SELECT COUNT(*) FROM ai_calls').fetchone()[0]
        env = dict(os.environ, CAREER_QUEST_DEMO_MODE='1', CAREER_QUEST_GROWTH_DB=str(store.path),
                   CAREER_QUEST_DATA_HOME=directory, OPENAI_API_KEY='', NVIDIA_API_KEY='', CAREER_QUEST_AI_PROVIDER='none')
        with (output/'server.log').open('w', encoding='utf-8') as log:
            server = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'app.py', '--server.headless', 'true',
                '--server.address', '127.0.0.1', '--server.port', str(port), '--browser.gatherUsageStats', 'false'],
                cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=flags)
            try:
                url = f'http://127.0.0.1:{port}'
                deadline = time.monotonic()+30
                while True:
                    try:
                        with urllib.request.urlopen(url+'/_stcore/health', timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        if time.monotonic() > deadline or server.poll() is not None:
                            raise RuntimeError('QA server did not start; see server.log') from None
                        time.sleep(.2)
                with sync_playwright() as runtime:
                    browser = runtime.chromium.launch(headless=True)
                    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
                    page.set_default_timeout(20000)
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    try:
                        page.goto(url, wait_until='networkidle')
                        login_demo(page)
                        tab(page, 'Треки и курсы')
                        headings = page.locator('.cq-direction-heading')
                        field = page.get_by_role('combobox', name='Фильтр по направлению', exact=True)
                        expect(field).to_have_value('Все направления')
                        expect(headings).to_have_count(2)
                        expect(headings.nth(0)).to_contain_text(FIRST)
                        expect(headings.nth(1)).to_contain_text(SECOND)
                        expect(page.get_by_role('button', name='Хочу этот курс', exact=True)).to_have_count(4)
                        expect(page.get_by_role('button', name='Другие варианты', exact=True)).to_have_count(0)
                        buttons = page.get_by_role('button', name='Хочу этот курс', exact=True)
                        first, second = buttons.nth(0).bounding_box(), buttons.nth(1).bounding_box()
                        assert abs(first['x']-second['x']) > 100, 'Desktop alternatives should occupy different columns'
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), 'Desktop overflow'
                        page.screenshot(path=str(output/'01-directions-desktop.png'), full_page=True)

                        filter_to(page, SECOND)
                        expect(headings).to_have_count(1)
                        expect(headings.first).to_contain_text(SECOND)
                        expect(buttons).to_have_count(2)
                        tab(page, 'Профиль и опыт')
                        tab(page, 'Треки и курсы')
                        expect(field).to_have_value(SECOND)
                        expect(headings).to_have_count(1)
                        filter_to(page, 'Все направления')
                        expect(headings).to_have_count(2)
                        tab(page, 'Мой маршрут')
                        tab(page, 'Треки и курсы')
                        expect(field).to_have_value('Все направления')
                        expect(headings).to_have_count(2)

                        tab(page, 'Карта развития')
                        page.get_by_role('button', name='Вся карта', exact=True).click()
                        page.locator('.cq-map-node.track').filter(has_text=SECOND).click()
                        settle(page)
                        page.get_by_role('button', name='Сравнить курсы направления', exact=True).first.click()
                        settle(page)
                        expect(page.get_by_role('tab', name='Треки и курсы', exact=True)).to_have_attribute('aria-selected', 'true')
                        expect(field).to_have_value(SECOND)
                        expect(headings).to_have_count(1)
                        expect(headings.first).to_contain_text(SECOND)
                        filter_to(page, 'Все направления')

                        page.set_viewport_size({'width': 390, 'height': 844})
                        page.wait_for_timeout(500)
                        collapse = page.locator('[data-testid="stSidebarCollapseButton"] button')
                        collapse_box = collapse.bounding_box() if collapse.count() else None
                        if collapse_box and 0 <= collapse_box['x'] < 390 and 0 <= collapse_box['y'] < 844:
                            collapse.click()
                        field.scroll_into_view_if_needed()
                        settle(page)
                        expect(headings).to_have_count(2)
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), 'Mobile overflow'
                        first, second = buttons.nth(0).bounding_box(), buttons.nth(1).bounding_box()
                        assert abs(first['x']-second['x']) < 20, 'Mobile alternatives should stack'
                        assert second['y'] > first['y'], 'Mobile alternatives overlap'
                        page.screenshot(path=str(output/'02-directions-mobile.png'), full_page=True)
                        filter_to(page, FIRST)
                        expect(headings).to_have_count(1)
                        expect(headings.first).to_contain_text(FIRST)
                        filter_to(page, 'Все направления')
                        assert service.budget()['used'] == budget
                        with store.connection() as db:
                            assert db.execute('SELECT COUNT(*) FROM ai_calls').fetchone()[0] == calls
                        assert not errors, errors
                    except Exception:
                        page.screenshot(path=str(output/'failure.png'), full_page=True)
                        (output/'failure.html').write_text(page.content(), encoding='utf-8')
                        raise
                    finally:
                        browser.close()
                print('PASS: two distinct directions; filter/reset persists across navigation; map transfers selected direction')
                print('PASS: desktop two-column cards, mobile stacked cards, no horizontal overflow or extra AI requests')
                print('Artifacts:', output)
            finally:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(server.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
                else:
                    server.terminate()
                server.wait(timeout=10)


if __name__ == '__main__':
    main()
