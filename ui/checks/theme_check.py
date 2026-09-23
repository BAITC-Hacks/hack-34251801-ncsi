"""Verify rendered text contrast with OS and persisted Streamlit themes."""

import argparse
import json
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

# Check actual foreground/background pairs, not the presence of CSS rules.
CONTRAST = """el => {
    const rgba = color => color.match(/[\\d.]+/g).map(Number);
    const blend = (front, back) => {
        const alpha = front[3] ?? 1;
        return front.slice(0, 3).map((value, i) => value * alpha + back[i] * (1 - alpha));
    };
    const ancestors = [];
    for (let node = el; node; node = node.parentElement) ancestors.push(node);
    let background = [255, 255, 255];
    for (const node of ancestors.reverse()) {
        background = blend(rgba(getComputedStyle(node).backgroundColor), background);
    }
    const color = getComputedStyle(el).color;
    const foreground = blend(rgba(color), background);
    const luminance = rgb => rgb.map(v => {
        v /= 255;
        return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    }).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
    const a = luminance(foreground), b = luminance(background);
    return {text: el.textContent.trim().slice(0, 70), color, background,
            ratio: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)};
}"""

TEXT = ", ".join([
    ".cq-brand strong", ".cq-brand small", ".cq-person strong", ".cq-person p", ".cq-pill",
    '[data-testid="stWidgetLabel"] p',
    '[data-testid="stRadioOption"] [data-testid="stMarkdownContainer"] p',
    '[data-testid="stCaptionContainer"] p', '[data-testid="stTab"]',
    ".cq-sidebar-note", ".cq-subtitle", ".cq-journey small", ".cq-journey strong",
    ".cq-event-title", ".cq-explanation b", ".cq-explanation p", ".cq-factor span", ".cq-gain", ".cq-bridge",
    ".cq-small-label", ".cq-meta", ".cq-skill-head b", ".cq-skill-head span",
    ".cq-critical", ".cq-help", ".cq-footer", ".cq-stat span", ".cq-stat strong",
    ".cq-stat small", '[data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] p',
    '[data-testid="stButton"] button', '[data-testid="stFormSubmitButton"] button',
    '[data-testid="stDownloadButton"] button',
])


def readable_text(page):
    readings = []
    for element in page.locator(TEXT).all():
        if element.is_visible():
            reading = element.evaluate(CONTRAST)
            if reading["text"]:
                readings.append(reading)
    assert len(readings) >= 10, "The page did not render enough text to check"
    failures = [row for row in readings if row["ratio"] < 4.5]
    assert not failures, f"Low contrast: {failures}"
    return min(row["ratio"] for row in readings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8502")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    output = Path(args.output_dir or tempfile.mkdtemp(prefix="career-quest-theme-"))
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        # A saved preference can differ from the operating system's theme.
        for scheme, saved in [("light", None), ("dark", None), ("light", "Dark"), ("dark", "Light")]:
            context = browser.new_context(viewport={"width": 1366, "height": 768}, color_scheme=scheme)
            if saved:
                context.add_init_script(
                    "localStorage.setItem('stActiveTheme-' + location.pathname + '-v2', "
                    + json.dumps(json.dumps(saved)) + ");"
                )
            page = context.new_page()
            page.set_default_timeout(30000)
            page.goto(args.url, wait_until="networkidle")
            page.locator(".cq-footer").wait_for()
            page.evaluate("document.fonts.ready")
            label = f"{scheme}-{saved or 'system'}"
            minimum = readable_text(page)
            expect(page.get_by_role("button", name="Завершить активность", exact=True)).to_be_in_viewport(ratio=1)
            page.screenshot(path=str(output / f"{label}-employee.png"))
            for mode, heading in [("HR", "Развитие команды"), ("Импорт данных", "Добавьте данные для проверки")]:
                page.get_by_text(mode, exact=True).click()
                expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
                minimum = min(minimum, readable_text(page))
            expect(page.locator('[data-testid="stException"]')).to_have_count(0)
            results.append(f"PASS: {label}, employee/HR/import text contrast >= {minimum:.2f}:1")
            context.close()
        browser.close()
    print("\n".join(results))
    print("Artifacts:", output)


if __name__ == "__main__":
    main()
