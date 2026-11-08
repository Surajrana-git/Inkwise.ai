"""INKWISE AI - Streamlit entry point. Owner: Aashi (Frontend).
Run from the repo root:  streamlit run app/Home.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make `engine` importable

import streamlit as st

from engine.bootstrap import startup
from engine.workflow import ROLES

st.set_page_config(page_title="INKWISE AI", page_icon="🖋️", layout="wide")


@st.cache_resource(show_spinner="Loading brand kit…")
def get_state():
    return startup()  # DB tables + knowledge index, once per server process


state = get_state()
if state.using_sample_kit:
    st.warning("Using the small sample brand kit. Add data/brand_kit/*.json to load Lumora.")

st.title("INKWISE AI")
st.caption("Brand governance before you publish: every finding cites its source.")

st.info(
    "AI disclosure: content you submit is reviewed by Google Gemini after personal data "
    "is masked. This demo uses synthetic data only. Humans make every final decision.",
    icon="ℹ️",
)

with st.sidebar:
    st.subheader("Sign in (demo)")
    name = st.text_input("Name", value=st.session_state.get("user", ""))
    role = st.selectbox("Role", ROLES, index=ROLES.index(st.session_state.get("role", "creator")))
    if st.button("Continue", type="primary"):
        st.session_state["user"] = name or "demo-user"
        st.session_state["role"] = role
        st.success(f"Signed in as {st.session_state['user']} ({role})")

st.markdown(
    """
**How it works**
1. Paste or upload content on the **Review** page.
2. INKWISE checks it against the brand kit: guidelines, approved facts (with expiry dates) and terminology.
3. Each finding shows the exact text, the source it relates to, why it matters and a suggested fix.
4. A manager approves or requests changes; every decision is saved in **History**.
"""
)
