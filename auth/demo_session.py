"""Browser-session-only identities for the openly labelled demonstration mode.

These helpers are presentation routing, not authentication or authorization.
They never open an account database, and preserve dataset/growth state while
switching between an employee and HR in the same Streamlit browser session.
"""

from __future__ import annotations

import streamlit as st

DEMO_IDENTITY_KEY = "cq_demo_identity"
DEMO_ROLES = frozenset({"employee", "hr", "admin"})


def _identity(role: str, employee_id: str | None, employees: list[dict]) -> dict:
    if not isinstance(role, str) or role not in DEMO_ROLES:
        raise ValueError("Выберите роль: сотрудник, HR или администратор.")
    if role == "employee":
        person = next((person for person in employees if person.get("employee_id") == employee_id), None)
        if person is None or not employee_id:
            raise ValueError("Выберите существующий профиль сотрудника из списка.")
        return {
            "role": "employee", "employee_id": employee_id,
            "name": person.get("full_name") or person.get("name") or employee_id,
            "job_role": person.get("role", ""), "grade": person.get("grade", ""),
            "demo": True,
        }
    return {
        "role": role,
        "name": "HR · деморежим" if role == "hr" else "Администратор · деморежим",
        "demo": True,
    }


def _clear_view_cache() -> None:
    st.session_state["views"] = {}
    st.session_state.pop("flash", None)


def get_demo_identity(employees: list[dict]) -> dict | None:
    """Read and revalidate a demo role/profile against the current dataset."""
    saved = st.session_state.get(DEMO_IDENTITY_KEY)
    if saved is None:
        return None
    if not isinstance(saved, dict):
        end_demo_session()
        return None
    try:
        current = _identity(saved.get("role"), saved.get("employee_id"), employees)
    except ValueError:
        end_demo_session()
        return None
    # Rebuild labels from the dataset instead of trusting stale session copies.
    st.session_state[DEMO_IDENTITY_KEY] = current
    return dict(current)


def start_demo_session(role: str, employee_id: str | None, employees: list[dict]) -> dict:
    """Select a demonstration role; only employees need an existing profile ID."""
    identity = _identity(role, employee_id, employees)
    _clear_view_cache()
    st.session_state[DEMO_IDENTITY_KEY] = identity
    return dict(identity)


def end_demo_session() -> None:
    """Clear the routing identity, keeping in-session learning and HR changes."""
    for key in list(st.session_state):
        if key.startswith("cq_demo_"):
            st.session_state.pop(key, None)
    _clear_view_cache()
