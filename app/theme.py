"""Shared INKWISE look & feel. Every page calls render_shell() once at the top."""
import base64
from pathlib import Path

import streamlit as st

import services

# ---- Switch this to True once engine/workflow.py has authenticate() ----
REQUIRE_LOGIN = False

APP_DIR = Path(__file__).resolve().parent   # .../app
ROOT = APP_DIR.parent                        # repo root

# Colours sampled from the logo
NAVY = "#1B2A4E"
TEAL = "#12917F"
TEAL_SOFT = "#E3F3F0"
BG = "#F4F6FA"
INK = "#1B2A4E"
MUTED = "#6B7690"
LINE = "#E2E7F0"

LOGO_CANDIDATES = [
    APP_DIR / "inkwise_logo.jpeg",
    ROOT / "assets" / "inkwise_logo.jpeg",
    ROOT / "inkwise_logo.jpeg",
]

ROLES = ["Creator", "Manager", "Reviewer", "Admin"]


def logo_src() -> str:
    """Return the logo as a data-URI so it can be placed in any HTML block."""
    for p in LOGO_CANDIDATES:
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            return f"data:image/jpeg;base64,{b64}"
    return ""  # logo missing: pages still render


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp {{ font-family: 'Inter', sans-serif; color: {INK}; }}
.stApp {{ background: {BG}; }}
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.2rem; max-width: 1180px; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: {NAVY}; }}
[data-testid="stSidebar"] * {{ color: #DCE3F2; }}
[data-testid="stSidebarNav"] a {{ border-radius: 10px; padding: .35rem .6rem; }}
[data-testid="stSidebarNav"] a:hover {{ background: rgba(255,255,255,.08); }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {TEAL}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] * {{ color: #fff; font-weight: 600; }}
.sb-logo img {{ width: 100%; border-radius: 12px; margin-bottom: .6rem; }}

/* Login */
.iw-login {{ background: {NAVY}; border-radius: 20px; padding: 26px; text-align: center; margin-bottom: 18px; }}
.iw-login img {{ width: min(420px, 100%); border-radius: 12px; }}

/* Components */
.iw-hero {{ background: {NAVY}; border-radius: 20px; padding: 28px 32px; color: #fff;
  display:flex; align-items:center; justify-content:space-between; gap:24px; flex-wrap:wrap; }}
.iw-hero h1 {{ color:#fff; font-size: 1.7rem; font-weight: 800; margin:0 0 6px; letter-spacing:-.02em; }}
.iw-hero p {{ color:#B9C4DD; margin:0; max-width: 520px; line-height:1.5; }}
.iw-hero img {{ height: 64px; border-radius: 14px; }}
.iw-kpi {{ background:#fff; border:1px solid {LINE}; border-radius:14px; padding:18px 20px; }}
.iw-kpi .n {{ font-size:2rem; font-weight:800; letter-spacing:-.03em; line-height:1.1; }}
.iw-kpi .l {{ color:{MUTED}; font-size:.85rem; margin-top:2px; }}
.iw-kpi.warn .n {{ color:#C2410C; }}
.iw-kpi.ok .n {{ color:{TEAL}; }}
.iw-card {{ background:#fff; border:1px solid {LINE}; border-left:4px solid {TEAL};
  border-radius:12px; padding:16px 18px; margin-bottom:6px; }}
.iw-card h4 {{ margin:0 0 4px; font-size:1.02rem; font-weight:700; }}
.iw-card p {{ margin:0; color:{MUTED}; font-size:.88rem; line-height:1.45; }}
.iw-section {{ font-size:1.05rem; font-weight:700; margin: 26px 0 10px; }}
.iw-banner {{ background:{TEAL_SOFT}; border:1px solid #BFE3DC; color:#0B5E52;
  border-radius:12px; padding:10px 16px; font-size:.86rem; margin-top:22px; }}
.iw-pill {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:.75rem; font-weight:600; }}
.iw-pill.open {{ background:#FFF1E0; color:#B45309; }}
.iw-pill.ok {{ background:{TEAL_SOFT}; color:#0B5E52; }}
.iw-pill.bad {{ background:#FDE8E8; color:#B42318; }}
.stButton>button, [data-testid="stPageLink"] a {{ border-radius:10px; font-weight:600; }}
.stButton>button[kind="primary"] {{ background:{TEAL}; border:none; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def ai_banner() -> None:
    """AI Disclosure banner. Reuse on Review / Approvals pages."""
    st.markdown(
        '<div class="iw-banner"><b>AI disclosure:</b> findings are generated with Gemini and '
        'checked against your brand kit. Every suggestion needs a human decision before it is used.</div>',
        unsafe_allow_html=True,
    )


def not_connected(err) -> None:
    """Shown when a backend part is missing. err is services.BackendNotConnected."""
    st.markdown(
        f'<div class="iw-card" style="border-left-color:#C2410C">'
        f'<h4>Backend not connected: {err.part}</h4>'
        f'<p>This screen needs <code>{err.needs}</code>. Owner: {err.owner}. '
        f'It will start working as soon as that is merged into main and you run <code>git pull</code>.</p></div>',
        unsafe_allow_html=True,
    )


def login_screen() -> None:
    """Full-page login. Stops the page until the user signs in."""
    left, mid, right = st.columns([1, 1.6, 1])
    with mid:
        st.markdown(f'<div class="iw-login"><img src="{logo_src()}"/></div>', unsafe_allow_html=True)
        st.subheader("Sign in")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", ROLES)
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            if not username.strip() or not password:
                st.warning("Enter your username and password.")
            else:
                try:
                    result = services.authenticate(username.strip(), password, role)
                except services.BackendNotConnected as e:
                    not_connected(e)
                except Exception as e:
                    st.error(f"Sign in failed ({type(e).__name__}). Try again in a moment.")
                else:
                    if result:
                        st.session_state.auth = True
                        st.session_state.user = result.get("user", username)
                        st.session_state.role = result.get("role", role)
                        st.rerun()
                    else:
                        st.error("Those details did not match. Check your username, password and role.")
    st.stop()


def render_shell() -> None:
    """Call at the top of every page: CSS + login check + sidebar."""
    inject_css()
    st.session_state.setdefault("role", "Creator")
    st.session_state.setdefault("user", "Demo user")

    if REQUIRE_LOGIN and not st.session_state.get("auth"):
        login_screen()

    with st.sidebar:
        src = logo_src()
        if src:
            st.markdown(f'<div class="sb-logo"><img src="{src}"/></div>', unsafe_allow_html=True)
        if REQUIRE_LOGIN:
            st.caption("Signed in as")
            st.markdown(f"**{st.session_state.user}** · {st.session_state.role}")
            if st.button("Sign out", use_container_width=True):
                for key in ("auth", "user", "role"):
                    st.session_state.pop(key, None)
                st.rerun()
        else:
            st.caption("Preview mode: pick a role to test the screens")
            st.session_state.user = st.text_input("Name", st.session_state.user, label_visibility="collapsed")
            st.session_state.role = st.selectbox(
                "Role", ROLES, index=ROLES.index(st.session_state.role), label_visibility="collapsed"
            )