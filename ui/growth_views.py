"""Growth screens. All mutations, calculations and model calls go through the adapter."""

import math
from datetime import date

import streamlit as st

from .components import e, html

STATUS = {'suggested': 'Предложение', 'pending': 'На рассмотрении', 'approved': 'Одобрено',
          'rejected': 'Отклонено', 'cancelled': 'Отменено', 'in_progress': 'В процессе',
          'completion_pending': 'Сертификат на проверке', 'completed': 'Обучение подтверждено'}


def action(call, success):
    """Widget callback: finish mutations before drawing the next page."""
    try:
        call()
        st.session_state.flash = success
        st.session_state.views = {}
    except (ValueError, PermissionError) as exc:
        st.session_state.flash_error = str(exc)


def radar(traits, labels):
    """Six-axis petal chart, with visible values and an accessible text equivalent."""
    center, radius = (220, 165), 100
    def point(index, scale):
        angle = -math.pi / 2 + index * math.pi / 3
        return center[0] + radius * scale * math.cos(angle), center[1] + radius * scale * math.sin(angle)
    def polygon(scale):
        return ' '.join(f'{x:.1f},{y:.1f}' for x, y in (point(i, scale) for i in range(6)))
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" class="cq-radar" viewBox="0 0 440 340" role="img" aria-label="Шесть характеристик сотрудника, оценка HR от нуля до пяти" font-family="Segoe UI, sans-serif">']
    for scale in (.2, .4, .6, .8, 1):
        parts.append(f'<polygon points="{polygon(scale)}" fill="none" stroke="#cdded5" stroke-width="1"/>')
    for i in range(6):
        x, y = point(i, 1)
        parts.append(f'<line x1="220" y1="165" x2="{x}" y2="{y}" stroke="#cdded5"/>')
    if traits:
        points = ' '.join(f'{x:.1f},{y:.1f}' for i, key in enumerate(labels) for x, y in [point(i, traits[key] / 5)])
        parts.append(f'<polygon points="{points}" fill="#087b5b" fill-opacity="0.22" stroke="#087b5b" stroke-width="3"/>')
    for i, (key, label) in enumerate(labels.items()):
        x, y = point(i, 1.4)
        value = f"{traits[key]}/5" if traits else '—'
        parts.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" fill="#182e27" font-size="11" font-weight="600">{e(label)}</text>')
        parts.append(f'<text x="{x:.1f}" y="{y+17:.1f}" text-anchor="middle" fill="#087b5b" font-size="12" font-weight="700">{value}</text>')
    parts.append('</svg>')
    # Streamlit sanitizes inline SVG out of st.html; its image component supports SVG.
    st.image(''.join(parts), width='stretch')


@st.fragment(run_every=60)
def render_profile(adapter, dataset, employee_id):
    state = adapter.growth.snapshot(dataset, employee_id)
    left, right = st.columns([1, 1.1], gap='large')
    with left, st.container(border=True):
        html('<span class="cq-tag">Паспорт развития</span>')
        st.subheader('Характеристики')
        radar(state['profile']['traits'], adapter.growth.traits)
        if not state['profile']['assessed']:
            st.caption('HR ещё не выставил оценки. Значения не предполагаются автоматически.')
        else:
            with st.expander('Оценки текстом'):
                for key, label in adapter.growth.traits.items():
                    st.write(f"{label}: {state['profile']['traits'][key]} / 5")
    with right, st.container(border=True):
        html(f'<span class="cq-tag">Уровень {state["level"]}</span><div class="cq-xp-value">{state["xp"]:,} <span>XP</span></div>')
        st.progress(state['level_xp'] / state['next_level_xp'], text=f"{state['level_xp']} / 1000 XP до следующего уровня")
        st.caption('Уровень опыта — игровой прогресс, не должностной грейд.')
        a, b = st.columns(2)
        a.metric('За стаж', f"{state['tenure_xp']} XP")
        b.metric('За обучение', f"{state['learning_xp']} XP")
        st.write(f"Дата выхода: **{state['profile']['hire_date']}**")
        st.caption('Каждый полный день с даты выхода: +10 XP. Подтверждённый HR курс: +100 XP. Профиль обновляется раз в минуту.')
        st.divider()
        st.subheader('Подтверждённая база')
        approved = [c for c in state['certificates'] if c['status'] == 'approved']
        pending = sum(c['status'] == 'pending' for c in state['certificates'])
        st.write(f'Курсов подтверждено: **{len(approved)}** · Ожидают HR: **{pending}**')
        st.caption('Профессиональные навыки: стартовая оценка core + прирост, подтверждённый HR. Характеристики на диаграмме HR оценивает отдельно.')
        for skill in sorted(state['view']['skills'], key=lambda s: -s['current'])[:4]:
            st.write(f"**{skill['label']}** · {skill['current']} / {skill['required']}")


