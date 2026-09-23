"""Presentation login for the integrated prototype; never constructs AuthService."""

from html import escape

import streamlit as st

from auth.demo_session import get_demo_identity, start_demo_session
from auth.ui import _hero, setup_page

ROLE_LABELS = {"employee": "Сотрудник", "hr": "HR", "admin": "Администратор"}
ROLE_COPY = {
    "employee": ("Ваш следующий шаг", "Выберите профиль, чтобы открыть личный маршрут развития."),
    "hr": ("Развитие начинается с команды", "Откройте обзор команды, профили и заявки на обучение."),
    "admin": ("Всё для точного старта", "Откройте пространство администратора и проверку данных."),
}


def render_demo_login(employees: list[dict]) -> dict | None:
    """Render the demo gate and rerun the host after a valid role selection.

    The host loads its dataset, calls get_demo_identity, then invokes this page
    and st.stop() when no identity is present. Account registration remains in
    auth_app.py; there is intentionally no fake registration in this demo gate.
    """
    identity = get_demo_identity(employees)
    if identity:
        return identity
    setup_page()
    choices = {person["employee_id"]: person for person in employees if person.get("employee_id")}
    st.session_state.setdefault("cq_demo_role", "employee")
    with st.container(key="cq_auth"):
        left, right = st.columns([1.13, 1], gap="large")
        with left:
            _hero()
        with right:
            with st.container(key="cq_auth_card"):
                st.html('<div class="auth-form-title"><span class="auth-eyebrow">CAREER QUEST</span>'
                        '<h2>Рады видеть вас</h2><p>Выберите пространство и продолжите путь развития.</p></div>')
                st.caption("Деморежим · без пароля и базы аккаунтов")
                selected = st.segmented_control(
                    "Войти как", options=list(ROLE_LABELS), format_func=ROLE_LABELS.get,
                    key="cq_demo_role", width="stretch",
                )
                role = selected or "employee"
                heading, hint = ROLE_COPY[role]
                st.html(f'<div class="auth-form-title"><h2 style="font-size:20px!important">{heading}</h2>'
                        f'<p>{hint}</p></div>')
                employee_id = None
                if role == "employee":
                    if choices:
                        pending = st.session_state.pop("pending_employee", None)
                        if pending in choices:
                            st.session_state["cq_demo_employee"] = pending
                        if st.session_state.get("cq_demo_employee") not in choices:
                            st.session_state["cq_demo_employee"] = next(iter(choices))
                        employee_id = st.selectbox(
                            "Профиль сотрудника", list(choices), key="cq_demo_employee",
                            format_func=lambda identifier: f'{choices[identifier].get("full_name") or choices[identifier].get("name") or identifier} · {identifier}',
                        )
                        person = choices[employee_id]
                        caption = " · ".join(str(value) for value in (person.get("role"), person.get("grade")) if value)
                        if caption:
                            st.html(f'<p class="auth-role-hint">{escape(caption)}</p>')
                        st.caption(f"Профили из подключённого датасета: {len(choices)}")
                    else:
                        st.info("В датасете ещё нет сотрудников. Войдите как администратор, чтобы загрузить профили.")
                elif role == "hr":
                    st.info("Проверяйте развитие сотрудников, рассматривайте сертификаты и заявки на обучение.")
                else:
                    st.info("Загружайте проверочные данные и проверяйте доступные возможности прототипа.")
                with st.form("cq_demo_login", border=False):
                    submitted = st.form_submit_button(
                        "Войти в деморежим →", key="cq_demo_enter", type="primary", width="stretch",
                        disabled=role == "employee" and not choices,
                    )
                if submitted:
                    try:
                        start_demo_session(role, employee_id, employees)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.rerun()
                st.caption("Роли доступны для проверки экранов. Это демонстрационный выбор, а не проверка прав доступа.")
                st.html('<div class="auth-form-footer"><span aria-hidden="true">◇</span> Пространство для роста внутри команды</div>')
    st.html('<footer class="auth-bottom"><span>Career Quest · Halyk</span><span>Каждый шаг имеет значение.</span></footer>')
    return None
