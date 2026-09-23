"""Isolated Streamlit account UI. Does not read or modify employee datasets."""

from html import escape
from pathlib import Path
import sqlite3

import streamlit as st

from auth.service import AuthError, AuthService

ROLES = {"employee": "Сотрудник", "hr": "HR", "admin": "Администратор"}
ROLE_HINTS = {
    "employee": "Личное пространство для следующего карьерного шага.",
    "hr": "Единая точка входа для команды развития персонала.",
    "admin": "Вход для администратора пространства Career Quest.",
}
TOKEN_KEY = "cq_auth_token"


def setup_page():
    st.html(f"<style>{Path(__file__).with_name('styles.css').read_text(encoding='utf-8')}</style>")
    st.html('''<header class="auth-header">
      <div class="auth-brand"><span class="auth-logo" aria-hidden="true">cq<span>↗</span></span>
        <div><strong>Career Quest</strong><small>ПРОСТРАНСТВО РАЗВИТИЯ</small></div></div>
      <div class="auth-bank"><span class="auth-bank-dot" aria-hidden="true"></span>Halyk<span> / </span>Career &amp; Growth</div>
    </header>''')


def _hero():
    st.html('''<section class="auth-hero">
      <div class="auth-eyebrow"><span></span> ТВОЙ ПОТЕНЦИАЛ. ТВОЙ МАРШРУТ.</div>
      <h1>Большие цели.<br>Твой следующий<br><em>шаг.</em></h1>
      <p class="auth-intro">Развивай сильные стороны, открывай новые<br class="auth-wide-br"> возможности и двигайся к следующему грейду.</p>
      <div class="auth-route" aria-label="Путь развития: профиль, навыки, следующий грейд">
        <div class="auth-route-line" aria-hidden="true"></div>
        <div class="auth-route-step"><span class="auth-route-dot">01</span><div><small>ТОЧКА ОТСЧЁТА</small><strong>Твой профиль</strong></div></div>
        <div class="auth-route-step"><span class="auth-route-dot">02</span><div><small>ШАГ ВПЕРЁД</small><strong>Новые навыки</strong></div><span class="auth-route-arrow" aria-hidden="true">↗</span></div>
        <div class="auth-route-step"><span class="auth-route-dot">03</span><div><small>ТВОЯ ЦЕЛЬ</small><strong>Следующий грейд</strong></div></div>
      </div>
      <div class="auth-hero-footer"><span>Расти в своём темпе.</span><span aria-hidden="true">✳</span></div>
    </section>''')


def _error(message):
    st.error(message, icon="⚠️")


def _login(service):
    st.session_state.setdefault("cq_auth_role", "employee")
    role = st.segmented_control(
        "Войти как", options=list(ROLES), format_func=ROLES.get,
        key="cq_auth_role", width="stretch",
    )
    selected_role = role or "employee"
    st.html(f'<p class="auth-role-hint">{ROLE_HINTS[selected_role]}</p>')
    with st.form("cq_auth_login", clear_on_submit=True, border=False):
        email = st.text_input("Рабочая почта", placeholder="name@company.kz", max_chars=254)
        password = st.text_input("Пароль", type="password", placeholder="Введите пароль", max_chars=128)
        submitted = st.form_submit_button("Войти в Career Quest →", type="primary", width="stretch")
    if submitted:
        try:
            token, _ = service.login(email, password, selected_role)
        except AuthError as exc:
            _error(str(exc))
        except (sqlite3.Error, OSError):
            _error("Не удалось выполнить вход. Попробуйте ещё раз через минуту.")
        else:
            st.session_state[TOKEN_KEY] = token
            st.rerun()
    with st.expander("Как получить доступ HR или администратора?"):
        st.write("Войдите с рабочей почтой и выберите роль, назначенную вашему аккаунту. Доступ HR и администратора выдаёт администратор Career Quest.")


