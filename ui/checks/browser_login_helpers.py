"""Shared navigation through the integrated, explicitly labelled demo gate.

These helpers select screens through the rendered controls; they do not inject
an identity, bypass the gate, create accounts, or change the session dataset.
"""

import re

from playwright.sync_api import expect


ROLE_LABELS = {"employee": "Сотрудник", "hr": "HR", "admin": "Администратор"}
ROLE_HEADINGS = {
    "employee": "Ваш следующий шаг",
    "hr": "Развитие начинается с команды",
    "admin": "Всё для точного старта",
}


def login_demo(page, role="employee", employee_id="E0001"):
    """Enter an anonymous browser session using the visible demo form."""
    label = ROLE_LABELS[role]
    enter = page.get_by_role("button", name="Войти в деморежим →", exact=True)
    expect(enter).to_be_visible()
    page.locator(".st-key-cq_demo_role").get_by_role("button", name=label, exact=True).click()
    expect(page.locator(".st-key-cq_auth_card").get_by_role(
        "heading", name=ROLE_HEADINGS[role], exact=True)).to_be_visible()
    if role == "employee":
        combo = page.locator(".st-key-cq_demo_employee").get_by_role("combobox")
        expect(combo).to_be_visible()
        combo.fill(employee_id)
        page.get_by_role("option", name=re.compile(re.escape(employee_id) + r"$")).click()
    enter.click()
    expect(page.get_by_role("button", name="Выйти / сменить роль", exact=True)).to_be_visible()
    page.locator(".cq-footer").wait_for()


def switch_demo_role(page, role, employee_id="E0001"):
    """Log out and select another demo screen while retaining learning data."""
    page.get_by_role("button", name="Выйти / сменить роль", exact=True).click()
    login_demo(page, role, employee_id)