def certificate_form(adapter, dataset, employee_id, request=None):
    prefix = f"certificate-{employee_id}" if request is None else f"completion-{request['id']}"
    def submit():
        def save():
            values = st.session_state
            if request is None:
                adapter.growth.submit_certificate(dataset, employee_id, values[prefix+'-title'],
                    values[prefix+'-provider'], values[prefix+'-url'], values[prefix+'-date'],
                    values[prefix+'-evidence'], values[prefix+'-skills'], values[prefix+'-tags'])
            else:
                adapter.growth.submit_training_completion(dataset, employee_id, request['id'],
                    values[prefix+'-date'], values[prefix+'-evidence'], values[prefix+'-skills'], values[prefix+'-tags'])
                st.session_state.pop(f'completion-open-{employee_id}', None)
        action(save, 'Сертификат отправлен HR. До одобрения опыт и навыки не начисляются.')
    with st.form(prefix, clear_on_submit=False):
        if request is None:
            left, right = st.columns(2)
            left.text_input('Название пройденного курса', max_chars=160, key=prefix+'-title')
            right.text_input('Учебный провайдер', max_chars=100, key=prefix+'-provider')
            st.text_input('Ссылка на курс', placeholder='https://...', max_chars=1500, key=prefix+'-url')
        else:
            st.write('Подтвердите завершение: **' + request['title'] + '**')
        st.date_input('Дата завершения курса', value=date.today(), max_value=date.today(), key=prefix+'-date')
        st.text_input('Ссылка или номер сертификата', max_chars=500, key=prefix+'-evidence')
        st.multiselect('Какие навыки развивали', list(adapter.catalog), format_func=adapter.skill_name, key=prefix+'-skills')
        st.text_input('Другие навыки и темы', placeholder='Например: SOC, SIEM', max_chars=300, key=prefix+'-tags')
        st.form_submit_button('Отправить сертификат HR', type='primary', on_click=submit)


def render_certificates(adapter, dataset, employee_id):
    st.subheader('Курсы и сертификаты')
    st.caption('Укажите пройденный курс и подтверждение. Опыт и навыки изменятся после решения HR.')
    certificate_form(adapter, dataset, employee_id)
    certificates = adapter.growth.snapshot(dataset, employee_id)['certificates']
    if not certificates:
        st.info('Пока нет отправленных сертификатов.')
    for certificate in certificates:
        item = certificate['payload']
        with st.container(border=True):
            st.write(f"**{item['title']}** · {item['provider']}")
            st.caption(f"{STATUS[certificate['status']]} · завершён {item['completed_on']}")
            if certificate['reason']:
                st.write('HR: ' + certificate['reason'])
            if certificate['status'] == 'approved':
                gains = ', '.join(f'{adapter.skill_name(sid)} +{gain}' for sid, gain in certificate['awards'].items() if gain)
                st.success('+100 XP' + (' · ' + gains if gains else ' · без изменения уровней навыков'))
            st.link_button('Страница курса', item['url'])


def change_tab(tab):
    st.session_state.employee_tab = tab


def open_completion(employee_id, request_id):
    st.session_state[f'completion-open-{employee_id}'] = request_id