def _register(service):
    st.html('<p class="auth-role-hint">Создайте аккаунт сотрудника и начните с первого шага.</p>')
    with st.form("cq_auth_register", clear_on_submit=True, border=False):
        name = st.text_input("Имя и фамилия", placeholder="Как к вам обращаться", max_chars=120)
        email = st.text_input("Рабочая почта", placeholder="name@company.kz", max_chars=254)
        password_column, confirmation_column = st.columns(2)
        with password_column:
            password = st.text_input("Пароль", type="password", placeholder="От 15 символов", max_chars=128,
                                     help="Используйте длинную запоминающуюся фразу: от 15 до 128 символов.")
        with confirmation_column:
            confirmation = st.text_input("Повторите пароль", type="password", placeholder="Ещё раз", max_chars=128)
        submitted = st.form_submit_button("Создать аккаунт →", type="primary", width="stretch")
    if submitted:
        try:
            service.register(name, email, password, confirmation)
        except AuthError as exc:
            _error(str(exc))
        except (sqlite3.Error, OSError):
            _error("Не удалось создать аккаунт. Попробуйте ещё раз через минуту.")
        else:
            st.session_state["cq_auth_registered"] = True
            st.rerun()
    st.caption("Новый аккаунт получает роль сотрудника. Другие роли назначает администратор.")


def render_auth(service=None):
    """Return the verified current user, or render sign-in and return None.

    The host must stop rendering protected content if None is returned and must
    separately enforce resource ownership and allowed roles on every operation.
    """
    try:
        service = service or AuthService()
        token = st.session_state.get(TOKEN_KEY)
        user = service.current_user(token) if token else None
    except (AuthError, sqlite3.Error, OSError):
        _error("Сервис входа временно недоступен. Повторите попытку позже.")
        return None
    if user:
        return user
    expired = bool(token)
    st.session_state.pop(TOKEN_KEY, None)
    registered = st.session_state.pop("cq_auth_registered", False)
    if registered:
        st.session_state["cq_auth_mode"] = "Вход"
        st.session_state["cq_auth_role"] = "employee"
    st.session_state.setdefault("cq_auth_mode", "Вход")
    with st.container(key="cq_auth"):
        left, right = st.columns([1.13, 1], gap="large")
        with left:
            _hero()
        with right:
            with st.container(key="cq_auth_card"):
                mode = st.segmented_control("Аккаунт", ["Вход", "Регистрация"],
                                            key="cq_auth_mode", label_visibility="collapsed", width="stretch")
                signup = mode == "Регистрация"
                title = "Начнём ваш путь" if signup else "Рады видеть вас"
                subtitle = "Ваше развитие начинается с одного решения." if signup else "Войдите, чтобы продолжить свой путь развития."
                st.html(f'<div class="auth-form-title"><span class="auth-eyebrow">CAREER QUEST</span><h2>{title}</h2><p>{subtitle}</p></div>')
                if registered:
                    st.success("Аккаунт создан. Войдите как сотрудник со своей почтой и паролем.")
                if expired:
                    st.info("Сессия завершена. Войдите снова, чтобы продолжить.")
                if signup:
                    _register(service)
                else:
                    _login(service)
                st.html('<div class="auth-form-footer"><span aria-hidden="true">◇</span> Пространство для роста внутри команды</div>')
    st.html('<footer class="auth-bottom"><span>Career Quest · Halyk</span><span>Каждый шаг имеет значение.</span></footer>')
    return None


def render_account(user, service=None):
    """Standalone result screen; never exposes the demonstration employee app."""
    with st.container(key="cq_auth_success"):
        st.html(f'''<div class="auth-welcome"><span class="auth-success-mark" aria-hidden="true">✓</span>
          <span class="auth-eyebrow">ВХОД ВЫПОЛНЕН</span>
          <h1>Добро пожаловать,<br>{escape(user['name'])}.</h1>
          <p>Вы вошли в Career Quest.</p>
          <div class="auth-identity"><span>{escape(user['email'])}</span><b>{ROLES[user['role']]}</b></div></div>''')
        st.info("Аккаунт готов. Подключение рабочего пространства к этой странице выполняется отдельно.")
        if st.button("Выйти из аккаунта", key="cq_auth_logout", width="stretch"):
            try:
                (service or AuthService()).logout(st.session_state.get(TOKEN_KEY))
            except (AuthError, sqlite3.Error, OSError):
                _error("Не удалось завершить сессию. Повторите попытку.")
            else:
                st.session_state.pop(TOKEN_KEY, None)
                st.rerun()
