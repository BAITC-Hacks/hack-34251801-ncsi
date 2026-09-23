"""Growth screens. All mutations, calculations and model calls go through the adapter."""

import math
from datetime import date

import streamlit as st

from .components import e, html

STATUS = {'pending': 'На рассмотрении', 'approved': 'Одобрено', 'rejected': 'Отклонено'}


def action(call, success):
    try:
        call()
        st.session_state.flash = success
        st.rerun()
    except (ValueError, PermissionError) as exc:
        st.error(str(exc))


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


def render_certificates(adapter, dataset, employee_id):
    st.subheader('Курсы и сертификаты')
    st.caption('Укажите пройденный курс и подтверждение. Опыт и навыки изменятся после решения HR.')
    with st.form(f'certificate-{employee_id}', clear_on_submit=False):
        left, right = st.columns(2)
        title = left.text_input('Название пройденного курса', max_chars=160)
        provider = right.text_input('Учебный провайдер', max_chars=100)
        url = st.text_input('Ссылка на курс', placeholder='https://...', max_chars=1500)
        completed = st.date_input('Дата завершения курса', value=date.today(), max_value=date.today())
        evidence = st.text_input('Ссылка или номер сертификата', max_chars=500)
        selected = st.multiselect('Какие навыки развивали', list(adapter.catalog), format_func=adapter.skill_name)
        tags = st.text_input('Другие навыки и темы', placeholder='Например: SOC, SIEM, расследование инцидентов', max_chars=300)
        submitted = st.form_submit_button('Отправить сертификат HR', type='primary')
    if submitted:
        action(lambda: adapter.growth.submit_certificate(dataset, employee_id, title, provider, url, completed, evidence, selected, tags),
               'Сертификат отправлен HR. До одобрения опыт и навыки не начисляются.')
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


def render_tracks(adapter, dataset, employee_id):
    st.subheader('В какую сторону расти')
    st.caption('AI учитывает подтверждённые сертификаты, навыки и цель. Глубокая специализация даёт следующий уровень; смешанный опыт — несколько направлений.')
    result = adapter.growth.recommend(dataset, employee_id)
    budget_caption = st.empty()
    if st.button('Подобрать треки и найти курсы', key=f'research-{employee_id}', type='primary'):
        with st.spinner('Анализируем подтверждённый опыт и ищем реальные курсы…'):
            try:
                result = adapter.growth.recommend(dataset, employee_id, generate=True)
            except ValueError as exc:
                st.error(str(exc))
    budget = result['budget']
    budget_caption.caption(f"Бюджет поиска: {budget['used']:.3f} USD из {budget['limit']:.2f} USD учтено / зарезервировано. До {budget['per_request']:.2f} USD за запрос. Кеш — 7 дней.")
    if result.get('message'):
        st.info(result['message'])
    if result.get('summary'):
        st.write(result['summary'])
        st.caption(f"GPT‑4.1 mini · {'из кеша' if result['status'] == 'cached' else 'новый подбор'} · поиск {result['searched_at'][:10]}")
    facts = adapter.growth.facts(dataset, employee_id)
    references = {s['ref']: f"{s['name']}: {s['level']}/5" for s in facts['skills']}
    references.update({c['ref']: f"Сертификат: {c['title']}" for c in facts['certificates']})
    references['role'] = f"{facts['role']} · {facts['grade']}"
    for i, track in enumerate(result['tracks']):
        with st.container(border=True):
            st.caption('Углубление специализации' if track['kind'] == 'specialization' else 'Новая ветка развития')
            st.subheader(track['title'])
            st.write(track['explanation'])
            st.caption('Подтверждённые основания: ' + ' · '.join(references[r] for r in track['basis_refs']))
            st.write('Что развивать: ' + ', '.join(track['next_skills']))
            if not track['courses']:
                st.caption('В этом поиске не найдены подтверждённые страницы подходящих курсов.')
            for j, course in enumerate(track['courses']):
                st.divider()
                st.write(f"**{course['title']}** · {course['provider']}")
                st.write(course['why'])
                st.caption(f"{course['level']} · {course['price_text']}")
                link, want = st.columns(2)
                link.link_button('Открыть курс · источник', course['url'], width='stretch')
                if want.button('Хочу на этот курс', key=f'want-{result["plan_id"]}-{i}-{j}', width='stretch'):
                    action(lambda: adapter.growth.request_training(dataset, employee_id, result['plan_id'], i, j),
                           'Запрос на обучение отправлен HR. Оплата не выполнялась.')
    st.subheader('Мои запросы на обучение')
    requests = adapter.growth.snapshot(dataset, employee_id)['requests']
    if not requests:
        st.caption('Выберите «Хочу на этот курс» у найденного предложения.')
    for request in requests:
        with st.container(border=True):
            st.write(f"**{request['payload']['title']}** — {STATUS[request['status']]}")
            st.write(request['reason'] or 'HR ещё не принял решение.')
            st.link_button('Курс', request['url'])


