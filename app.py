"""Run with: python -m streamlit run app.py"""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from pathlib import Path

import streamlit as st

from ui.components import STATUSES, e, empty_state, html, journey, number, page_heading, recommendation_content, skill_card, stat
from ui.core_adapter import AdapterError, CoreAdapter

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("CAREER_QUEST_DATA_DIR", str(ROOT / "case/case_1/career_quest_dataset")))
LOGGER = logging.getLogger("career_quest.ui")


def show_error(exc, action):
    if isinstance(exc, (ValueError, FileNotFoundError)):
        st.error(str(exc))
    else:
        LOGGER.error("%s failed: %s", action, type(exc).__name__)
        st.error(f"Не удалось {action}. Проверьте доступность движка и повторите попытку.")


def employee_view(adapter, employee_id):
    key = (st.session_state.revision, employee_id)
    if key not in st.session_state.views:
        with st.spinner("Готовим ваш маршрут…"):
            st.session_state.views[key] = adapter.get_employee_view(st.session_state.dataset, employee_id)
    return st.session_state.views[key]


def finish_activity(adapter, employee_id, rec, current_view):
    with st.spinner("Обновляем навыки и следующий шаг…"):
        updated, view = adapter.complete_activity(st.session_state.dataset, employee_id, rec["event_id"])
    before = {s["skill_id"]: s["current"] for s in current_view["skills"]}
    changes = [f'{s["name"]}: {number(before.get(s["skill_id"], 0))} → {number(s["current"])}'
               for s in view["skills"] if s["current"] > before.get(s["skill_id"], 0)]
    st.session_state.dataset = updated
    st.session_state.revision += 1
    st.session_state.views = {(st.session_state.revision, employee_id): view}
    st.session_state.flash = f'Активность «{rec["title"]}» завершена. ' + (" · ".join(changes) if changes else "Профиль и рекомендации пересчитаны.")
    st.rerun()


def render_recommendation(adapter, view, rec, index):
    with st.container(border=True, key=f"recommendation_{index}"):
        recommendation_content(rec, best=index == 0)
        if st.button("Завершить активность" if index == 0 else "Завершить эту активность",
                     key=f'complete-{view["employee"]["employee_id"]}-{rec["event_id"]}', type="primary" if index == 0 else "secondary", width="stretch"):
            try:
                finish_activity(adapter, view["employee"]["employee_id"], rec, view)
            except Exception as exc:
                show_error(exc, "завершить активность")


def render_employee(adapter, employee_id):
    view = employee_view(adapter, employee_id)
    employee = view["employee"]
    page_heading("Ваш следующий шаг", f'{employee.get("full_name", "Сотрудник")} · {employee.get("role", "")} · Развитие в вашем темпе')
    journey(view)
    st.caption(view.get("ai_status", "Детерминированный расчёт"))
    if not view.get("next_grade"):
        st.caption("Для текущей роли следующего грейда нет. Индивидуальную цель развития можно обсудить с руководителем.")
    route, skills_tab, history_tab = st.tabs(["Мой маршрут", "Навыки и требования", "История участия"])
    with route:
        recs = view["recommendations"]
        left, right = st.columns([1.95, 1], gap="large")
        with left:
            if recs:
                render_recommendation(adapter, view, recs[0], 0)
                if len(recs) > 1:
                    with st.expander(f"Другие подходящие активности · {len(recs) - 1}"):
                        for index, rec in enumerate(recs[1:], 1):
                            render_recommendation(adapter, view, rec, index)
            else:
                with st.container(border=True):
                    empty_state("Следующий шаг требует обсуждения", view.get("empty_reason") or "Движок не нашёл подходящей активности. Посмотрите разрывы в навыках и обсудите индивидуальный план с руководителем.")
        with right:
            with st.container(border=True, key="focus"):
                html('<span class="cq-tag">Фокус развития</span>')
                st.subheader(f'До {view["next_grade"]}' if view.get("next_grade") else "Ваши навыки")
                gaps = [s for s in view["skills"] if s["gap"] > 0]
                if gaps:
                    for skill in gaps[:4]:
                        skill_card(skill)
                    if len(gaps) > 4:
                        st.caption(f'Ещё {len(gaps) - 4} — во вкладке «Навыки и требования».')
                else:
                    st.caption("Разрывов до цели по данным движка нет.")
                html('<div class="cq-rule"></div><p class="cq-help">Уровни по шкале 0–5. Выполнение требований по навыкам помогает обсудить рост, но не означает автоматического повышения.</p>')
    with skills_tab:
        st.subheader("Навыки на пути к цели")
        st.caption("Текущий уровень учитывает завершённое обучение. Требования — из профиля следующего грейда.")
        if view["skills"]:
            data = [{"Навык": s["name"], "Тип": "Профессиональный" if s["type"] == "hard" else "Надпрофессиональный",
                     "Текущий уровень": s["current"], "Требуется": s["required"], "Разрыв": s["gap"],
                     "Ключевой": "Да" if s["critical"] else "Нет"} for s in view["skills"]]
            st.dataframe(data, hide_index=True, width="stretch")
        else:
            empty_state("Требования следующего грейда не заданы", "Движок не вернул список требований для этой цели.")
    with history_tab:
        st.subheader("История участия")
        history = sorted(view["history"], key=lambda r: r.get("date", ""), reverse=True)
        if history:
            st.dataframe([{"Дата": h.get("date", ""), "Активность": h.get("title", ""),
                           "Статус": STATUSES.get(h.get("status"), h.get("status", "")),
                           "Прогресс, %": int(h.get("completion_pct") or 0)} for h in history], hide_index=True, width="stretch")
        else:
            empty_state("Пока нет истории", "Первое завершённое обучение появится здесь и будет учтено при следующем подборе.")


