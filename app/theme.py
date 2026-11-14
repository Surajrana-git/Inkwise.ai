import base64
import html
from pathlib import Path

import streamlit as st

import services

REQUIRE_LOGIN = True  # Round 3: real sign-in with the demo accounts printed on the login screen

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent

NAVY = "#1B2A4E"
TEAL = "#12917F"
TEAL_SOFT = "#E3F3F0"
BG = "#F4F6FA"
INK = "#1B2A4E"
MUTED = "#5A6480"
LINE = "#E2E7F0"

RED = "#D93025"
AMBER = "#B45309"
BLUE = "#1A73E8"
CATEGORY_COLORS = {
    "claim": RED,
    "fact": RED,
    "expired_fact": RED,
    "expired": RED,
    "unverified_claim": RED,
    "tone": AMBER,
    "terminology": AMBER,
    "glossary": AMBER,
    "accessibility": BLUE,
    "readability": BLUE,
}

LOGO_CANDIDATES = [
    APP_DIR / "inkwise_logo.jpeg",
    ROOT / "assets" / "inkwise_logo.jpeg",
    ROOT / "inkwise_logo.jpeg",
]

ROLES = ["Creator", "Manager", "Reviewer", "Admin"]


def logo_src() -> str:
    for p in LOGO_CANDIDATES:
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            return f"data:image/jpeg;base64,{b64}"
    return ""


