"""Small escaped presentation components; no recommendations or AI calls here."""

from html import escape

import streamlit as st

FORMATS = {"online": "Онлайн", "offline": "Очно", "self_paced": "В своём темпе"}
EVENT_TYPES = {"course": "Курс", "workshop": "Воркшоп", "mentoring": "Менторство", "certification": "Сертификация", "meetup": "Встреча", "compliance": "Обязательное обучение", "onboarding": "Онбординг"}
STATUSES = {"completed": "Завершено", "in_progress": "В процессе", "dropped": "Прервано", "no_show": "Неявка", "declined": "Отказ", "overdue": "Просрочено"}


def e(value):
    return escape(str(value if value is not None else ""), quote=True)


def html(value):
    st.html(value)


def number(value):
    return f"{float(value):g}" if isinstance(value, (int, float)) else str(value)


def page_heading(title, subtitle, tag="Пространство развития"):
    if st.session_state.get("backend_name") == "demo":
        tag = "Предпросмотр UI · core ещё не подключён"
    html(f'<div class="cq-page-top"><span class="cq-tag">{e(tag)}</span><span>Срез данных · 01 октября 2026</span></div>')
    st.title(title)
    html(f'<p class="cq-subtitle">{e(subtitle)}</p>')


def journey(view):
    employee = view["employee"]
    progress = min(100, max(0, float(view["trajectory"]["progress_pct"])))
    gaps = view["trajectory"]["gap_count"]
    target = view.get("next_grade") or "Экспертиза"
    target_label = "Следующий грейд" if view.get("next_grade") else "Дальнейшее развитие"
    html(f'''<div class="cq-journey">
        <div><small>Сейчас</small><strong>{e(employee.get('grade'))}</strong></div>
        <div class="cq-bridge"><div class="cq-bridge-line">→</div>{e(gaps)} навыков до цели</div>
        <div><small>{target_label}</small><strong class="cq-target">{e(target)}</strong></div>
        <div class="cq-progress"><strong>{number(progress)}%</strong><small>требований по навыкам выполнено</small>
        <div class="cq-progress-track"><i style="width:{progress}%"></i></div></div></div>''')


def empty_state(title, text):
    html(f'<div class="cq-empty"><div class="cq-empty-symbol">↗</div><h3>{e(title)}</h3><p>{e(text)}</p></div>')


def recommendation_content(rec, best=False):
    pieces = []
    add = pieces.append
    label = "Рекомендуемый следующий шаг" if best else "Ещё одна возможность"
    kind = EVENT_TYPES.get(rec.get("type"), rec.get("type", "Развитие"))
    add(f'<div class="cq-rec-label"><span class="cq-tag">{label}</span><span class="cq-pill">{e(kind)}</span></div>')
    add(f'<div class="cq-event-title">{e(rec["title"])}</div>')
    meta = [FORMATS.get(rec.get("format"), rec.get("format", ""))]
    if rec.get("duration_hours"):
        meta.append(f'{number(rec["duration_hours"])} ч')
    sessions = [d for d in rec.get("upcoming_sessions", []) if d >= "2026-10-01"]
    if sessions:
        meta.append(f'Ближайшая дата · {min(sessions)}')
    add('<div class="cq-meta">' + ''.join(f'<span>{e(m)}</span>' for m in meta if m) + '</div>')
    explanation = rec.get("display_explanation")
    if explanation:
        source = rec.get("display_explanation_source", "rules")
        source_label = "Персональное объяснение AI" if source == "ai" else "Объяснение на основе данных"
        if source == "demo":
            source_label = "Пример объяснения · временный режим"
        add(f'<div class="cq-explanation"><b>{source_label}</b><p>{e(explanation)}</p></div>')
    if rec.get("ai_fallback"):
        add('<p class="cq-help">AI-объяснение недоступно. Показано объяснение движка на основе данных.</p>')
    factors = rec.get("display_factors") or rec.get("reasons", [])
    if factors:
        add('<div class="cq-small-label">Факторы из данных</div><div class="cq-factors">' + ''.join(
            f'<div class="cq-factor"><i>✓</i><span>{e(reason)}</span></div>' for reason in factors) + '</div>')
    gains = rec.get("skill_changes", [])
    if gains:
        add('<div class="cq-small-label">Ожидаемый прирост навыков</div><div class="cq-gains">' + ''.join(
            f'<div class="cq-gain"><span>{e(c["name"])} · {e(number(c["before"]))} → {e(number(c["after"]))}</span><strong>+{e(number(c["gain"]))}</strong></div>'
            for c in gains) + '</div>')
    html("".join(pieces))


def skill_card(skill):
    percent = min(100, max(0, 100 * skill["current"] / (skill["required"] or 1)))
    html(f'''<div class="cq-skill"><div class="cq-skill-head"><b>{e(skill['name'])}</b>
        <span>{e(number(skill['current']))} / {e(number(skill['required']))}</span></div>
        {'<div class="cq-critical">Ключевой навык для следующего грейда</div>' if skill['critical'] else ''}
        <div class="cq-progress-track"><i style="width:{percent}%"></i></div></div>''')


def stat(label, value, detail):
    html(f'<div class="cq-stat"><span>{e(label)}</span><strong>{e(value)}</strong><small>{e(detail)}</small></div>')
