"""Read-only development map. Every level is supplied by core, never awarded here."""

from __future__ import annotations

from pathlib import Path
from textwrap import wrap

import streamlit as st

from ui.components import e, empty_state, html, number


CATEGORIES = {
    "engineering": "Разработка", "frontend": "Фронтенд", "data": "Данные",
    "product": "Продукт", "hr": "HR", "sales": "Продажи", "quality": "Качество",
    "support": "Поддержка", "communication": "Коммуникация", "leadership": "Лидерство",
    "collaboration": "Сотрудничество", "thinking": "Мышление",
    "personal_effectiveness": "Личная эффективность",
}


def branch_label(skill, catalog):
    meta = catalog.get(skill["skill_id"], {})
    category = meta.get("category")
    kind = meta.get("type")
    if category:
        return f'{CATEGORIES.get(category, category)} · {kind}' if kind else str(category)
    return {"hard": "Профессиональные · hard", "soft": "Надпрофессиональные · soft"}.get(kind, "Без категории")


def build_map_model(view, catalog, events, selected_skill_id=None, selected_event_id=None,
                    expanded=False, completion=None):
    """Join facts for presentation; no eligibility, scoring or level calculation."""
    skills = [dict(s) for s in view.get("skills", [])]
    recs = {r["event_id"]: r for r in view.get("recommendations", [])}
    done_id = (completion or {}).get("event_id")
    choices = list(recs)
    if done_id and done_id in events and done_id not in choices:
        choices.append(done_id)
    event_id = selected_event_id if selected_event_id in choices else next(iter(choices), None)
    event = events.get(event_id)
    completed = bool(event_id and event_id == done_id)
    changes = {}
    if completed:
        # Both snapshots were obtained by querying core before/after completion.
        changes = {sid: {"before": before, "after": completion["after"][sid]}
                   for sid, before in completion["before"].items() if sid in completion["after"]}
    elif event_id in recs:
        changes = {c["skill_id"]: c for c in recs[event_id].get("skill_changes", [])}
    develops = {d["skill_id"]: d for d in (event or {}).get("develops_skills", [])}
    prerequisites = (event or {}).get("prerequisites", {})
    # Display priority only. Recommendation order and core output are not changed.
    skills.sort(key=lambda s: (s["skill_id"] not in develops, s.get("gap", 0) <= 0,
                               not s.get("critical", False), -s.get("gap", 0)))
    selected = next((s for s in skills if s["skill_id"] == selected_skill_id), next(iter(skills), None))
    visible = skills if expanded else skills[:5]
    if selected and selected not in visible:
        visible = visible[:4] + [selected]
    for skill in visible:
        skill["branch"] = branch_label(skill, catalog)
    visible.sort(key=lambda s: (s["branch"], s["skill_id"] != (selected or {}).get("skill_id", "")))
    edges = []
    for skill in visible:
        sid = skill["skill_id"]
        if sid in develops:
            edges.append({"skill_id": sid, "event_id": event_id, "kind": "develops",
                          "gain": develops[sid]["gain"], "max_level": develops[sid]["max_level"]})
        if sid in prerequisites:
            edges.append({"skill_id": sid, "event_id": event_id, "kind": "prerequisite",
                          "required": prerequisites[sid]})
    return {"skills": visible, "all_skills": skills, "selected_skill": selected,
            "event": event, "event_id": event_id, "choices": choices, "completed": completed,
            "changes": changes, "edges": edges, "recommendation": recs.get(event_id),
            "target": view.get("next_grade"), "total": len(skills)}


def _svg_text(text, x, y, width=29, css="cq-map-name", max_lines=2):
    lines = wrap(str(text), width=width, break_long_words=True) or [""]
    shown = lines[:max_lines]
    if len(lines) > max_lines:
        shown[-1] = shown[-1].rstrip(" .") + "…"
    return f'<text x="{x}" y="{y}" class="{css}">' + "".join(
        f'<tspan x="{x}" dy="{0 if i == 0 else 17}">{e(line)}</tspan>' for i, line in enumerate(shown)) + '</text>'


