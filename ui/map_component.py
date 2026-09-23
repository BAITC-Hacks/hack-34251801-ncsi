"""Interactive presentation of the persisted growth plan and approved facts.

The component only returns a selected node. All course decisions and requests
are handled by GrowthService through the containing page.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st


ASSETS = Path(__file__).with_name("map_frontend")


def _stable_id(prefix, value):
    return prefix + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:20]


def build_map_model(plan: dict, snapshot: dict) -> dict:
    """Join saved recommendations to confirmed facts without predicting levels."""
    nodes, edges, facts = [], [], {}
    labels = dict(snapshot.get("skill_labels", {}))
    for skill in snapshot.get("view", {}).get("skills", []):
        labels.setdefault(skill["skill_id"], skill.get("label", skill.get("name", skill["skill_id"])))
    for ref, level in sorted(snapshot.get("skills", {}).items()):
        if not isinstance(level, (float, int)) or isinstance(level, bool) or level <= 0:
            continue
        node_id = "skill:" + str(ref)
        facts[str(ref)] = node_id
        nodes.append({"id": node_id, "kind": "skill", "label": str(labels.get(ref, ref)),
                      "subtitle": f"Подтверждено · {level:g}/5", "ref": str(ref),
                      "payload": {"skill_id": ref, "level": level, "name": labels.get(ref, ref)}})
    for certificate in snapshot.get("certificates", []):
        if certificate.get("status") != "approved":
            continue
        ref = str(certificate["id"])
        node_id = "certificate:" + ref
        facts[ref] = node_id
        payload = certificate.get("payload", {})
        nodes.append({"id": node_id, "kind": "certificate", "label": str(payload.get("title", "Сертификат")),
                      "subtitle": "Сертификат · подтверждён HR", "ref": ref, "payload": dict(certificate)})

    plan_id = str(plan.get("plan_id") or plan.get("id") or "")
    for track_index, track in enumerate(plan.get("tracks", [])):
        track_id = str(track.get("id") or f"{plan_id}:track:{track_index}")
        node_id = "track:" + track_id
        nodes.append({"id": node_id, "kind": "track", "label": str(track.get("title", "Направление")),
                      "subtitle": "Направление развития", "track_id": track_id,
                      "payload": dict(track)})
        for ref in dict.fromkeys(track.get("basis_refs", [])):
            if str(ref) in facts:
                edges.append({"source": facts[str(ref)], "target": node_id, "kind": "basis"})
        for index, skill in enumerate(track.get("next_skills", [])):
            label = skill.get("name", skill.get("title", "Навык")) if isinstance(skill, dict) else str(skill)
            future_id = _stable_id("future:", f"{track_id}:{index}:{label}")
            nodes.append({"id": future_id, "kind": "future_skill", "label": str(label),
                          "subtitle": "Навык · предложение", "track_id": track_id,
                          "parent_id": node_id, "payload": {"name": str(label), "suggested": True}})
            edges.append({"source": node_id, "target": future_id, "kind": "suggestion"})
        for index, course in enumerate(track.get("courses", [])):
            if course.get("hidden"):
                continue
            course_id = str(course.get("id") or _stable_id("course-", course.get("url", f"{track_id}:{index}")))
            # A course can be suggested in more than one direction. Its backend
            # ID remains unchanged; the map node identifies this occurrence.
            course_node = _stable_id("course:", f"{track_id}:{course_id}")
            requested = bool(course.get("request_id"))
            nodes.append({"id": course_node, "kind": "course", "label": str(course.get("title", "Курс")),
                          "subtitle": "Курс · в маршруте" if requested else "Курс · вариант обучения",
                          "track_id": track_id, "course_id": course_id, "parent_id": node_id,
                          "payload": dict(course)})
            edges.append({"source": node_id, "target": course_node, "kind": "suggestion"})

    # Put the facts used by this plan first without changing their levels.
    used = {edge["source"] for edge in edges if edge["kind"] == "basis"}
    nodes.sort(key=lambda node: node["kind"] in {"skill", "certificate"} and node["id"] not in used)
    return {"nodes": nodes, "edges": edges, "plan_id": plan_id}


@st.cache_resource
def _component():
    return st.components.v2.component(
        "career_growth_map",
        html=(ASSETS / "map.html").read_text(encoding="utf-8"),
        css=(ASSETS / "map.css").read_text(encoding="utf-8"),
        js=(ASSETS / "map.js").read_text(encoding="utf-8"),
        isolate_styles=True,
    )


def render_interactive_map(model: dict, key: str) -> dict | None:
    """Return the selected node; keep navigation state across page unmounts.

    Use a stable key per employee, such as ``growth-map-E0001``. This is a
    presentation component: it never initiates research or awards progress.
    """
    saved_key = "_saved_map_view_" + key
    nodes = {node["id"]: node for node in model.get("nodes", [])}
    default_id = next((node["id"] for node in nodes.values() if node["kind"] == "track"), next(iter(nodes), None))
    saved = dict(st.session_state.get(saved_key, {}))
    if saved.get("selected_id") not in nodes:
        saved["selected_id"] = default_id
    saved.setdefault("viewport", None)
    saved["collapsed"] = [value for value in saved.get("collapsed", []) if value in nodes]

    def remember():
        view = st.session_state.get(key, {}).get("view")
        if isinstance(view, dict):
            st.session_state[saved_key] = view

    result = _component()(
        data={**model, "view": saved}, key=key, default={"view": saved},
        on_view_change=remember, width="stretch", height="content",
    )
    view = result.get("view") or saved
    if view.get("selected_id") not in nodes:
        view = saved
    st.session_state[saved_key] = view
    return nodes.get(view.get("selected_id"))
