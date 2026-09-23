"""First-run setup and account/profile administration for the local application."""

import streamlit as st

from auth.service import AuthError
from auth.ui import ROLES, TOKEN_KEY, _hero


def render_first_admin(service):
    left, right = st.columns([1.13, 1], gap='large')
    with left:
        _hero()
    with right, st.container(key='cq_auth_card'):
        st.subheader('Настроим ваше пространство')
        st.write('Это первый запуск. Создайте личный аккаунт администратора — он управляет пользователями и связывает их с профилями сотрудников.')
        st.caption('База создаётся на этом компьютере. Внешний сервис и общие пароли не нужны.')
        with st.form('cq_first_admin', clear_on_submit=True, border=False):
            name = st.text_input('Имя и фамилия', max_chars=120)
            email = st.text_input('Рабочая почта', placeholder='name@company.kz', max_chars=254)
            password = st.text_input('Пароль', type='password', max_chars=128, help='От 15 до 128 символов. Можно использовать фразу.')
            confirmation = st.text_input('Повторите пароль', type='password', max_chars=128)
            submit = st.form_submit_button('Создать пространство →', type='primary', width='stretch')
        if submit:
            try:
                service.create_admin(name, email, password, confirmation)
                token, _ = service.login(email, password, 'admin')
            except AuthError as exc:
                st.error(str(exc))
            else:
                st.session_state[TOKEN_KEY] = token
                st.session_state.flash = 'Пространство готово. Зарегистрированные сотрудники появятся в разделе «Пользователи».'
                st.rerun()


def render_users(service, token, employees):
    st.title('Пользователи')
    st.caption('Назначьте роль и привяжите аккаунт к профилю. Каждый профиль может принадлежать одному аккаунту. Изменение роли или привязки завершает прежние сессии пользователя.')
    users = service.list_users(token)
    names = {p['employee_id']: p.get('full_name', p['employee_id']) for p in employees}
    st.dataframe([
        {'Имя': u['name'], 'Почта': u['email'], 'Роль': ROLES[u['role']],
         'Профиль': names.get(u.get('employee_id'), u.get('employee_id') or 'Не назначен')}
        for u in users
    ], hide_index=True, width='stretch')
    by_id = {u['user_id']: u for u in users}
    selected = st.selectbox('Аккаунт', list(by_id), key='account_to_manage',
                            format_func=lambda uid: f"{by_id[uid]['name']} · {by_id[uid]['email']}")
    user = by_id[selected]
    with st.form(f'configure-user-{selected}'):
        role = st.selectbox('Роль аккаунта', list(ROLES), index=list(ROLES).index(user['role']), format_func=ROLES.get)
        options = [None, *names]
        linked = user.get('employee_id')
        employee_id = st.selectbox('Профиль сотрудника', options,
            index=options.index(linked) if linked in options else 0,
            format_func=lambda eid: f'{names[eid]} · {eid}' if eid else 'Пока не назначен')
        st.caption('Выбирайте профиль после проверки принадлежности аккаунта сотруднику. Назначенная роль хранится в базе, её нельзя получить переключателем на входе.')
        saved = st.form_submit_button('Сохранить доступ', type='primary')
    if saved:
        try:
            service.configure_user(token, selected, role, employee_id, set(names))
        except (AuthError, PermissionError) as exc:
            st.error(str(exc))
        else:
            st.session_state.flash = 'Доступ обновлён. При изменении роли или профиля пользователь должен войти заново.'
            st.rerun()
