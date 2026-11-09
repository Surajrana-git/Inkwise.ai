"""INKWISE AI - Home.py  (run from repo root:  python -m streamlit run app/Home.py)"""
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent))  # lets pages import theme/services
import services
import theme

st.set_page_config(page_title="inkwise.ai", page_icon="✒️", layout="wide")

SPLASH_SECONDS = 5

# Page files, exactly as named in app/pages/
PAGE_REVIEW = "pages/1_Review.py"
PAGE_APPROVALS = "pages/Approvals.py"
PAGE_HISTORY = "pages/History.py"
PAGE_KB = "pages/Knowledge_Base.py"


# ---------- STEP 1: splash screen (once per session) ----------
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


# ---------- STEP 2: shell (css + sidebar + role) ----------
theme.render_shell()
role = st.session_state.role

# Stats come from engine/workflow.py. If it is not connected yet, show dashes.
try:
    stats = services.get_dashboard_stats(role)
    wf_error = None
except services.BackendNotConnected as e:
    stats = {"reviews_today": "–", "open_findings": "–", "pending_approvals": "–", "expired_facts": "–"}
    wf_error = e

# ---------- STEP 3: hero ----------
st.markdown(
    f"""
    <div class="iw-hero">
      <div>
        <h1>Welcome back, {st.session_state.user}</h1>
        <p>Paste your content, get findings backed by your brand kit, and send approved copy forward.
           You are signed in as <b>{role}</b>.</p>
      </div>
      <img src="{theme.logo_src()}"/>
    </div>
    """,
    unsafe_allow_html=True,
)
c1, c2, _ = st.columns([1.2, 1.2, 4])
with c1:
    st.page_link(PAGE_REVIEW, label="Start a review", icon="📝", use_container_width=True)
with c2:
    st.page_link(PAGE_APPROVALS, label="Open approvals", icon="✅", use_container_width=True)

# ---------- STEP 4: KPI row ----------
st.markdown('<div class="iw-section">Overview</div>', unsafe_allow_html=True)
k = st.columns(4)
kpis = [
    ("reviews_today", "Reviews today", ""),
    ("open_findings", "Open findings", ""),
    ("pending_approvals", "Waiting for approval", "warn"),
    ("expired_facts", "Expired facts flagged", "warn"),
]
for col, (key, label, cls) in zip(k, kpis):
    col.markdown(
        f'<div class="iw-kpi {cls}"><div class="n">{stats[key]}</div><div class="l">{label}</div></div>',
        unsafe_allow_html=True,
    )

# ---------- STEP 5: navigation cards ----------
st.markdown('<div class="iw-section">Where to next</div>', unsafe_allow_html=True)
NAV = [
    (PAGE_REVIEW, "📝", "Review", "Paste content and see cited findings with accept, edit and reject."),
    (PAGE_APPROVALS, "✅", "Approvals", "Work through the queue of findings and drafts waiting for a decision."),
    (PAGE_HISTORY, "🕘", "History", "Look back at earlier reviews and who decided what."),
    (PAGE_KB, "📚", "Knowledge Base", "Browse brand guidelines, facts and the glossary."),
]
cols = st.columns(4)
for col, (path, icon, title, desc) in zip(cols, NAV):
    with col:
        st.markdown(
            f'<div class="iw-card"><h4>{icon} {title}</h4><p>{desc}</p></div>', unsafe_allow_html=True
        )
        st.page_link(path, label=f"Open {title}")

# ---------- STEP 6: recent activity ----------
st.markdown('<div class="iw-section">Recent activity</div>', unsafe_allow_html=True)
if wf_error:
    theme.not_connected(wf_error)
else:
    activity = services.get_recent_activity()
    if not activity:
        st.info("No activity yet. Start a review to see it here.")
    else:
        label = {"open": "Open", "ok": "Done", "bad": "Rejected"}
        for a in activity:
            a1, a2, a3 = st.columns([0.7, 5, 1.2])
            a1.caption(a["when"])
            a2.markdown(f"**{a['who']}** · {a['what']}")
            a3.markdown(
                f'<span class="iw-pill {a["status"]}">{label[a["status"]]}</span>',
                unsafe_allow_html=True,
            )

# ---------- STEP 7: AI disclosure ----------
theme.ai_banner()

# ---------- STEP 8: backend status ----------
with st.expander("Backend status"):
    names = {
        "review": "Review engine (Riyana)",
        "workflow": "Workflow and approvals (Suraj)",
        "knowledge": "Brand kit (Pritha)",
    }
    for part, live in services.backend_status().items():
        st.write(f"{'🟢 Connected' if live else '🔴 Not connected'} · {names[part]}")