def render_hr_profile(adapter, dataset, employee_id):
    profile = adapter.growth.profile(dataset, employee_id)
    st.subheader('Характеристики и дата выхода')
    st.caption('Сотрудник выбран в боковой панели. Оценки по шкале 0–5 задаёт HR.')
    left, right = st.columns([1.25, 1])
    with left, st.form(f'hr-profile-{employee_id}'):
        started = st.date_input('Дата начала работы', value=date.fromisoformat(profile['hire_date']),
                                min_value=date(1960, 1, 1), max_value=date(date.today().year + 1, 12, 31))
        values = {key: st.slider(label, 0, 5, profile['traits'].get(key, 3), key=f'trait-{employee_id}-{key}')
                  for key, label in adapter.growth.traits.items()}
        saved = st.form_submit_button('Сохранить профиль HR', type='primary')
    with right:
        radar(profile['traits'], adapter.growth.traits)
    if saved:
        action(lambda: adapter.growth.save_profile(dataset, employee_id, started, values, actor='hr'), 'Характеристики и дата выхода сохранены.')


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
        with st.expander(f"{names[certificate['employee_id']]} · {item['title']}", expanded=True):
            st.write(f"Провайдер: {item['provider']} · завершён {item['completed_on']}")
            st.write('Подтверждение: ' + item['evidence'])
            st.write('Темы: ' + (item['tags'] or 'Не указаны'))
            st.link_button('Проверить страницу курса', item['url'])
            with st.form(f'review-cert-{cid}'):
                skills = st.multiselect('Подтвердить прирост +1 по навыкам', list(adapter.catalog),
                                        default=item['skill_ids'], format_func=adapter.skill_name, key=f'awards-{cid}')
                st.caption('Оставьте список пустым, если курс подтверждён, но прирост уровня не установлен. Максимум уровня — 5.')
                reason = st.text_input('Комментарий HR', key=f'cert-reason-{cid}', max_chars=500)
                yes, no = st.columns(2)
                approve = yes.form_submit_button('Подтвердить сертификат', type='primary')
                reject = no.form_submit_button('Отклонить сертификат')
            if approve or reject:
                action(lambda: adapter.growth.review_certificate(dataset, cid, approve, dict.fromkeys(skills, 1), reason, actor='hr'),
                       'Решение по сертификату сохранено.')
    pending_requests = [r for r in requests if r['status'] == 'pending' and r['employee_id'] in names]
    st.subheader(f'Запросы бюджета на обучение · {len(pending_requests)}')
    if not pending_requests:
        st.caption('Запросов на обучение пока нет.')
    for request in pending_requests:
        item, rid = request['payload'], request['id']
        with st.expander(f"{names[request['employee_id']]} · {item['title']}", expanded=True):
            st.write(item['why'])
            st.caption(f"{item['provider']} · {item['price_text']}")
            st.link_button('Страница провайдера', item['url'])
            with st.form(f'review-budget-{rid}'):
                decision = st.selectbox('Решение по бюджету', ['Одобрить', 'Нет бюджета', 'Не соответствует плану развития', 'Нужны уточнения'], key=f'decision-{rid}')
                comment = st.text_input('Комментарий сотруднику', key=f'budget-reason-{rid}', max_chars=400)
                save = st.form_submit_button('Отправить решение сотруднику', type='primary')
            if save:
                action(lambda: adapter.growth.decide_training(rid, decision == 'Одобрить', decision + (': ' + comment if comment else ''), actor='hr'),
                       'Решение по обучению отправлено сотруднику.')
    reviewed = [r for r in certificates + requests if r['status'] != 'pending' and r['employee_id'] in names]
    with st.expander(f'Последние решения · {len(reviewed)}'):
        for row in sorted(reviewed, key=lambda r: r['reviewed_at'], reverse=True)[:20]:
            st.write(f"{names[row['employee_id']]} · {row['payload']['title']} · {STATUS[row['status']]}")
            st.caption(row['reason'] or 'Подтверждено HR')
    budget = adapter.growth.budget()
    st.caption(f"AI: {budget['used']:.3f} USD учтено / зарезервировано из {budget['limit']:.2f} USD. Новый запрос — до {budget['per_request']:.2f} USD.")