@st.fragment(run_every=2)
def research_progress(adapter, dataset, employee_id):
    result = adapter.growth.development_plan(dataset, employee_id)
    if result['status'] == 'running':
        st.info('Подбор выполняется в фоне. Можно переключать разделы и роли.')
    else:
        # Only a finished background job refreshes the page, never a card mutation.
        st.rerun(scope='app')


def plan_header(adapter, dataset, employee_id, plan):
    def start():
        action(lambda: adapter.growth.start_research(dataset, employee_id, trigger='manual'),
               'Запуск подбора проверен. Состояние запроса показано ниже.')
    st.button('Обновить подбор' if plan.get('plan_id') else 'Подобрать треки и найти курсы',
              key=f'research-{employee_id}', on_click=start, disabled=plan['status'] == 'running' or bool(plan.get('retry_after_seconds')), type='primary')
    budget = plan['budget']
    st.caption(f"Бюджет поиска: {budget['used']:.3f} USD из {budget['limit']:.2f} USD учтено / зарезервировано. До {budget['per_request']:.2f} USD на подбор.")
    st.caption('GPT-5 · автоподбор на карте не чаще раза в неделю. Обновление вручную — отдельный платный запрос.')
    if plan.get('retry_after_seconds'):
        st.caption(f"Повторный ручной подбор доступен через {plan['retry_after_seconds']} сек. Обновите страницу после этой паузы.")
    if plan.get('is_stale'):
        st.warning('План устарел. Подтверждённый опыт изменился или прошла неделя. Выбранные курсы сохранены; можно обновить подбор вручную.')
    if plan.get('message'):
        st.info(plan['message'])
    if plan.get('error_code'):
        st.caption('Код: ' + plan['error_code'] + (' · Запрос: ' + str(plan['request_id']) if plan.get('request_id') else ''))
    if plan['status'] == 'running':
        research_progress(adapter, dataset, employee_id)
    if plan.get('sources_insufficient'):
        st.caption('Источников поиска недостаточно для нескольких вариантов в каждом направлении. Показаны только подтверждённые ссылки.')
    if plan.get('summary'):
        st.write(plan['summary'])
    elif plan['status'] != 'running':
        st.caption('Объяснение по правилам core:')
        for rec in plan['snapshot']['view'].get('recommendations', [])[:1]:
            st.write(rec.get('explanation') or (rec.get('reasons') or [''])[0])
            if rec.get('reasons'):
                with st.expander('Факторы исходного движка'):
                    for reason in rec['reasons']:
                        st.write(reason)
            if rec.get('skill_changes'):
                st.caption('Прогноз core для активности «' + rec['title'] + '»; не начисление за внешние курсы:')
                for change in rec['skill_changes']:
                    st.write(f"{change['label']}: {change['before']} → {change['after']}")


def references(plan):
    facts = plan['facts']
    refs = {s['ref']: f"{s['name']}: {s['level']}/5" for s in facts['skills']}
    refs.update({c['ref']: f"Сертификат: {c['title']}" for c in facts['certificates']})
    refs['role'] = f"{facts['role']} · {facts['grade']}"
    return refs


def track_details(track, plan):
    st.subheader(track['title'])
    st.write(track['explanation'])
    refs = references(plan)
    st.caption('Подтверждённые основания: ' + ' · '.join(refs.get(r, r) for r in track['basis_refs']))
    st.write('Предлагаемые навыки: ' + ', '.join(track['next_skills']))
    st.caption('Будущие навыки — предложение. Прирост уровня определяет HR после обучения.')


def alternatives(track_id):
    st.session_state['growth-track-filter'] = track_id
    change_tab('Треки и курсы')


