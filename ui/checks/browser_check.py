"""Read-only browser smoke on a running app. Full mutation acceptance is isolated
in interactive_browser_check.py to avoid changing production learning records.
"""
import argparse
import tempfile
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
from .browser_login_helpers import login_demo, switch_demo_role


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8502')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    output = Path(args.output_dir or tempfile.mkdtemp(prefix='career-quest-browser-'))
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1366,'height':900})
        page.set_default_timeout(30000)
        page.goto(args.url,wait_until='networkidle')
        login_demo(page)
        for tab in ['Профиль и опыт','Треки и курсы','Мой маршрут','Навыки и требования','История участия']:
            page.get_by_role('tab',name=tab,exact=True).click()
            expect(page.locator('[data-testid="stException"]')).to_have_count(0)
            expect(page.locator('[data-testid="stTabs"]')).to_have_count(1)
            expect(page.locator('[data-stale="true"]')).to_have_count(0)
        page.screenshot(path=str(output/'employee.png'))
        switch_demo_role(page,'hr')
        page.get_by_role('tab',name='Обзор команды',exact=True).click()
        expect(page.get_by_role('heading',name='Развитие команды',exact=True)).to_be_visible()
        switch_demo_role(page,'admin')
        expect(page.locator('[data-testid="stFileUploader"]')).to_have_count(2)
        page.screenshot(path=str(output/'admin.png'))
        expect(page.locator('[data-testid="stException"]')).to_have_count(0)
        browser.close()
    print('PASS: employee, shared route, HR and admin navigation; no stale trees')
    print('Artifacts:',output)


if __name__=='__main__':
    main()
