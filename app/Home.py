import html
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent))
import services
import theme

st.set_page_config(page_title="inkwise.ai", layout="wide")

SPLASH_SECONDS = 0.8

PAGE_REVIEW = "pages/1_Review.py"
PAGE_APPROVALS = "pages/Approvals.py"


def splash() -> None:
    theme.persist_css({"iw-boot": theme.BOOT_CSS})       # navy stays while the sign-in page loads
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


if not st.session_state.get("splash_done") and not st.session_state.get("auth"):
    splash()
    st.stop()

services.ensure_started()


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
if role == "Creator" and st.session_state.get("landed_for") != user:
    st.session_state.landed_for = user
    try:
        st.switch_page(PAGE_REVIEW)
    except Exception:
        pass
first = theme.full_name(user).split()[0]

import datetime as _dt
hour = (_dt.datetime.utcnow() + _dt.timedelta(hours=5, minutes=30)).hour
greet = "Good morning" if 5 <= hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
SUB = {
    "Creator": "Check your copy before it goes out. Every finding shows the brand-kit source behind it.",
    "Manager": "Drafts waiting for you, and which guidelines your team finds unclear.",
    "Admin": "Keep facts current, settle unclear guidelines and keep an eye on the whole workspace.",
    "Reviewer": "Drafts waiting for a decision, with the evidence behind every finding.",
}
theme.page_header(f"Workspace · {theme.ORG}", f"{greet}, {first}", SUB.get(role, ""))

wf_error, stats, queue, activity, facts = None, {}, [], [], []
try:
    stats = services.get_dashboard_stats(role)
    submissions = services.list_submissions()
    activity = services.get_recent_activity(8)
    facts = services.fact_register()
    if role == "Creator":
        queue = [s for s in submissions if s.get("author") == user and s.get("status") in ("rejected", "pending")]
    else:
        queue = [s for s in submissions if s.get("status") == "pending"]
except services.BackendNotConnected as e:
    wf_error = e

# primary action per role
a1, a2, a3, _ = st.columns([1.3, 1.3, 1.3, 4])
def _go(col, label, page, primary=False, key=None):
    with col:
        try:
            st.page_link(page, label=label, width="stretch")
        except Exception:
            st.button(label, key=key or label, width="stretch", type="primary" if primary else "secondary")
if role == "Creator":
    _go(a1, "＋  New review", PAGE_REVIEW, True)
    _go(a2, "My submissions", "pages/History.py")
elif role == "Admin":
    _go(a1, f"Renew expired facts ({stats.get('expired_facts', 0)})", "pages/Fact_Register.py", True)
    _go(a2, "Guideline insights", "pages/Insights.py")
    _go(a3, "Brand kit", "pages/Knowledge_Base.py")
else:
    _go(a1, f"Review approvals ({stats.get('pending_approvals', 0)})", PAGE_APPROVALS, True)
    _go(a2, "Guideline insights", "pages/Insights.py")
st.write("")

d = "–"
theme.stat_cards([
    (stats.get("reviews_today", d), "Reviews today", "✎", "#E8F6F2", "#0B5E52"),
    (stats.get("open_findings", d), "Open findings", "◎", "#EEF2FF", "#3C4FB8"),
    (stats.get("pending_approvals", d), "Waiting for approval", "⧗", "#FFF4E0", "#8A4B06"),
    (stats.get("expired_facts", d), "Expired facts", "!", "#FDECEC", "#B42318"),
    (stats.get("expiring_facts", d), "Expiring in 30 days", "◷", "#FFF7E6", "#9A5B00"),
])
st.write("")

left, right = st.columns([1.75, 1], gap="large")

with left:
    # needs attention
    title = "Returned to you or waiting" if role == "Creator" else "Waiting for your decision"
    rows = ""
    for s in queue[:6]:
        stc = s.get("status", "")
        dot = "#D93025" if stc == "rejected" else "#B45309"
        lbl = "Changes requested" if stc == "rejected" else "Pending"
        rows += (f'<div class="iw-row"><span class="iw-dot" style="background:{dot}"></span>'
                 f'<div class="t"><b>{html.escape(s.get("title", "Untitled"))}</b>'
                 f'<small>{html.escape(theme.full_name(s.get("author", "")))} · {html.escape(s.get("submitted_at", ""))} · '
                 f'{len(s.get("findings", []))} findings</small></div>'
                 f'<span class="iw-pill {"bad" if stc == "rejected" else "open"}">{lbl}</span></div>')
    empty = '<div class="sub" style="padding:14px 0">Nothing is waiting for you. Nice.</div>'
    st.markdown(f'<div class="iw-panel"><h3>{title}</h3><div class="sub">{len(queue)} item(s)</div>'
                f'{rows or empty}</div>', unsafe_allow_html=True)
    if queue:
        try:
            st.page_link(PAGE_APPROVALS if role != "Creator" else "pages/History.py", label="Open the full list →")
        except Exception:
            pass

    # activity timeline
    COL = {"ok": "#12917F", "bad": "#D93025", "open": "#8A93A6"}
    act = "".join(
        f'<div class="iw-row"><span class="iw-dot" style="background:{COL.get(a.get("status"), "#8A93A6")}"></span>'
        f'<div class="t"><b style="font-weight:600">{html.escape(theme.full_name(a.get("who", "")))} '
        f'<span style="font-weight:400;color:#5A6480">{html.escape(a.get("what", ""))}</span></b>'
        f'<small>{html.escape(a.get("day", ""))} · {html.escape(a.get("when", ""))} UTC</small></div></div>'
        for a in activity)
    st.markdown(f'<div class="iw-panel"><h3>Recent activity</h3><div class="sub">From the audit log</div>'
                f'{act or empty}</div>', unsafe_allow_html=True)

