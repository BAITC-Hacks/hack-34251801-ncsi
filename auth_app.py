"""Standalone account page: python -m streamlit run auth_app.py --server.port 8503."""

import streamlit as st

from auth.ui import render_account, render_auth, setup_page
from storage.config import configure_storage

configure_storage()

st.set_page_config(page_title="Вход · Career Quest", page_icon="🌱", layout="wide")
setup_page()
user = render_auth()
if user:
    render_account(user)