def render_hr(adapter, employees):
    page_heading("Развитие команды", "Где нужна поддержка, какие навыки развивать и как сотрудники участвуют в обучении.", "HR · Обзор развития")
    key = (st.session_state.revision, "__hr__")
    if key not in st.session_state.views:
        with st.spinner("Собираем обзор команды…"):
            st.session_state.views[key] = adapter.get_hr_view(st.session_state.dataset)
    view = st.session_state.views[key]
    gaps = view.get("skill_gaps", [])
    blocked = view.get("employees_without_next_step", [])
    participation = view.get("participation", [])
    a, b, c = st.columns(3)
    with a:
        stat("Профилей в датасете", len(employees), "Общий контур развития")
    with b:
        stat("Нужна помощь с маршрутом", len(blocked), "Нет подходящего следующего шага")
    with c:
        stat("Навыков с разрывами", len(gaps), "До требований следующего грейда")
    st.write("")
    left, right = st.columns([1.1, 1], gap="large")
    with left, st.container(border=True, key="hr_gaps"):
        st.subheader("Частые разрывы в навыках")
        st.caption("Количество сотрудников с разрывом до следующего грейда")
        if gaps:
            maximum = max(float(g.get("employee_count", 0)) for g in gaps) or 1
            for gap in sorted(gaps, key=lambda g: -g.get("employee_count", 0))[:8]:
                count = gap.get("employee_count", 0)
                html(f'<div class="cq-bar-row"><div class="cq-bar-title"><span>{e(gap.get("name", "Навык"))}</span><strong>{e(count)}</strong></div><div class="cq-bar"><i style="width:{100 * float(count) / maximum}%"></i></div></div>')
        else:
            empty_state("Разрывов не найдено", "По текущим данным нет неудовлетворённых требований следующего грейда.")
        with st.expander(f"Все разрывы по навыкам · {len(gaps)}"):
            st.dataframe([{"Навык": row["name"], "Сотрудников": row.get("employee_count", 0)} for row in gaps], hide_index=True, width="stretch")
    with right, st.container(border=True, key="hr_support"):
        st.subheader("Нужен индивидуальный план")
        st.caption("Список для поддержки сотрудника. Порядок — по имени.")
        if blocked:
            st.dataframe([{"Сотрудник": row.get("full_name", row.get("employee_id", "")), "Роль": row.get("role", ""),
                           "Грейд": row.get("grade", ""), "Причина": row.get("reason", "Нет подходящего следующего шага")}
                          for row in sorted(blocked, key=lambda r: r.get("full_name", ""))], hide_index=True, width="stretch", height=340)
        else:
            empty_state("Маршруты доступны", "Движок не выделил сотрудников, которым требуется индивидуальный следующий шаг.")
    st.subheader("Участие по активностям")
    st.caption("Количество записей истории, включая отказы и повторные участия. Завершения — записи со статусом «Завершено».")
    if participation:
        st.dataframe([{"Активность": row.get("title", row.get("event_id", "")),
                       "Записей участия": row.get("records", 0), "Завершений": row.get("completed", 0)} for row in participation], hide_index=True, width="stretch")
    else:
        empty_state("Участие ещё не зафиксировано", "Загрузите историю или завершите активность на экране сотрудника.")