def course_card(adapter, dataset, employee_id, plan, course, track_id, prefix='course'):
    with st.container(border=True):
        st.write(f"**{course['title']}** · {course['provider']}")
        st.write(course.get('why') or course.get('reason', ''))
        st.caption(f"{course.get('level', '')} · {course.get('price_text', 'Стоимость уточнить у провайдера')}")
        st.link_button('Открыть курс · источник', course['url'])
        cid = course['id']
        prefix = prefix + '-' + track_id
        if course.get('request_id'):
            st.info('В маршруте: ' + STATUS.get(course['status'], course['status']))
            st.button('Открыть заявку', key=f'{prefix}-route-{cid}', on_click=change_tab, args=('Мой маршрут',))
        else:
            st.button('Хочу этот курс', key=f'{prefix}-want-{cid}', type='primary', on_click=action,
                      args=(lambda: adapter.growth.choose_course(dataset, employee_id, plan['plan_id'], cid),
                            'Курс добавлен в маршрут. Заявка отправлена HR.'))
        a, b = st.columns(2)
        hidden = course.get('hidden', False)
        a.button('Восстановить' if hidden else 'Не подходит', key=f'{prefix}-hide-{cid}', on_click=action,
                 args=(lambda: adapter.growth.hide_course(dataset, employee_id, plan['plan_id'], cid, hidden=not hidden),
                       'Предложение восстановлено.' if hidden else 'Предложение скрыто. XP не изменился.'))
        b.button('Другие варианты', key=f'{prefix}-other-{cid}', on_click=alternatives, args=(track_id,))


def custom_course_form(adapter, dataset, employee_id):
    prefix = f'custom-{employee_id}'
    def submit():
        action(lambda: adapter.growth.add_custom_course(dataset, employee_id,
            st.session_state[prefix+'-title'], st.session_state[prefix+'-url'], st.session_state[prefix+'-reason']),
            'Ваш курс добавлен в маршрут и отправлен HR.')
    with st.expander('Предложить свой курс'):
        with st.form(prefix):
            st.text_input('Название своего курса', key=prefix+'-title', max_chars=160)
            st.text_input('HTTPS-ссылка на курс', key=prefix+'-url', max_chars=1500)
            st.text_area('Почему хотите этот курс', key=prefix+'-reason', max_chars=500)
            st.form_submit_button('Предложить курс HR', on_click=submit)


def hidden_courses(adapter, dataset, employee_id, plan):
    hidden = [(t, c) for t in plan['tracks'] for c in t['courses'] if c.get('hidden')]
    if hidden:
        with st.expander(f'Скрытые предложения · {len(hidden)}'):
            for track, course in hidden:
                course_card(adapter, dataset, employee_id, plan, course, track['id'], prefix='hidden')


def render_tracks(adapter, dataset, employee_id):
    st.subheader('В какую сторону расти')
    plan = adapter.growth.development_plan(dataset, employee_id)
    plan_header(adapter, dataset, employee_id, plan)
    selected = st.session_state.get('growth-track-filter')
    tracks = plan['tracks']
    if selected and any(t['id'] == selected for t in tracks):
        st.caption('Альтернативы выбранного направления')
        st.button('Показать все направления', on_click=lambda: st.session_state.pop('growth-track-filter', None))
        tracks = [t for t in tracks if t['id'] == selected]
    for track in tracks:
        track_details(track, plan)
        visible = [c for c in track['courses'] if not c.get('hidden')]
        if not visible:
            st.caption('Подтверждённых видимых вариантов нет. Можно восстановить предложение или добавить свой курс.')
        for course in visible:
            course_card(adapter, dataset, employee_id, plan, course, track['id'])
    hidden_courses(adapter, dataset, employee_id, plan)
    custom_course_form(adapter, dataset, employee_id)
    st.button('Перейти в мой маршрут', on_click=change_tab, args=('Мой маршрут',))


