"""Drive the real demo-entry widgets; never manufacture an authenticated identity."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch


def isolate_demo_storage(test, growth_path=None):
    """Keep growth fixtures temporary and fail if demo entry constructs AuthService."""
    directory = tempfile.TemporaryDirectory()
    test.addCleanup(directory.cleanup)
    folder = Path(directory.name)
    auth_path = folder / "auth-must-not-exist" / "auth.sqlite3"
    environment = patch.dict(os.environ, {
        "CAREER_QUEST_DEMO_MODE": "1",
        "CAREER_QUEST_AUTH_DB": str(auth_path),
        "CAREER_QUEST_GROWTH_DB": str(growth_path or folder / "growth.sqlite3"),
        "CAREER_QUEST_AI_PROVIDER": "none", "OPENAI_API_KEY": "", "NVIDIA_API_KEY": "",
    })
    environment.start()
    test.addCleanup(environment.stop)
    auth_constructor = patch("auth.service.AuthService.__init__",
                             side_effect=AssertionError("Demo entry must not construct AuthService"))
    auth_constructor.start()
    test.addCleanup(auth_constructor.stop)
    return auth_path


def assert_rendered(app):
    if app.exception:
        raise AssertionError("Streamlit exception: " + str([item.value for item in app.exception]))
    if app.error:
        raise AssertionError("Streamlit error: " + str([item.value for item in app.error]))
    return app


def demo_login(app, role="employee", employee_id="E0001"):
    assert_rendered(app)
    group = next(widget for widget in app.get("button_group") if widget.key == "cq_demo_role")
    group.set_value(role).run()
    assert_rendered(app)
    if role == "employee":
        app.selectbox(key="cq_demo_employee").select(employee_id).run()
        assert_rendered(app)
    app.button(key="cq_demo_enter").click().run()
    return assert_rendered(app)


def demo_logout(app):
    app.button(key="cq_demo_logout").click().run()
    return assert_rendered(app)


def switch_demo_role(app, role="employee", employee_id="E0001"):
    identity = app.session_state["cq_demo_identity"] if "cq_demo_identity" in app.session_state else {}
    if identity.get("role") == role and (role != "employee" or identity.get("employee_id") == employee_id):
        return app
    if any(button.key == "cq_demo_logout" for button in app.button):
        demo_logout(app)
    return demo_login(app, role, employee_id)


def employee_tab(app, label):
    # AppTest does not serialize stateful tab selection between reruns yet.
    app.session_state["employee_tab"] = label
    return assert_rendered(app.run())


def hr_tab(app, label):
    app.session_state["hr_tab"] = label
    return assert_rendered(app.run())