def map_svg(model):
    """A small accessible SVG; grouping is a backdrop, never an invented edge."""
    skills = model["skills"]
    height = max(260, 56 + len(skills) * 96)
    cy = height / 2
    event = model["event"]
    chosen = (model["selected_skill"] or {}).get("skill_id")
    out = [f'<svg class="cq-map-svg" viewBox="0 0 1000 {height}" role="img" aria-label="Карта развития: навыки, активность и результат. Выбор через списки над картой." xmlns="http://www.w3.org/2000/svg">',
           '<style>' + '\n'.join(line for line in (Path(__file__).resolve().parents[1] / "styles/main.css").read_text(encoding="utf-8").splitlines() if line.startswith(".cq-map-")) + '</style>',
           '<text x="20" y="23" class="cq-map-column">НАВЫКИ СЕЙЧАС · ИЗ 5</text>',
           '<text x="382" y="23" class="cq-map-column">ВЫБРАННЫЙ ШАГ</text>',
           f'<text x="742" y="23" class="cq-map-column">{"РЕЗУЛЬТАТ" if model["completed"] else "ПРОГНОЗ"} · ЦЕЛЬ {e(model["target"] or "ТЕКУЩЕГО ГРЕЙДА")}</text>']
    edges = {(ed["skill_id"], ed["kind"]): ed for ed in model["edges"]}
    for index, skill in enumerate(skills):
        sid = skill["skill_id"]
        y = 43 + index * 96
        center = y + 46
        focus = sid == chosen
        develop = edges.get((sid, "develops"))
        prereq = edges.get((sid, "prerequisite"))
        change = model["changes"].get(sid) if develop else None
        if develop:
            cls = "cq-map-link cq-map-link-active" if focus else "cq-map-link"
            out.append(f'<path class="{cls}" d="M280 {center} C328 {center},330 {cy},380 {cy}"/>')
            if change:
                out.append(f'<path class="{cls}" d="M630 {cy} C690 {cy},685 {center},735 {center}"/>')
        if prereq:
            out.append(f'<path class="cq-map-prerequisite" d="M280 {center+9} C338 {center+9},329 {cy+12},380 {cy+12}"><title>Условие допуска: уровень ≥ {e(prereq["required"])}</title></path>')
        state = "есть разрыв" if skill.get("gap", 0) > 0 else "освоено"
        color = "gap" if skill.get("gap", 0) > 0 else "mastered"
        out.append(f'<g class="cq-map-node {color}{" selected" if focus else ""}"><title>{e(skill["name"])} · {e(skill["branch"])} · {e(state)}</title><rect x="14" y="{y}" width="266" height="86" rx="12"/>')
        out.append(_svg_text(skill["branch"], 28, y+16, 39, "cq-map-branch", 1))
        out.append(_svg_text(skill["name"], 28, y+35, 29))
        out.append(f'<text x="28" y="{y+74}" class="cq-map-level">{e(number(skill["current"]))}/5 · {state} · цель {e(number(skill["required"]))}</text></g>')
        if change:
            label = "Получено" if model["completed"] else "Ожидается"
            out.append(f'<g class="cq-map-result{" selected" if focus else ""}"><rect x="735" y="{y+7}" width="248" height="72" rx="12"/>')
            out.append(f'<text x="751" y="{y+30}" class="cq-map-level">{label}: {e(number(change["after"]))}/5</text>')
            out.append(f'<text x="751" y="{y+49}" class="cq-map-detail">{e(number(change["before"]))} → {e(number(change["after"]))} · требование {e(number(skill["required"]))}/5</text>')
            out.append(f'<text x="751" y="{y+67}" class="cq-map-detail">gain +{e(number(develop["gain"]))} · max_level {e(number(develop["max_level"]))}</text></g>')
    if event:
        state = "✓ Активность завершена" if model["completed"] else "↗ Рекомендовано"
        out.append(f'<g class="cq-map-event{" completed" if model["completed"] else ""}"><title>{e(event["title"])}</title><rect x="380" y="{cy-80}" width="250" height="160" rx="18"/>')
        out.append(f'<text x="398" y="{cy-53}" class="cq-map-event-status">{state}</text>')
        out.append(_svg_text(event["title"], 398, cy-25, 25, "cq-map-event-name", 4))
        out.append(f'<text x="398" y="{cy+58}" class="cq-map-event-meta">{e(event["event_id"])} · {e(number(event.get("duration_hours", "—")))} ч</text></g>')
        if not model["edges"]:
            out.append(_svg_text("Нет связей с навыками этой цели", 376, cy+107, 32, "cq-map-detail", 2))
    else:
        out.append(_svg_text("Нет рекомендованного шага", 382, cy, 26, "cq-map-name", 2))
    out.append('</svg>')
    return ''.join(out)


