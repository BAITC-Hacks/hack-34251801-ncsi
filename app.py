"""Career Quest — Streamlit entry point."""
import os
import logging
from html import escape
from pathlib import Path
import streamlit as st
from ui.adapter import Engine, friendly_error

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='Career Quest · Halyk', page_icon='🌱', layout='wide')
st.markdown('<style>' + (ROOT / 'styles/main.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)

def error(exc):
    logging.exception('Career Quest operation failed')
    st.error(friendly_error(exc))
    with st.expander('Технические подробности'):
        st.code(f'{type(exc).__name__}: {exc}')

def safe(value):
    return escape(str(value))

def records(title, rows, empty):
    st.subheader(title)
    if rows:
        st.dataframe(rows, hide_index=True, width='stretch')
    else:
        st.info(empty)

try:
    engine = Engine()
except Exception as exc:
    error(exc)
    st.stop()

with st.sidebar:
    st.markdown('### 🌱 Career Quest')
    st.caption('HALYK · РАЗВИТИЕ СОТРУДНИКОВ')
    mode = st.radio('Представление', ['Сотрудник', 'HR', 'Импорт данных'])
    st.caption('Демонстрационные представления, не система разграничения доступа.')
    st.divider()
    st.caption('Источник: ' + engine.key)
    data_dir = st.text_input('Папка стартового кита', value=os.environ.get('CAREER_QUEST_DATA_DIR', '__demo__' if engine.is_demo else str(ROOT / 'case/case_1/career_quest_dataset')))
    if st.button('Перезагрузить данные', width='stretch'):
        st.session_state.pop('dataset', None)
        st.session_state.pop('employee_id', None)
    st.caption('Изменения живут в текущей сессии. Перезагрузка сбрасывает их.')

if engine.is_demo:
    st.warning('Демонстрационный каркас: временные профили и правила. Стартовый кит и настоящий AI-движок ещё не подключены.')
if st.session_state.get('engine_key') != engine.key:
    st.session_state.pop('dataset', None)
    st.session_state.pop('employee_id', None)
    st.session_state.engine_key = engine.key
if 'dataset' not in st.session_state:
    try:
        st.session_state.dataset = engine.load(data_dir)
    except Exception as exc:
        error(exc)
        st.stop()
dataset = st.session_state.dataset
if dataset.get('_demo_only') and not engine.is_demo:
    st.warning('Вы явно выбрали __demo__: показаны временные демонстрационные данные, не стартовый кит.')
if message := st.session_state.pop('notice', None):
    st.success(message)

if mode == 'Сотрудник':
    try:
        employees = engine.employees(dataset)
    except Exception as exc:
        error(exc)
        st.stop()
    if not employees:
        st.info('Профилей пока нет. Загрузите их в разделе «Импорт данных».')
        st.stop()
    labels = {str(e['employee_id']): f"{e.get('name') or e['employee_id']} · {e.get('role', '')}" for e in employees}
    if st.session_state.get('employee_id') not in labels:
        st.session_state.employee_id = next(iter(labels))
    top, select = st.columns([1.15, 1])
    with top:
        st.markdown('<div class="eyebrow">Мой карьерный маршрут</div>', unsafe_allow_html=True)
        st.title('Следующий шаг — понятен')
    with select:
        employee_id = st.selectbox('Сотрудник', list(labels), format_func=labels.get, key='employee_id')
    try:
        view = engine.employee(dataset, employee_id)
        e, trajectory = view['employee'], view['trajectory']
        progress = float(trajectory['progress_percent'])
    except Exception as exc:
        error(exc)
        st.stop()
    st.markdown(f'<div class="hero"><div class="eyebrow">Вы здесь</div><h2>{safe(e.get("name") or e["employee_id"])}</h2><p>{safe(e["role"])} &nbsp; / &nbsp; {safe(e["grade"])} &nbsp; / &nbsp; В команде {safe(e["tenure_months"])} мес.</p></div>', unsafe_allow_html=True)
    left, right = st.columns([.95, 1.25], gap='large')
    with left:
        with st.container(border=True):
            st.subheader('До следующего грейда')
            target = trajectory.get('target_grade') or view.get('next_grade') or 'Поддержание Lead'
            st.markdown(f'<div class="route"><strong>{safe(trajectory["current_grade"])}</strong><span>→</span><strong>{safe(target)}</strong></div>', unsafe_allow_html=True)
            st.progress(max(0., min(1., progress / 100)), text=f'{progress:g}% требований по навыкам закрыто')
            st.caption('Прогресс навыков не означает автоматического повышения грейда.')
            for s in view['skills']:
                st.markdown(f'<div class="skill-row"><b>{safe(s["label"])}</b><span>{safe(s["current"])} / {safe(s["required"])} · разрыв {safe(s["gap"])}</span></div><div class="skill-track"><div class="skill-fill" style="width:{max(0,min(100,float(s["current"])*20))}%"></div><div class="skill-target" style="left:{max(0,min(100,float(s["required"])*20))}%"></div></div>', unsafe_allow_html=True)
            if not view['skills']:
                st.info('Движок не вернул требования по навыкам.')
            st.caption('Шкала 0–5. Золотая отметка — требование следующего грейда.')
    with right:
        st.caption(engine.ai_status())
        recommendations = view['recommendations'][:3]
        if not recommendations:
            st.info('Сейчас нет рекомендованного шага. Требования могли быть достигнуты или в каталоге нет подходящей активности. Обсудите следующий шаг с HR.')
        for index, rec in enumerate(recommendations):
            with st.container(border=True):
                st.markdown('<div class="eyebrow">' + ('Ваш лучший следующий шаг' if index == 0 else f'Альтернатива {index}') + '</div>', unsafe_allow_html=True)
                st.subheader(rec['title'])
                st.markdown('**Почему этот шаг**')
                for reason in rec['reasons']:
                    st.write('• ' + str(reason))
                st.markdown('**Что изменится**')
                if rec['skill_changes']:
                    st.markdown(''.join(f'<span class="gain">{safe(c["label"])} &nbsp; {safe(c["before"])} → <b>{safe(c["after"])}</b></span>' for c in rec['skill_changes']), unsafe_allow_html=True)
                else:
                    st.caption('Численный прирост навыков не указан движком.')
                if st.button('Отметить выполненной', key=f'complete-{employee_id}-{rec["event_id"]}', type='primary' if index == 0 else 'secondary', width='stretch'):
                    try:
                        with st.spinner('Обновляем профиль и рекомендации…'):
                            candidate = engine.complete(dataset, employee_id, rec['event_id'])
                            after = engine.employee(candidate, employee_id)['trajectory']['progress_percent']
                            st.session_state.dataset = candidate
                            st.session_state.notice = f'Активность завершена. Прогресс: {progress:g}% → {after:g}%. Рекомендации обновлены.'
                        st.rerun()
                    except Exception as exc:
                        error(exc)
    with st.expander(f'История участия · {len(view["history"])}', expanded=not bool(view['history'])):
        if view['history']:
            st.dataframe(view['history'], hide_index=True, width='stretch')
        else:
            st.caption('Пока нет активностей. После первого завершения здесь появится запись.')

elif mode == 'HR':
    st.markdown('<div class="eyebrow">Команда и развитие</div>', unsafe_allow_html=True)
    st.title('Где нужна поддержка')
    st.caption('Срез развития без публичного рейтинга сотрудников.')
    try:
        hr = engine.hr(dataset)
        known = {'skill_gaps', 'employees_without_recommendations', 'activity_participation'}
        if not known <= hr.keys():
            st.warning('Формат HR API ещё не согласован. Ниже — фактический ответ движка, без подмены данных.')
            st.json(hr)
        else:
            a, b = st.columns(2)
            with a:
                records('Частые разрывы по навыкам', hr['skill_gaps'], 'Разрывов по навыкам нет.')
            with b:
                records('Сотрудники без следующего шага', hr['employees_without_recommendations'], 'У каждого сотрудника есть рекомендованный шаг.')
            records('Участие по активностям', hr['activity_participation'], 'Данных об участии пока нет.')
    except Exception as exc:
        error(exc)
else:
    st.markdown('<div class="eyebrow">Проверка новых профилей</div>', unsafe_allow_html=True)
    st.title('Новые данные. Тот же движок.')
    st.write('Загрузите дополнительные профили и историю. После успешного импорта сотрудники появятся в общем списке.')
    st.caption('Профили — employees.json; история — activity_history.csv. UTF-8, до 10 МБ на файл. Проверка схемы выполняется активным адаптером.')
    if engine.is_demo or dataset.get('_demo_only'):
        st.info('Схема демо временная: JSON-массив профилей Backend Engineer / Middle; навыки SK_PYTHON, SK_SYSTEM_DESIGN, SK_PUBLIC_SPEAKING. Официальная схема будет подтверждена по стартовому киту.')
    else:
        st.info('Формат стартового кита: JSON-объект с массивом employees (в том числе full_name, last_review_date и skills). История: record_id, employee_id, event_id, date, due_date, status, completion_pct, score, feedback_rating, assigned_by. Новые ID должны быть уникальными.')
    with st.form('import'):
        employees_file = st.file_uploader('Дополнительные профили', type=['json'], max_upload_size=10)
        history_file = st.file_uploader('История участия', type=['csv'], max_upload_size=10)
        submitted = st.form_submit_button('Проверить и импортировать', type='primary')
    if submitted:
        try:
            with st.spinner('Проверяем файлы…'):
                candidate = engine.import_files(dataset, employees_file, history_file)
                count = len(engine.employees(candidate))
                st.session_state.dataset = candidate
                st.session_state.notice = f'Импорт завершён. В списке {count} сотрудников. Откройте представление «Сотрудник».'
            st.rerun()
        except Exception as exc:
            error(exc)
