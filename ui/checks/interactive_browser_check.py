"""Isolated real-browser acceptance of the interactive, persisted growth route.

Run: python -m ui.checks.interactive_browser_check
The fixture transport is mocked in this process; the app has an empty API key.
"""

import argparse
import json
import os
import re
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
from core.growth import GrowthService, GrowthStore, TRAITS
from .browser_login_helpers import login_demo, switch_demo_role
from .test_growth import provider_response

ROOT = Path(__file__).resolve().parents[2]
FIRST = 'Mitigate threats using Microsoft Defender XDR'
SECOND = 'Investigate incidents with Microsoft Sentinel (QA fixture)'


def settle(page, role='employee'):
    page.locator('.cq-footer').wait_for()
    expect(page.get_by_role('button', name='Stop', exact=True)).not_to_be_visible()
    expect(page.locator('[data-testid="stException"]')).to_have_count(0)
    expect(page.locator('[data-stale="true"]')).to_have_count(0)
    expect(page.locator('.st-key-employee_tab')).to_have_count(1 if role == 'employee' else 0)
    expect(page.locator('.st-key-hr_tab')).to_have_count(1 if role == 'hr' else 0)


def tab(page, name):
    page.get_by_role('tab', name=name, exact=True).click()
    settle(page)


def route_card(page, title):
    return page.locator('[class*="st-key-route-"]').filter(
        has=page.get_by_text(re.compile('^' + re.escape(title) + r' · '))).last


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir')
    parser.add_argument('--skip-timer', action='store_true', help='Skip the 60-second fragment/navigation soak')
    args = parser.parse_args()
    output = Path(args.output_dir or tempfile.mkdtemp(prefix='cq-interactive-browser-')).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='cq-interactive-qa-db-') as directory:
        store = GrowthStore(Path(directory) / 'growth.sqlite3')
        service = GrowthService(store)
        data = api.load_dataset(str(ROOT / 'case/case_1/career_quest_dataset'))
        service.save_profile(data, 'E0001', date.today()-timedelta(days=20), dict.fromkeys(TRAITS, 4), actor='hr')
        response = provider_response(service.facts(data, 'E0001'))
        payload = json.loads(response['output'][1]['content'][0]['text'])
        second_url = 'https://learn.microsoft.com/en-us/training/paths/sc-200-configure-microsoft-sentinel-environment/'
        payload['tracks'][0]['courses'].append({'title': SECOND, 'provider': 'Microsoft Learn',
            'url': second_url, 'level': 'Intermediate', 'price_text': 'Уточнить у провайдера', 'why': 'Альтернатива для практики SOC.'})
        response['output'][1]['content'][0]['text'] = json.dumps(payload)
        response['output'][0]['action']['sources'].append({'url': second_url})
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-token',
             'CAREER_QUEST_GROWTH_BUDGET_USD': '5', 'CAREER_QUEST_GROWTH_REQUEST_USD': '.1'}), \
             patch('core.growth_ai._bounded_http', return_value=response):
            seeded = service.recommend(data, 'E0001', True)
            assert seeded['status'] == 'generated', seeded
        used_before = service.budget()['used']
        env = dict(os.environ, CAREER_QUEST_DEMO_MODE='1', CAREER_QUEST_GROWTH_DB=str(store.path), OPENAI_API_KEY='', NVIDIA_API_KEY='',
                   CAREER_QUEST_AI_PROVIDER='none', CAREER_QUEST_GROWTH_BUDGET_USD='5', CAREER_QUEST_GROWTH_REQUEST_USD='.1')
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        with (output / 'server.log').open('w', encoding='utf-8') as log:
            server = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'app.py', '--server.headless', 'true',
                '--server.address', '127.0.0.1', '--server.port', str(port), '--browser.gatherUsageStats', 'false'],
                cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=flags)
            try:
                url = f'http://127.0.0.1:{port}'
                deadline = time.monotonic()+30
                while True:
                    try:
                        with urllib.request.urlopen(url+'/_stcore/health', timeout=1) as result:
                            if result.status == 200:
                                break
                    except OSError:
                        if time.monotonic() > deadline or server.poll() is not None:
                            raise RuntimeError('QA server did not start; see server.log') from None
                        time.sleep(.2)
                with sync_playwright() as runtime:
                    browser = runtime.chromium.launch(headless=True)
                    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
                    page.set_default_timeout(20000)
                    console_errors = []
                    page.on('pageerror', lambda error: console_errors.append(str(error)))
                    try:
                        page.goto(url, wait_until='networkidle')
                        login_demo(page)
                        settle(page)
                        expect(page.locator('.cq-xp-value')).to_contain_text('200')
                        tab(page, 'Карта развития')
                        nodes = page.locator('.cq-map-node.course')
                        expect(nodes).to_have_count(2)
                        nodes.first.click()
                        settle(page)
                        expect(page.get_by_role('button', name='Хочу этот курс', exact=True)).to_have_count(1)

                        # Real SVG interactions, including local viewport persistence.
                        zoom = page.locator('.cq-map-zoom')
                        before = zoom.inner_text()
                        page.get_by_role('button', name='Увеличить карту', exact=True).click()
                        expect(zoom).not_to_have_text(before)
                        settle(page)
                        world = page.locator('.cq-map-world')
                        transform = world.get_attribute('transform')
                        canvas = page.locator('.cq-map-canvas')
                        bounds = canvas.bounding_box()
                        page.mouse.move(bounds['x']+bounds['width']*.45, bounds['y']+bounds['height']-25)
                        page.mouse.down()
                        page.mouse.move(bounds['x']+bounds['width']*.45+45, bounds['y']+bounds['height']-40, steps=6)
                        page.mouse.up()
                        expect(world).not_to_have_attribute('transform', transform)
                        settle(page)
                        expect(world).not_to_have_attribute('transform', transform)
                        canvas.focus()
                        canvas.press('Home')
                        page.keyboard.press('Enter')
                        settle(page)
                        expect(page.locator('.cq-map-node[aria-pressed="true"]')).to_have_count(1)
                        page.get_by_role('button', name='Вся карта', exact=True).click()
                        nodes.first.click()
                        settle(page)
                        page.get_by_role('button', name='Свернуть ветвь', exact=True).click()
                        expect(nodes).to_have_count(0)
                        page.get_by_role('button', name='Раскрыть ветвь', exact=True).click()
                        expect(nodes).to_have_count(2)
                        nodes.first.click()
                        settle(page)
                        selected_id = page.locator('.cq-map-node[aria-pressed="true"]').get_attribute('data-node-id')
                        scale_before_choice = zoom.inner_text()
                        page.get_by_role('button', name='Хочу этот курс', exact=True).click()
                        expect(page.get_by_text('Курс добавлен в маршрут. Заявка отправлена HR.', exact=True)).to_be_visible()
                        settle(page)
                        expect(zoom).to_have_text(scale_before_choice)
                        expect(page.locator('.cq-map-node[aria-pressed="true"]')).to_have_attribute('data-node-id', selected_id)
                        assert len(service.snapshot(data, 'E0001')['requests']) == 1
                        expect(page.get_by_role('button', name='Открыть заявку', exact=True)).to_have_count(1)

                        nodes.nth(1).click()
                        settle(page)
                        page.get_by_role('button', name='Не подходит', exact=True).click()
                        expect(nodes).to_have_count(1)
                        page.get_by_text('Скрытые предложения · 1', exact=True).click()
                        page.get_by_role('button', name='Восстановить', exact=True).click()
                        expect(nodes).to_have_count(2)
                        nodes.nth(1).click()
                        settle(page)
                        page.get_by_role('button', name='Хочу этот курс', exact=True).click()
                        settle(page)
                        assert len(service.snapshot(data, 'E0001')['requests']) == 2
                        page.get_by_role('button', name='Сравнить курсы направления', exact=True).click()
                        settle(page)
                        expect(page.get_by_role('tab', name='Треки и курсы', exact=True)).to_have_attribute('aria-selected', 'true')
                        direction = page.get_by_role('combobox', name='Фильтр по направлению', exact=True)
                        expect(direction).to_have_value('SOC: следующий уровень')
                        direction.click()
                        page.get_by_role('option', name='Все направления', exact=True).click()
                        settle(page)
                        expect(direction).to_have_value('Все направления')
                        page.get_by_text('Предложить свой курс', exact=True).click()
                        page.get_by_label('Название своего курса', exact=True).fill('Custom course (QA fixture)')
                        page.get_by_label('HTTPS-ссылка на курс', exact=True).fill('https://example.org/courses/custom-qa')
                        page.get_by_label('Почему хотите этот курс', exact=True).fill('Практика для рабочего проекта')
                        page.get_by_role('button', name='Предложить курс HR', exact=True).click()
                        settle(page)
                        assert len(service.snapshot(data, 'E0001')['requests']) == 3
                        tab(page, 'Мой маршрут')
                        custom = route_card(page, 'Custom course (QA fixture)')
                        custom.get_by_role('button', name='Отменить заявку', exact=True).click()
                        settle(page)
                        expect(custom).to_contain_text('Отменено')
                        page.screenshot(path=str(output/'01-course-choices.png'), full_page=True)

                        switch_demo_role(page, 'hr')
                        page.get_by_role('tab', name='Заявки и решения', exact=True).click()
                        settle(page, 'hr')
                        approval = page.locator('[data-testid="stExpander"]').filter(has_text=FIRST)
                        approval.get_by_label('Комментарий сотруднику', exact=True).fill('Бюджет подтверждён QA')
                        approval.get_by_role('button', name='Отправить решение сотруднику', exact=True).click()
                        settle(page, 'hr')
                        switch_demo_role(page, 'employee')
                        tab(page, 'Мой маршрут')
                        chosen = route_card(page, FIRST)
                        chosen.get_by_role('button', name='Начать обучение', exact=True).click()
                        settle(page)
                        chosen.get_by_role('button', name='Завершить обучение', exact=True).click()
                        settle(page)
                        expect(chosen.get_by_label('Ссылка или номер сертификата', exact=True)).to_be_visible()
                        chosen.get_by_label('Ссылка или номер сертификата', exact=True).fill('QA-CERT-INTERACTIVE-001')
                        chosen.get_by_role('button', name='Отправить сертификат HR', exact=True).click()
                        settle(page)
                        expect(chosen).to_contain_text('Сертификат на проверке')
                        assert service.snapshot(data, 'E0001')['xp'] == 200
                        expect(page.get_by_role('button', name='Завершить обучение', exact=True)).to_have_count(0)
                        for name in ['Профиль и опыт', 'Треки и курсы', 'Мои сертификаты', 'Карта развития',
                                     'Навыки и требования', 'История участия', 'Мой маршрут']:
                            tab(page, name)
                        page.screenshot(path=str(output/'02-completion-no-overlap.png'), full_page=True)
                        switch_demo_role(page, 'hr')
                        page.get_by_role('tab', name='Заявки и решения', exact=True).click()
                        page.get_by_role('button', name='Подтвердить сертификат', exact=True).click()
                        settle(page, 'hr')
                        assert service.snapshot(data, 'E0001')['xp'] == 300
                        expect(page.get_by_role('button', name='Подтвердить сертификат', exact=True)).to_have_count(0)
                        for name in ['Оценка сотрудника', 'Обзор команды', 'Заявки и решения']:
                            page.get_by_role('tab', name=name, exact=True).click()
                            settle(page, 'hr')

                        switch_demo_role(page, 'employee')
                        tab(page, 'Профиль и опыт')
                        expect(page.locator('.cq-xp-value')).to_contain_text('300')
                        if not args.skip_timer:
                            # Cross a timer tick while the profile is mounted, then
                            # navigate away and cross another tick with it unmounted.
                            for _ in range(2):
                                page.wait_for_timeout(32000)
                            settle(page)
                            expect(page.locator('.cq-xp-value')).to_contain_text('300')
                            tab(page, 'Мой маршрут')
                            for _ in range(2):
                                page.wait_for_timeout(32000)
                            settle(page)
                        tab(page, 'Мой маршрут')
                        expect(route_card(page, FIRST)).to_contain_text('Обучение подтверждено')
                        assert service.snapshot(data, 'E0001')['xp'] == 300
                        tab(page, 'Карта развития')
                        expect(page.get_by_text(re.compile('План устарел'))).to_be_visible()
                        assert service.budget()['used'] == used_before, 'Navigation or changed portfolio charged AI'

                        # Import remains available through the new role gate.
                        switch_demo_role(page, 'admin')
                        settle(page, 'admin')
                        profile = dict(data['employees'][0], employee_id='JURY_INTERACTIVE_001', full_name='Проверочный профиль карты')
                        upload = output/'jury-profile.json'
                        upload.write_text(json.dumps({'employees': [profile]}, ensure_ascii=False), encoding='utf-8')
                        page.locator('input[type="file"]').first.set_input_files(str(upload))
                        page.get_by_role('button', name='Импортировать данные', exact=True).click()
                        expect(page.get_by_text(re.compile('Импорт завершён'))).to_be_visible()
                        settle(page, 'admin')
                        switch_demo_role(page, 'employee', 'JURY_INTERACTIVE_001')
                        settle(page)
                        expect(page.locator('.cq-subtitle').filter(has_text='Проверочный профиль карты').first).to_be_visible()
                        tab(page, 'Карта развития')
                        expect(page.locator('.cq-map-node.skill').first).to_be_visible()
                        assert service.budget()['used'] == used_before
                        page.screenshot(path=str(output/'03-imported-profile.png'), full_page=True)
                        assert not console_errors, console_errors
                    except Exception:
                        page.screenshot(path=str(output/'failure.png'), full_page=True)
                        (output/'failure.html').write_text(page.content(), encoding='utf-8')
                        raise
                    finally:
                        browser.close()
                print('PASS: real SVG click, keyboard, zoom, pan, collapse; multi-course selection, hide/restore, custom link and cancellation')
                print('PASS: HR budget approval -> start -> certificate form -> HR confirmation -> exactly +100 XP')
                print('PASS: all employee/HR tabs, role switching, imported profile, no stale trees/overlays or navigation expense')
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