def render_development_map(adapter, view, on_complete):
    employee_id = view["employee"]["employee_id"]
    completion = st.session_state.get("map_completions", {}).get(employee_id)
    if not view.get("skills"):
        empty_state("Навыки для карты не заданы", "В ответе движка нет требований для этой цели.")
        return
    skill_key, event_key = f"map-skill-{employee_id}", f"map-event-{employee_id}"
    seed = build_map_model(view, adapter.catalog, adapter.events,
                           st.session_state.get(skill_key), st.session_state.get(event_key), completion=completion)
    st.caption("Выберите навык и шаг: карта подсветит связь и покажет результат до следующего грейда.")
    a, b = st.columns([1, 1.35])
    with b:
        if seed["choices"]:
            if st.session_state.get(event_key) not in seed["choices"]:
                st.session_state[event_key] = seed["event_id"]
            event_id = st.selectbox("Шаг на карте", seed["choices"], key=event_key,
                format_func=lambda eid: adapter.events[eid]["title"])
        else:
            event_id = None
            st.info("Нет рекомендаций. Изучите разрывы и обсудите шаг с руководителем.")
    seed = build_map_model(view, adapter.catalog, adapter.events, st.session_state.get(skill_key), event_id, completion=completion)
    previous_event_key = f"map-previous-event-{employee_id}"
    if st.session_state.get(previous_event_key) != event_id:
        linked = {edge["skill_id"] for edge in seed["edges"] if edge["kind"] == "develops"}
        first_linked = next((s["skill_id"] for s in seed["all_skills"] if s["skill_id"] in linked), None)
        if first_linked:
            st.session_state[skill_key] = first_linked
        st.session_state[previous_event_key] = event_id
    with a:
        skill_choices = {s["skill_id"]: s for s in seed["all_skills"]}
        if st.session_state.get(skill_key) not in skill_choices:
            st.session_state[skill_key] = seed["selected_skill"]["skill_id"]
        sid = st.selectbox("Навык на карте", list(skill_choices), key=skill_key,
                          format_func=lambda sid: skill_choices[sid]["name"])
    expanded = st.checkbox(f'Показать все навыки цели ({seed["total"]})', key=f"map-all-{employee_id}") if seed["total"] > 5 else False
    model = build_map_model(view, adapter.catalog, adapter.events, sid, event_id, expanded, completion)
    # Streamlit's image component supports SVG; st.html strips inline SVG.
    # Interaction stays in accessible native controls above the image.
    with st.container(border=True, key="development_map_canvas"):
        st.image(map_svg(model), width="stretch")
    html('<div class="cq-map-legend"><span class="gap">● Есть разрыв</span><span class="mastered">✓ Освоено: требование выполнено</span><span class="recommended">↗ Рекомендовано</span><span class="completed">✓ Активность завершена</span></div>')
    st.caption("Ветки — category/type из skills.json; русские подписи — перевод категорий. Линия — develops_skills, пунктир — prerequisites из events.json. Между навыками обязательных зависимостей нет. Справа — уровень из ответа движка и требование грейда.")
    skill = model["selected_skill"]
    left, right = st.columns([1, 1.15], gap="large")
    with left, st.container(border=True):
        st.subheader(skill["name"])
        target = f'для {view["next_grade"]}' if view.get("next_grade") else "для текущего грейда (следующего нет)"
        st.write(f'Сейчас **{number(skill["current"])}/5** · Требуется **{number(skill["required"])}/5** {target}.')
        st.caption(("Ключевой навык" if skill.get("critical") else "Навык") + f' входит в требования профиля {view["employee"].get("role", "")} {target}.')
        description = adapter.catalog.get(sid, {}).get("description")
        if description:
            st.caption(description)
        if skill.get("gap", 0) > 0:
            st.write(f'Есть разрыв: **{number(skill["gap"])}**. Выберите подходящий шаг из рекомендаций движка.')
        else:
            html('<div class="cq-map-status">✓ Освоено: требование по этому навыку выполнено.</div>')
    with right, st.container(border=True):
        rec = model["recommendation"]
        event = model["event"]
        if event:
            st.subheader(event["title"])
            change = model["changes"].get(sid) if any(x["skill_id"] == sid and x["kind"] == "develops" for x in model["edges"]) else None
            if change:
                st.write(f'{"Фактический результат" if model["completed"] else "Прогноз движка"}: **{number(change["before"])} → {number(change["after"])}/5** · требование **{number(skill["required"])}/5**.')
            else:
                st.caption("Этот шаг не меняет выбранный навык. Выберите связанный узел через список.")
            if model["completed"]:
                html('<div class="cq-map-status completed">✓ Активность завершена. Профиль, рекомендации и карта обновлены.</div>')
            elif rec:
                for reason in rec.get("reasons", [])[:3]:
                    st.caption(reason)
                if st.button("Завершить шаг на карте", key=f"map-complete-{employee_id}-{event_id}", type="primary", width="stretch"):
                    on_complete(rec)
        else:
            st.caption("Для завершения нужен шаг, рекомендованный движком.")
    related = [event for event in adapter.events.values() if any(d["skill_id"] == sid for d in event.get("develops_skills", []))]
    with st.expander(f"Активности для навыка · {len(related)}"):
        st.caption("Доступный следующий шаг подтверждают рекомендации. Остальные строки — связи каталога, а не подтверждение допуска. gain — величина из каталога; фактический прирост может быть меньше из-за max_level. Прогноз рассчитывает движок.")
        recs = {r["event_id"]: r for r in view.get("recommendations", [])}
        completed_ids = {r["event_id"] for r in view.get("history", []) if r.get("status") == "completed"}
        rows = []
        for event in related:
            change = next((c for c in recs.get(event["event_id"], {}).get("skill_changes", []) if c["skill_id"] == sid), None)
            develop = next(d for d in event["develops_skills"] if d["skill_id"] == sid)
            status = "Рекомендовано" if event["event_id"] in recs else "Активность завершена" if event["event_id"] in completed_ids else "В каталоге"
            rows.append({"Активность": event["title"], "Статус": status, "gain": develop["gain"], "max_level": develop["max_level"],
                         "Прогноз движка": f'{number(change["before"])} → {number(change["after"])}' if change else "—",
                         "Условия допуска": "; ".join(f'{adapter.skill_name(k)} ≥ {number(v)}' for k, v in event.get("prerequisites", {}).items()) or "Нет условий по навыкам"})
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.info("В каталоге нет активности, развивающей этот навык. Нужен индивидуальный план.")