CSS = f"""
<style>
html, body, .stApp {{ color: {INK}; }}
.stApp {{ background: {BG}; color-scheme: light; }}
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stDecoration"], .stDeployButton {{ display: none; }}
.block-container {{ padding-top: 1.2rem; max-width: 1180px; }}

h1, h2, h3, h4, h5 {{ color: {NAVY}; letter-spacing: -.01em; }}

textarea, input,
[data-baseweb="textarea"] textarea,
[data-baseweb="input"] input {{
  background: #fff !important;
  color: {INK} !important;
  -webkit-text-fill-color: {INK} !important;
  caret-color: {INK};
}}
[data-baseweb="textarea"], [data-baseweb="input"], [data-baseweb="select"] > div {{
  background: #fff !important;
  border-color: {LINE} !important;
}}
[data-baseweb="select"] div, [data-baseweb="select"] span {{ color: {INK} !important; }}
::placeholder {{ color: {MUTED} !important; opacity: 1 !important; -webkit-text-fill-color: {MUTED} !important; }}

[data-testid="stWidgetLabel"] p, label, label p {{ color: {INK} !important; font-weight: 600; }}
[data-testid="stCaptionContainer"], .stCaption {{ color: {MUTED} !important; }}

[data-testid="stSidebar"] {{ background: #fff; border-right: 1px solid {LINE}; }}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {{ color: {INK}; }}
[data-testid="stSidebarNav"] a {{ border-radius: 8px; padding: .35rem .6rem; }}
[data-testid="stSidebarNav"] a:hover {{ background: {BG}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {TEAL}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] * {{ color: #fff !important; font-weight: 600; }}
.sb-logo img {{ width: 100%; border-radius: 12px; margin-bottom: .6rem; }}

[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"] button {{
  background: {TEAL} !important; color: #fff !important;
  border-radius: 8px; opacity: 1 !important;
}}
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stExpandSidebarButton"] svg,
[data-testid="stSidebarCollapsedControl"] svg {{ fill: #fff !important; color: #fff !important; }}

.iw-login {{ background: {NAVY}; border-radius: 16px; padding: 24px; text-align: center; margin-bottom: 18px; }}
.iw-login img {{ width: min(420px, 100%); border-radius: 12px; }}

.iw-kpi {{ background:#fff; border:1px solid {LINE}; border-radius:10px; padding:12px 14px; min-width:0; }}
.iw-kpi .n {{ font-size:1.8rem; font-weight:700; letter-spacing:-.02em; line-height:1.1; color:{NAVY}; }}
.iw-kpi .l {{ color:{MUTED}; font-size:.85rem; margin-top:2px; 
   white space:nowrap; overflow:hidden; text-overflow:ellipsis; word-break:normal; }}
.iw-kpi.warn .n {{ color:#B45309; }}
.iw-kpi.ok .n {{ color:{TEAL}; }}

.iw-card {{ background:#fff; border:1px solid {LINE}; border-radius:10px;
  padding:14px 16px; margin-bottom:6px; }}
.iw-card h4 {{ margin:0 0 4px; font-size:1rem; font-weight:700; color:{NAVY}; }}
.iw-card p {{ margin:0; color:{MUTED}; font-size:.88rem; line-height:1.45; }}
.iw-section {{ font-size:1.05rem; font-weight:700; margin: 22px 0 8px; color:{NAVY}; }}

.iw-empty {{ border:1px dashed #C5CCDA; border-radius:10px; padding:24px;
  text-align:center; color:{MUTED}; background:#fff; }}

.iw-banner {{ background:{TEAL_SOFT}; border:1px solid #BFE3DC; color:#0B5E52;
  border-radius:8px; padding:6px 12px; font-size:.8rem; margin-top:12px; }}

.iw-pill {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:.75rem; font-weight:600; }}
.iw-pill.open {{ background:#FFF1E0; color:#B45309; }}
.iw-pill.ok {{ background:{TEAL_SOFT}; color:#0B5E52; }}
.iw-pill.bad {{ background:#FDE8E8; color:#B42318; }}

.iw-tag {{ display:inline-block; padding:1px 6px; border-radius:4px; font-size:.7rem;
  font-weight:700; letter-spacing:.03em; border:1px solid {LINE}; color:{MUTED}; background:#fff; }}
.iw-tag.ai {{ color:{TEAL}; border-color:{TEAL}; }}

.iw-quote {{ background:{BG}; border-left:3px solid #C5CCDA; border-radius:4px;
  padding:10px 14px; color:{INK}; font-size:.9rem; line-height:1.5; }}
.iw-quote .src {{ color:{MUTED}; font-size:.78rem; margin-top:4px; }}

.iw-text {{ background:#fff; border:1px solid {LINE}; border-radius:10px;
  padding:16px 18px; line-height:1.9; color:{INK}; white-space:pre-wrap; }}
.iw-text mark {{ background:transparent; color:inherit; padding:0 1px;
  text-decoration-line:underline; text-decoration-style:wavy; text-decoration-thickness:2px;
  text-underline-offset:3px; }}
.iw-text sup {{ font-weight:700; font-size:.7rem; margin-left:1px; }}

.stButton>button, [data-testid="stPageLink"] a {{ border-radius:8px; font-weight:600; }}
.stButton>button[kind="primary"] {{ background:{TEAL}; border:none; color:#fff; }}
.stButton>button[kind="secondary"] {{ background:#fff; color:{INK}; border:1px solid {LINE}; }}

[data-testid="stAppDeployButton"] {{ display: none !important; }}

[data-baseweb="select"] > div, [data-baseweb="select"] > div > div {{ background: #fff !important; }}
[data-baseweb="select"] svg {{ fill: {INK} !important; color: {INK} !important; }}
[data-baseweb="popover"] ul, [data-baseweb="popover"] li, [data-baseweb="menu"] {{
  background: #fff !important; color: {INK} !important; }}

[data-testid="stBaseButton-secondary"] {{ background: #fff !important; color: {INK} !important;
  border: 1px solid {LINE} !important; border-radius: 8px; font-weight: 600; }}
[data-testid="stBaseButton-secondary"] p {{ color: {INK} !important; }}
[data-testid="stBaseButton-primary"] {{ background: {TEAL} !important; color: #fff !important;
  border: none !important; border-radius: 8px; font-weight: 600; }}
[data-testid="stBaseButton-primary"] p {{ color: #fff !important; }}

[data-baseweb="tab"] p {{ color: {INK} !important; font-weight: 600; }}
[data-baseweb="tab-highlight"] {{ background: {TEAL} !important; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED} !important; }}
[data-testid="stMetricValue"] {{ color: {NAVY} !important; }}

[data-baseweb="radio"] > div:first-child {{ border-color: {TEAL} !important; }}
[data-baseweb="radio"] label p, [data-testid="stRadio"] p {{ color: {INK} !important; }}

[data-testid="stExpander"] summary p {{ color: {INK} !important; font-weight: 600; }}
[data-testid="stExpander"] {{ background: #fff; border: 1px solid {LINE}; border-radius: 10px; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def ai_banner() -> None:
    st.markdown(
        '<div class="iw-banner"><b>AI disclosure:</b> findings are generated with Gemini and '
        'checked against your brand kit. A human must approve every suggestion.</div>',
        unsafe_allow_html=True,
    )


def empty_state(msg: str) -> None:
    st.markdown(f'<div class="iw-empty">{html.escape(msg)}</div>', unsafe_allow_html=True)


def metric_row(items) -> None:
    cols = st.columns(len(items))
    for col, (n, label, kind) in zip(cols, items):
        col.markdown(
            f'<div class="iw-kpi {kind}"><div class="n">{n}</div><div class="l">{html.escape(label)}</div></div>',
            unsafe_allow_html=True,
        )


def source_quote(source_text: str, source_id: str, owner: str = "") -> None:
    owner_part = f" · {html.escape(owner)}" if owner else ""
    st.markdown(
        f'<div class="iw-quote">{html.escape(source_text)}'
        f'<div class="src">{html.escape(source_id)}{owner_part}</div></div>',
        unsafe_allow_html=True,
    )
    if source_id == "UNVERIFIED":
        st.warning("No approved source supports this claim.")


def checker_tag(checked_by: str) -> str:
    if checked_by == "ai":
        return '<span class="iw-tag ai">AI</span>'
    return '<span class="iw-tag">Rule</span>'


def highlight_html(text: str, findings) -> str:
    out, pos = [], 0
    for i, f in enumerate(sorted(findings, key=lambda x: x["start"]), 1):
        if f["start"] < pos:
            continue
        color = CATEGORY_COLORS.get(str(f.get("category", "")).lower(), MUTED)
        out.append(html.escape(text[pos:f["start"]]))
        out.append(
            f'<mark style="text-decoration-color:{color};">'
            f'{html.escape(text[f["start"]:f["end"]])}</mark>'
            f'<sup style="color:{color}">[{i}]</sup>'
        )
        pos = f["end"]
    out.append(html.escape(text[pos:]))
    return f'<div class="iw-text">{"".join(out)}</div>'


def not_connected(err) -> None:
    st.markdown(
        f'<div class="iw-card" style="border-color:#B45309">'
        f'<h4>Backend not connected: {err.part}</h4>'
        f'<p>This screen needs <code>{err.needs}</code>. Owner: {err.owner}. '
        f'It will start working as soon as that is merged into main and you run <code>git pull</code>.</p></div>',
        unsafe_allow_html=True,
    )


def login_screen() -> None:
    left, mid, right = st.columns([1, 1.6, 1])
    with mid:
        st.markdown(f'<div class="iw-login"><img src="{logo_src()}"/></div>', unsafe_allow_html=True)
        st.subheader("Sign in")
        st.caption("Inkwise checks marketing copy against the Lumora brand kit and explains every finding "
                   "with its source. Use a demo account below; no real data is involved.")
        accounts = services.demo_accounts()
        if accounts:
            rows = "".join(
                f"<tr><td><code>{html.escape(a['username'])}</code></td><td><code>{html.escape(a['password'])}</code></td>"
                f"<td>{html.escape(a['role'])}</td><td>{html.escape(a['can'])}</td></tr>" for a in accounts)
            st.markdown(
                '<div class="iw-card"><h4>Demo accounts</h4>'
                '<table style="width:100%;font-size:.85rem;border-collapse:collapse">'
                '<tr style="color:#5A6480"><th align="left">Username</th><th align="left">Password</th>'
                '<th align="left">Role</th><th align="left">Can do</th></tr>' + rows + '</table></div>',
                unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", ROLES)
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
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
                        st.session_state.team = result.get("team", "")
                        st.rerun()
                    else:
                        st.error("Those details did not match. Check the username, password and that the "
                                 "role matches the account (see the demo accounts above).")
    st.stop()


def render_shell() -> None:
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
            if st.button("Sign out", width="stretch"):
                for key in ("auth", "user", "role"):
                    st.session_state.pop(key, None)
                st.rerun()
        else:
            st.caption("Preview mode: pick a role to test the screens")
            st.session_state.user = st.text_input("Name", st.session_state.user, label_visibility="collapsed")
            st.session_state.role = st.selectbox(
                "Role", ROLES, index=ROLES.index(st.session_state.role), label_visibility="collapsed"
            )