with right:
    # guided path for judges
    TOUR = [
        ("1", "Evidence-grounded review", "asha", "pages/1_Review.py",
         "Review a sample post. Each finding quotes its source, or is marked UNVERIFIED.", "launch"),
        ("2", "Fact freshness", "ravi", "pages/Fact_Register.py",
         "Expired facts first, each with an owner. Renew one; open drafts are re-checked.", None),
        ("3", "Guideline clarity", "meera", "pages/Insights.py",
         "See which rules reviewers keep overriding, and accept a clearer wording.", None),
    ]
    if not st.session_state.get("tour_hidden"):
        steps = "".join(f'<div class="iw-step"><span class="num">{n}</span><div><b>{t}</b><small>{d}</small></div></div>'
                        for n, t, _w, _p, d, _s in TOUR)
        st.markdown(f'<div class="iw-panel"><h3>Try it in 3 minutes</h3><div class="sub">Each step signs you in as '
                    f'the right person</div>{steps}</div>', unsafe_allow_html=True)
        bcols = st.columns(3)
        for col, (n, t, who, page, _d, sample_id) in zip(bcols, TOUR):
            if col.button(f"Step {n}", key=f"tour_{n}", width="stretch", help=f"Go as {theme.full_name(who)}"):
                if theme.switch_user(who):
                    if sample_id:
                        sample = next((x for x in services.demo_samples() if x["id"] == sample_id), None)
                        if sample:
                            st.session_state.rv_text = sample["text"]
                            st.session_state.rv_title = sample["title"]
                    st.switch_page(page)
        if st.button("Hide this guide", key="tour_hide"):
            st.session_state.tour_hidden = True
            st.rerun()
        st.write("")

    # measured accuracy
    ev = services.eval_summary()
    if ev.get("recall"):
        bars = "".join(
            f'<div class="iw-bar"><span class="k">{html.escape(k)}</span><div class="track">'
            f'<div class="fill" style="width:{(a / b * 100) if b else 0:.0f}%"></div></div><span class="v">{a}/{b}</span></div>'
            for k, a, b in ev.get("by_type", []))
        st.markdown(
            f'<div class="iw-panel"><h3>Measured accuracy</h3><div class="sub">Labelled test set, '
            f'{html.escape(ev.get("samples") or "100")} samples · rules + Gemini</div>'
            f'<div class="iw-big"><div><b>{ev["recall"]}</b><small>recall</small></div>'
            f'<div><b>{ev.get("precision", d)}</b><small>precision</small></div>'
            f'<div><b>{ev.get("citation", d)}</b><small>correct source cited</small></div></div>'
            f'{bars}<div class="sub" style="margin-top:8px">Method and raw results: eval/results.md</div></div>',
            unsafe_allow_html=True)

    # fact health
    risky = [f for f in facts if f["status"] != "valid"][:4]
    frows = "".join(
        f'<div class="iw-row"><span class="iw-dot" style="background:{"#D93025" if f["status"] == "expired" else "#B45309"}"></span>'
        f'<div class="t"><b>{html.escape(f["id"])} · {html.escape(f["statement"])}</b>'
        f'<small>{html.escape(f["owner"])} · {"expired" if f["status"] == "expired" else "expires"} {html.escape(f["expires_on"])}</small></div></div>'
        for f in risky)
    st.markdown(f'<div class="iw-panel"><h3>Fact health</h3><div class="sub">{stats.get("expired_facts", 0)} expired · '
                f'{stats.get("expiring_facts", 0)} expiring in 30 days</div>{frows or empty}</div>', unsafe_allow_html=True)

if stats.get("seeded_at"):
    st.caption(f"Demo workspace: sample history was loaded on {stats['seeded_at']} UTC and comes back automatically "
               "if the free host restarts.")
theme.ai_banner()
