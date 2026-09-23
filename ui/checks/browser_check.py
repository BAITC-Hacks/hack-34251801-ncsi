"""Browser acceptance checks. Requires playwright + its Chromium runtime.

Run an app first, then: python -m ui.checks.browser_check --url http://localhost:8501
Screenshots and synthetic uploads are saved outside the repository by default.
"""

import argparse
import json
import re
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    output = Path(args.output_dir or tempfile.mkdtemp(prefix="career-quest-browser-"))
    output.mkdir(parents=True, exist_ok=True)
    profile = json.loads((ROOT / "case/case_1/career_quest_dataset/employees.json").read_text(encoding="utf-8"))["employees"][0]
    profile["employee_id"] = "JURY_BROWSER_001"
    profile["full_name"] = "Проверочный сотрудник с очень длинным именем для проверки переноса текста"
    upload = output / "jury_employees.json"
    upload.write_text(json.dumps({"employees": [profile]}, ensure_ascii=False), encoding="utf-8")
    bad_upload = output / "invalid.json"
    bad_upload.write_text("{invalid}", encoding="utf-8")
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 768}, device_scale_factor=1)
        page.set_default_timeout(30000)
        page.goto(args.url, wait_until="networkidle")
        expect(page.get_by_role("heading", name="Ваш следующий шаг", exact=True)).to_be_visible()
        page.locator(".cq-footer").wait_for()
        page.evaluate("document.fonts.ready")
        expect(page.get_by_role("button", name="Stop", exact=True)).not_to_be_visible()
        expect(page.locator('[data-testid="stException"]')).to_have_count(0)
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), "Horizontal page overflow"
        button = page.get_by_role("button", name="Завершить активность", exact=True)
        expect(button).to_be_in_viewport(ratio=1)
        page.screenshot(path=str(output / "01-employee-1366.png"))
        results.append("Employee profile, grade, target, recommendation and completion button visible at 1366x768")
        assert page.locator(".cq-factor").count() >= 3, "Missing three evidence factors"
        assert page.locator(".cq-gain").count() > 0, "Missing expected skill gains"
        results.append("Recommendation evidence and skill gains rendered separately")
        # A layout stress test only: change DOM text, then restore the real response.
        title = page.locator(".cq-event-title").first
        original_title = title.inner_text()
        title.evaluate("(el) => el.textContent = 'Практикум по проектированию распределённых банковских систем и развитию навыков межфункциональной коммуникации'")
        assert title.evaluate("el => el.scrollWidth <= el.clientWidth + 1"), "Long title is clipped"
        button.scroll_into_view_if_needed()
        expect(button).to_be_in_viewport()
        page.screenshot(path=str(output / "02-long-title.png"))
        title.evaluate("(el, text) => el.textContent = text", original_title)
        before = page.locator(".cq-progress strong").inner_text()
        button.click()
        expect(page.get_by_text(re.compile("Активность.*завершена"))).to_be_visible()
        after = page.locator(".cq-progress strong").inner_text()
        assert float(after.rstrip("%")) > float(before.rstrip("%"))
        results.append(f"Completion updates progress: {before} -> {after}; recommendations refreshed")
        page.get_by_text("HR", exact=True).click()
        expect(page.get_by_role("heading", name="Развитие команды", exact=True)).to_be_visible()
        expect(page.get_by_role("heading", name="Участие по активностям", exact=True)).to_be_visible()
        page.screenshot(path=str(output / "03-hr-1366.png"))
        results.append("HR gaps, employees needing support and event participation visible")
        page.get_by_text("Импорт данных", exact=True).click()
        expect(page.get_by_role("heading", name="Добавьте данные для проверки", exact=True)).to_be_visible()
        inputs = page.locator('input[type="file"]')
        expect(inputs).to_have_count(2)
        inputs.nth(0).set_input_files(str(upload))
        page.get_by_role("button", name="Импортировать данные", exact=True).click()
        expect(page.get_by_text(re.compile("Импорт завершён. Новых сотрудников: 1"))).to_be_visible()
        page.screenshot(path=str(output / "04-import-success.png"))
        page.get_by_text("Сотрудник", exact=True).click()
        expect(page.locator(".cq-subtitle").filter(has_text=profile["full_name"]).first).to_be_visible()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), "Long employee name overflows"
        page.screenshot(path=str(output / "05-imported-profile.png"))
        results.append("New profile imported through the same adapter, selected and rendered; long name wraps")
        page.get_by_text("Импорт данных", exact=True).click()
        page.locator('input[type="file"]').nth(0).set_input_files(str(bad_upload))
        page.get_by_role("button", name="Импортировать данные", exact=True).click()
        expect(page.get_by_text(re.compile("Не удалось прочитать файл"))).to_be_visible()
        page.get_by_text("Сотрудник", exact=True).click()
        expect(page.locator(".cq-subtitle").filter(has_text=profile["full_name"]).first).to_be_visible()
        results.append("Malformed upload rejected without losing the imported profile")
        # Select another arbitrary existing employee through the actual combobox.
        combo = page.get_by_role("combobox", name="Профиль сотрудника")
        combo.fill("E0002")
        page.get_by_role("option", name=re.compile("E0002")).click()
        expect(page.locator(".cq-subtitle").filter(has_text="Arman Zhaksylykov").first).to_be_visible()
        results.append("Arbitrary employee selection works through the UI")
        browser.close()
    (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS: " + "\nPASS: ".join(results))
    print("Artifacts:", output)


if __name__ == "__main__":
    main()
