import sys
import time
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent))
import services
import theme

st.set_page_config(page_title="inkwise.ai", layout="wide")

SPLASH_SECONDS = 5

PAGE_REVIEW = "pages/1_Review.py"
PAGE_APPROVALS = "pages/Approvals.py"


def splash() -> None:
    st.markdown(
        f"""
        <style>
          [data-testid="stSidebar"], [data-testid="stSidebarNav"],
          [data-testid="collapsedControl"], header, footer {{ display:none !important; }}
          .stApp {{ background:{theme.NAVY} !important; }}
          .splash {{ height:80vh; display:flex; flex-direction:column; align-items:center;
                     justify-content:center; gap:28px; }}
          .splash img {{ width:min(560px, 86vw); animation: pop .9s ease-out both; }}
          .bar {{ width:min(280px, 60vw); height:4px; background:rgba(255,255,255,.15);
                  border-radius:4px; overflow:hidden; }}
          .bar i {{ display:block; height:100%; background:{theme.TEAL};
                    animation: fill {SPLASH_SECONDS}s linear forwards; }}
          @keyframes pop {{ from {{ opacity:0; transform:scale(.94); }} to {{ opacity:1; transform:scale(1); }} }}
          @keyframes fill {{ from {{ width:0; }} to {{ width:100%; }} }}
          @media (prefers-reduced-motion: reduce) {{ .splash img {{ animation:none; }} }}
        </style>
        <div class="splash"><img src="{theme.logo_src()}"/><div class="bar"><i></i></div></div>
        """,
        unsafe_allow_html=True,
    )
    time.sleep(SPLASH_SECONDS)
    st.session_state.splash_done = True
    st.rerun()


if not st.session_state.get("splash_done"):
    splash()
    st.stop()


theme.render_shell()

if not theme.REQUIRE_LOGIN:
    current = st.session_state.role
    picked = st.radio(
        "Viewing as",
        theme.ROLES,
        index=theme.ROLES.index(current),
        horizontal=True,
    )
    if picked != current:
        st.session_state.role = picked
        st.rerun()

role = st.session_state.role
user = st.session_state.user

st.title("Home")
st.caption(f"{user} · {role}")

c1, c2, _ = st.columns([1.2, 1.2, 4])
with c1:
    st.page_link(PAGE_REVIEW, label="Start a review", use_container_width=True)
with c2:
    st.page_link(PAGE_APPROVALS, label="Open approvals", use_container_width=True)

wf_error = None
stats = {}
queue = []
activity = []
try:
    stats = services.get_dashboard_stats(role)
    submissions = services.list_submissions()
    activity = services.get_recent_activity()
    if role == "Creator":
        queue = [s for s in submissions
                 if s.get("author") == user and str(s.get("status", "")).lower() in ("rejected", "changes_requested")]
    else:
        queue = [s for s in submissions if str(s.get("status", "")).lower() in ("pending", "open", "submitted")]
except services.BackendNotConnected as e:
    wf_error = e

dash = "–"
theme.metric_row([
    (stats.get("reviews_today", dash), "Reviews today", ""),
    (stats.get("open_findings", dash), "Open findings", ""),
    (stats.get("pending_approvals", dash), "Waiting for approval", "warn"),
    (stats.get("expired_facts", dash), "Expired facts flagged", "warn"),
])

st.markdown('<div class="iw-section">Waiting for you</div>', unsafe_allow_html=True)
if wf_error:
    theme.not_connected(wf_error)
elif not queue:
    theme.empty_state("Nothing is waiting for you right now.")
else:
    for s in queue[:5]:
        q1, q2 = st.columns([5, 1.4])
        q1.markdown(f"**{s.get('title', 'Untitled')}**")
        q1.caption(f"{s.get('author', '')} · {s.get('submitted', s.get('when', ''))}")
        status = str(s.get("status", "open")).lower()
        cls = "bad" if status in ("rejected", "changes_requested") else "open"
        q2.markdown(
            f'<span class="iw-pill {cls}">{status.replace("_", " ").title()}</span>',
            unsafe_allow_html=True,
        )
    if len(queue) > 5:
        st.caption(f"{len(queue) - 5} more in Approvals.")
    st.page_link(PAGE_APPROVALS, label="Go to Approvals")

st.markdown('<div class="iw-section">Recent activity</div>', unsafe_allow_html=True)
if wf_error:
    pass
elif not activity:
    theme.empty_state("No activity yet. Start a review to see it here.")
else:
    label = {"open": "Open", "ok": "Done", "bad": "Rejected"}
    for a in activity:
        status = a.get("status", "open")
        a1, a2, a3 = st.columns([0.9, 5, 1.2])
        a1.caption(a.get("when", ""))
        a2.markdown(f"**{a.get('who', '')}** · {a.get('what', '')}")
        a3.markdown(
            f'<span class="iw-pill {status}">{label.get(status, status.title())}</span>',
            unsafe_allow_html=True,
        )

theme.ai_banner()

with st.expander("Backend status"):
    names = {
        "review": "Review engine (Riyana)",
        "workflow": "Workflow and approvals (Suraj)",
        "knowledge": "Brand kit (Pritha)",
    }
    for part, live in services.backend_status().items():
        st.write(f"{'Connected' if live else 'Not connected'} · {names[part]}")