def render_import(adapter, employees):
    page_heading("Добавьте данные для проверки", "Новые профили и история попадут в тот же движок и тот же список сотрудников.", "Данные жюри")
    left, right = st.columns([1.5, 1], gap="large")
    with left, st.container(border=True, key="import_panel"):
        st.subheader("Загрузка стартового формата")
        st.caption("Можно загрузить один файл или оба вместе. До 10 МБ на файл, кодировка UTF-8.")
        with st.form("jury_import", clear_on_submit=False):
            profiles = st.file_uploader("Профили сотрудников · JSON", type=["json"], key="employees_upload")
            history = st.file_uploader("История участия · CSV", type=["csv"], key="history_upload")
            submitted = st.form_submit_button("Импортировать данные", type="primary", width="stretch")
        if submitted:
            try:
                before_ids = {emp["employee_id"] for emp in employees}
                with st.spinner("Проверяем и импортируем данные…"):
                    updated = adapter.import_test_data(st.session_state.dataset,
                                                      profiles.getvalue() if profiles else None,
                                                      history.getvalue() if history else None)
                    imported_employees = adapter.list_employees(updated)
                new_ids = [emp["employee_id"] for emp in imported_employees if emp["employee_id"] not in before_ids]
                st.session_state.dataset = updated
                st.session_state.revision += 1
                st.session_state.views = {}
                if new_ids:
                    st.session_state.pending_employee = new_ids[0]
                st.session_state.flash = f"Импорт завершён. Новых сотрудников: {len(new_ids)}. История учтена движком. Перейдите в режим «Сотрудник»."
                st.rerun()
            except Exception as exc:
                show_error(exc, "импортировать данные")
    with right, st.container(border=True, key="import_format"):
        st.subheader("Формат файлов")
        st.markdown("**Профили:** исходный `employees.json` с массивом `employees` или массив объектов. У каждого профиля должен быть уникальный `employee_id`.")
        st.markdown("**История:** исходный `activity_history.csv`. Идентификаторы сотрудников и активностей должны существовать в датасете или в загружаемом файле.")
        st.caption("Структура и значения проверяются движком. Если импорт отклонён, текущая сессия сохраняет прежние данные.")
        if employees:
            source = deepcopy(employees[0])
            # Use the original starter profile (list_employees may return a summary).
            original = json.loads((DATA_DIR / "employees.json").read_text(encoding="utf-8-sig"))["employees"][0]
            source = deepcopy(original)
            source["employee_id"] = "JURY_001"
            source["full_name"] = "Demo Jury Profile"
            st.download_button("Скачать пример профиля", json.dumps({"employees": [source]}, ensure_ascii=False, indent=2),
                               file_name="jury_employees.example.json", mime="application/json", width="stretch")
    st.info("Изменения хранятся в сессии демонстрации. Переключение экранов сохраняет прогресс; новый сеанс браузера начинает с исходного датасета.")


def main():
    st.set_page_config(page_title="Career Quest · Halyk", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")
    html("<style>" + (ROOT / "styles/main.css").read_text(encoding="utf-8") + "</style>")
    try:
        adapter = CoreAdapter(DATA_DIR)
        if "dataset" not in st.session_state or st.session_state.get("backend_name") != adapter.backend_name:
            st.session_state.dataset = adapter.load_dataset()
            st.session_state.backend_name = adapter.backend_name
            st.session_state.revision = 0
            st.session_state.views = {}
        employees = adapter.list_employees(st.session_state.dataset)
    except Exception as exc:
        page_heading("Не удалось открыть данные", "Проверьте путь к стартовому киту и готовность core/api.py.")
        show_error(exc, "загрузить датасет")
        st.stop()
    with st.sidebar:
        html('<div class="cq-brand"><div class="cq-mark">cq</div><div><strong>Career Quest</strong><small>HALYK · РАЗВИТИЕ</small></div></div><div class="cq-rule"></div>')
        mode = st.radio("Демонстрационный режим", ["Сотрудник", "HR", "Импорт данных"], key="mode")
        st.caption("Переключение для показа MVP. Это не разграничение доступа.")
        html('<div class="cq-rule"></div>')
        choices = {emp["employee_id"]: emp for emp in employees}
        ids = list(choices)
        if not ids:
            st.warning("Нет сотрудников. Загрузите профили.")
            employee_id = None
        else:
            pending = st.session_state.pop("pending_employee", None)
            if pending in ids:
                st.session_state.employee_id = pending
            if st.session_state.get("employee_id") not in ids:
                st.session_state.employee_id = ids[0]
            employee_id = st.selectbox("Профиль сотрудника", ids,
                                       format_func=lambda eid: f'{choices[eid].get("full_name", eid)} · {eid}', key="employee_id")
            person = choices[employee_id]
            initials = "".join(part[0] for part in person.get("full_name", "CQ").split()[:2])
            html(f'<div class="cq-person"><div class="cq-avatar">{e(initials)}</div><strong>{e(person.get("full_name", employee_id))}</strong><p>{e(person.get("role", ""))}</p><span class="cq-pill">{e(person.get("grade", ""))}</span><span class="cq-pill">{e(person.get("tenure_months", "—"))} мес. в компании</span></div>')
        html('<p class="cq-sidebar-note">Рост начинается с понятного следующего шага.<br>Вы выбираете темп вместе с руководителем.</p>')
        if adapter.is_demo:
            st.warning("Предпросмотр UI: core/ ещё не подключён. Карточка E0001 — пример, AI не используется.")
        else:
            st.caption("● Подключён рекомендательный движок")
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))
    try:
        if mode == "Импорт данных":
            render_import(adapter, employees)
        elif mode == "HR":
            render_hr(adapter, employees)
        elif employee_id:
            render_employee(adapter, employee_id)
        else:
            page_heading("Начните с профиля", "Откройте «Данные жюри» и добавьте сотрудников.")
    except Exception as exc:
        show_error(exc, "построить представление")
    html('<div class="cq-footer"><span>Career Quest · HackAlem AI · 2026</span><span>Развитие — совместное решение сотрудника и руководителя</span></div>')


if __name__ == "__main__":
    main()
