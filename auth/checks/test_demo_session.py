"""Demo routing preserves learning state and never uses the account database."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from auth import demo_session

EMPLOYEES = [
    {"employee_id": "E0001", "full_name": "Demo Employee One", "role": "Engineer", "grade": "Junior"},
    {"employee_id": "E0002", "full_name": "Demo Employee Two", "role": "Analyst", "grade": "Middle"},
]


class DemoSessionTests(unittest.TestCase):
    def setUp(self):
        self.state = {"dataset": {"employees": EMPLOYEES}, "growth_store": {"certificate": "pending"},
                      "revision": 3, "views": {"cached": True}, "flash": "previous user"}
        self.patch = patch.object(demo_session.st, "session_state", self.state)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_employee_then_hr_then_employee_preserves_progress(self):
        identity = demo_session.start_demo_session("employee", "E0002", EMPLOYEES)
        self.assertEqual(identity["name"], "Demo Employee Two")
        self.assertEqual(identity["employee_id"], "E0002")
        self.assertEqual(self.state["views"], {})
        self.assertNotIn("flash", self.state)
        demo_session.end_demo_session()
        hr = demo_session.start_demo_session("hr", None, EMPLOYEES)
        self.assertNotIn("employee_id", hr)
        self.state["growth_store"]["certificate"] = "approved"
        demo_session.end_demo_session()
        demo_session.start_demo_session("employee", "E0002", EMPLOYEES)
        self.assertEqual(self.state["growth_store"]["certificate"], "approved")
        self.assertEqual(self.state["revision"], 3)
        self.assertEqual(self.state["dataset"]["employees"], EMPLOYEES)

    def test_invalid_profile_or_role_does_not_create_identity(self):
        for role, identifier in [("owner", None), ("employee", None), ("employee", "missing")]:
            with self.subTest(role=role, identifier=identifier), self.assertRaises(ValueError):
                demo_session.start_demo_session(role, identifier, EMPLOYEES)
        self.assertIsNone(demo_session.get_demo_identity(EMPLOYEES))

    def test_removed_employee_invalidates_identity_without_losing_dataset(self):
        demo_session.start_demo_session("employee", "E0001", EMPLOYEES)
        self.assertIsNone(demo_session.get_demo_identity([EMPLOYEES[1]]))
        self.assertIn("dataset", self.state)
        self.assertIn("growth_store", self.state)

    def test_read_refreshes_profile_labels_and_ignores_copied_name(self):
        demo_session.start_demo_session("employee", "E0001", EMPLOYEES)
        self.state["cq_demo_identity"]["name"] = "stale copied name"
        current = demo_session.get_demo_identity(EMPLOYEES)
        self.assertEqual(current["name"], "Demo Employee One")
        current["role"] = "admin"
        self.assertEqual(self.state["cq_demo_identity"]["role"], "employee")

    def test_admin_identity_does_not_inherit_employee_id(self):
        identity = demo_session.start_demo_session("admin", "E0001", EMPLOYEES)
        self.assertNotIn("employee_id", identity)
        self.assertEqual(identity["role"], "admin")


class DemoLoginUITests(unittest.TestCase):
    def test_real_role_widgets_without_account_database(self):
        script = '''
import streamlit as st
from auth.demo_ui import render_demo_login
from auth.demo_session import get_demo_identity, end_demo_session
employees = %r
identity = get_demo_identity(employees)
if not identity:
    render_demo_login(employees)
    st.stop()
st.write(identity["role"])
if st.button("Выйти", key="cq_demo_logout"):
    end_demo_session()
    st.rerun()
''' % EMPLOYEES
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {"CAREER_QUEST_AUTH_DB": str(Path(directory) / "must-not-exist.sqlite3")}), \
             patch("auth.ui.AuthService", side_effect=AssertionError("Demo must never create AuthService")):
            app = AppTest.from_string(script).run()
            self.assertEqual(len(app.exception), 0)
            for role in ["employee", "hr", "admin"]:
                selector = next(group for group in app.get("button_group") if group.key == "cq_demo_role")
                selector.set_value(role).run()
                if role == "employee":
                    app.selectbox(key="cq_demo_employee").set_value("E0002").run()
                app.button(key="cq_demo_enter").click().run()
                self.assertEqual(len(app.exception), 0)
                identity = app.session_state["cq_demo_identity"]
                self.assertEqual(identity["role"], role)
                if role == "employee":
                    self.assertEqual(identity["employee_id"], "E0002")
                app.button(key="cq_demo_logout").click().run()
            self.assertFalse((Path(directory) / "must-not-exist.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