def render_growth_map(adapter, dataset, employee_id):
    from .map_component import build_map_model, render_interactive_map
    # The service enforces the persisted weekly attempt gate, including failures.
    adapter.growth.start_research(dataset, employee_id, trigger='auto')
    plan = adapter.growth.development_plan(dataset, employee_id)
    st.subheader('Карта развития')
    plan_header(adapter, dataset, employee_id, plan)
    state = dict(plan['snapshot'], skill_labels={sid: adapter.skill_name(sid) for sid in adapter.catalog})
    node = render_interactive_map(build_map_model(plan, state), key=f'growth-map-{employee_id}')
    if node:
        kind = node['kind']
        if kind == 'course':
            course_card(adapter, dataset, employee_id, plan, node['payload'], node['track_id'], prefix='map')
            track = next((t for t in plan['tracks'] if t['id'] == node['track_id']), None)
            if track:
                track_details(track, plan)
        elif kind == 'track':
            track_details(node['payload'], plan)
            for course in node['payload']['courses']:
                if not course.get('hidden'):
                    course_card(adapter, dataset, employee_id, plan, course, node['track_id'], prefix='map')
        else:
            st.subheader(node['label'])
            st.caption('Предлагаемый навык; ещё не подтверждён.' if kind == 'future_skill' else 'Подтверждённая база сотрудника.')
    else:
        st.caption('Выберите узел карты, чтобы увидеть объяснение, источник и варианты действий.')
    hidden_courses(adapter, dataset, employee_id, plan)
    custom_course_form(adapter, dataset, employee_id)


def render_route(adapter, dataset, employee_id):
    st.subheader('Мой маршрут')
    st.caption('Выбирайте несколько курсов. Согласование бюджета, обучение и проверка сертификата — отдельные шаги.')
    plan = adapter.growth.development_plan(dataset, employee_id)
    if not plan['requests']:
        st.info('В маршруте пока нет курсов. Выберите предложение на карте или добавьте свою ссылку.')
    for request in plan['requests']:
        rid, status = request['id'], request['status']
        with st.container(border=True, key=f'route-{rid}'):
            st.write(f"**{request['title']}** · {STATUS.get(status, status)}")
            st.caption('Предложение сотрудника' if request.get('source') == 'employee' else 'Из плана развития')
            if request.get('reason'):
                st.write('HR: ' + request['reason'])
            st.link_button('Страница курса', request['url'])
            if status == 'approved':
                st.button('Начать обучение', key=f'start-{rid}', on_click=action,
                          args=(lambda rid=rid: adapter.growth.start_training(dataset, employee_id, rid), 'Обучение начато.'))
            if status == 'in_progress':
                st.button('Завершить обучение', key=f'finish-{rid}', type='primary',
                          on_click=open_completion, args=(employee_id, rid))
                if st.session_state.get(f'completion-open-{employee_id}') == rid:
                    certificate_form(adapter, dataset, employee_id, request)
            if status in {'pending', 'approved', 'in_progress'}:
                st.button('Отменить заявку', key=f'cancel-{rid}', on_click=action,
                          args=(lambda rid=rid: adapter.growth.cancel_training(dataset, employee_id, rid), 'Заявка отменена. XP не изменился.'))
            st.button('Выбрать другой курс', key=f'replace-{rid}', on_click=change_tab, args=('Треки и курсы',))
    st.button('Выбрать курсы на карте', on_click=change_tab, args=('Карта развития',))
    custom_course_form(adapter, dataset, employee_id)


def render_hr_profile(adapter, dataset, employee_id):
    profile = adapter.growth.profile(dataset, employee_id)
    st.subheader('Характеристики и дата выхода')
    st.caption('Сотрудник выбран в боковой панели. Оценки по шкале 0–5 задаёт HR.')
    def save():
        action(lambda: adapter.growth.save_profile(dataset, employee_id, st.session_state[f'hire-{employee_id}'],
            {key: st.session_state[f'trait-{employee_id}-{key}'] for key in adapter.growth.traits}, actor='hr'),
            'Характеристики и дата выхода сохранены.')
    left, right = st.columns([1.25, 1])
    with left, st.form(f'hr-profile-{employee_id}'):
        st.date_input('Дата начала работы', value=date.fromisoformat(profile['hire_date']), key=f'hire-{employee_id}',
                      min_value=date(1960, 1, 1), max_value=date(date.today().year + 1, 12, 31))
        for key, label in adapter.growth.traits.items():
            st.slider(label, 0, 5, profile['traits'].get(key, 3), key=f'trait-{employee_id}-{key}')
        st.form_submit_button('Сохранить профиль HR', type='primary', on_click=save)
    with right:
        radar(profile['traits'], adapter.growth.traits)


def render_hr_requests(adapter, dataset, employees):
    names = {e['employee_id']: e.get('full_name', e['employee_id']) for e in employees}
    certificates = adapter.growth.store.rows('certificates')
    requests = adapter.growth.store.rows('training_requests')
    pending = [c for c in certificates if c['status'] == 'pending' and c['employee_id'] in names]
    st.subheader(f'Сертификаты на проверке · {len(pending)}')
    if not pending:
        st.caption('Новых сертификатов нет.')
    for certificate in pending:
        item, cid = certificate['payload'], certificate['id']
        def review(approve, cid=cid):
            action(lambda: adapter.growth.review_certificate(dataset, cid, approve,
                dict.fromkeys(st.session_state[f'awards-{cid}'], 1), st.session_state[f'cert-reason-{cid}'], actor='hr'),
                'Решение по сертификату сохранено.')
        with st.expander(f"{names[certificate['employee_id']]} · {item['title']}", expanded=True):
            st.write(f"Провайдер: {item['provider']} · завершён {item['completed_on']}")
            st.write('Подтверждение: ' + item['evidence'])
            st.write('Темы: ' + (item['tags'] or 'Не указаны'))
            st.link_button('Проверить страницу курса', item['url'])
            with st.form(f'review-cert-{cid}'):
                st.multiselect('Подтвердить прирост +1 по навыкам', list(adapter.catalog),
                               default=item['skill_ids'], format_func=adapter.skill_name, key=f'awards-{cid}')
                st.caption('Оставьте список пустым, если прирост уровня не установлен. Максимум — 5.')
                st.text_input('Комментарий HR', key=f'cert-reason-{cid}', max_chars=500)
                yes, no = st.columns(2)
                yes.form_submit_button('Подтвердить сертификат', type='primary', on_click=review, args=(True,))
                no.form_submit_button('Отклонить сертификат', on_click=review, args=(False,))
    pending_requests = [r for r in requests if r['status'] == 'pending' and r['employee_id'] in names]
    st.subheader(f'Запросы бюджета на обучение · {len(pending_requests)}')
    if not pending_requests:
        st.caption('Запросов на обучение пока нет.')
    for request in pending_requests:
        item, rid = request['payload'], request['id']
        def decide(rid=rid):
            decision = st.session_state[f'decision-{rid}']
            comment = st.session_state[f'budget-reason-{rid}']
            action(lambda: adapter.growth.decide_training(rid, decision == 'Одобрить',
                decision + (': ' + comment if comment else ''), actor='hr'), 'Решение по обучению отправлено сотруднику.')
        with st.expander(f"{names[request['employee_id']]} · {item['title']}", expanded=True):
            st.write(item.get('why', ''))
            st.caption(f"{item['provider']} · {item.get('price_text', 'Стоимость уточняется')}")
            st.link_button('Страница провайдера', item['url'])
            with st.form(f'review-budget-{rid}'):
                st.selectbox('Решение по бюджету', ['Одобрить', 'Нет бюджета', 'Не соответствует плану развития', 'Нужны уточнения'], key=f'decision-{rid}')
                st.text_input('Комментарий сотруднику', key=f'budget-reason-{rid}', max_chars=400)
                st.form_submit_button('Отправить решение сотруднику', type='primary', on_click=decide)
    reviewed = [r for r in certificates + requests if r['status'] != 'pending' and r['employee_id'] in names]
    with st.expander(f'Последние решения · {len(reviewed)}'):
        for row in sorted(reviewed, key=lambda r: r['reviewed_at'] or '', reverse=True)[:20]:
            st.write(f"{names[row['employee_id']]} · {row['payload']['title']} · {STATUS.get(row['status'], row['status'])}")
            st.caption(row['reason'] or 'Решение сохранено')
    budget = adapter.growth.budget()
    st.caption(f"AI: {budget['used']:.3f} USD учтено / зарезервировано из {budget['limit']:.2f} USD. Новый запрос — до {budget['per_request']:.2f} USD.")
