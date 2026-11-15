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


theme.restore_session()          # a refresh keeps the demo person signed in (no splash again)
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
theme.page_header(f"{theme.WORKSPACE.get(role, ('Workspace', ''))[0]} · {theme.ORG}", f"{greet}, {first}", SUB.get(role, ""))

wf_error, stats, queue, activity, facts, submissions, unclear = None, {}, [], [], [], [], 0
try:
    stats = services.get_dashboard_stats(role)
    submissions = services.list_submissions()
    activity = services.get_recent_activity(8)
    facts = services.fact_register()
    if role != "Creator":
        unclear = sum(1 for g in services.guideline_stats() if g.get("unclear") and not g.get("accepted_rewording"))
    if role == "Creator":
        queue = [s for s in submissions if s.get("author") == user and s.get("status") in ("rejected", "pending")]
    else:
        queue = [s for s in submissions if s.get("status") == "pending" and s.get("author") != user]
except services.BackendNotConnected as e:
    wf_error = e

# what needs this person right now, in one line, with the button that does it
def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


if not wf_error:
    if role == "Creator":
        back = [s for s in queue if s.get("status") == "rejected"]
        waiting = [s for s in queue if s.get("status") == "pending"]
        if back:
            theme.attention("bad", f"<b>{_plural(len(back), 'draft was', 'drafts were')} sent back to you</b> with a "
                            "comment from your manager. Fix it and send it again.", "pages/History.py", "Open my drafts →")
        elif waiting:
            theme.attention("warn", f"<b>{_plural(len(waiting), 'draft is', 'drafts are')} waiting for sign-off.</b> "
                            "You will get a notification when the manager decides.", "pages/History.py", "See my drafts →")
        else:
            theme.attention("ok", "<b>Nothing is waiting on you.</b> Paste or import your next draft to check it.",
                            PAGE_REVIEW, "Check a draft →")
    elif role == "Admin":
        expired = stats.get("expired_facts", 0) or 0
        if expired:
            theme.attention("bad", f"<b>{_plural(expired, 'fact has', 'facts have')} expired.</b> Drafts that repeat "
                            "them are flagged until you renew them.", "pages/Fact_Register.py", "Renew facts →")
        elif unclear:
            theme.attention("warn", f"<b>{_plural(unclear, 'guideline looks', 'guidelines look')} unclear</b> to "
                            "reviewers. Accept a clearer wording.", "pages/Insights.py", "Open insights →")
        else:
            theme.attention("ok", "<b>Every fact is current</b> and no guideline looks unclear.")
    else:
        if queue:
            theme.attention("warn", f"<b>{_plural(len(queue), 'draft is', 'drafts are')} waiting for your decision.</b> "
                            "Each one shows the creator's choices and the evidence behind every finding.",
                            PAGE_APPROVALS, "Open the approval queue →")
        else:
            theme.attention("ok", "<b>Your approval queue is empty.</b> New drafts appear here and in the bell.",
                            "pages/Insights.py", "See guideline insights →")
    st.write("")

# primary action per role: page links styled as buttons (first one filled)
st.markdown("""<style>
.st-key-home_actions [data-testid="stPageLink"] a { border:1px solid #CFD8E6 !important; border-radius:10px !important;
  background:#fff !important; padding:9px 14px !important; justify-content:center; transition:all .15s ease; }
.st-key-home_actions [data-testid="stPageLink"] a:hover { border-color:#12917F !important; box-shadow:0 6px 16px rgba(18,145,127,.12); }
.st-key-home_actions [data-testid="stPageLink"] a p { font-weight:600 !important; color:#1B2A4E !important; font-size:.86rem !important; }
.st-key-home_actions [data-testid="stColumn"]:first-child [data-testid="stPageLink"] a { background:#12917F !important;
  border-color:#12917F !important; }
.st-key-home_actions [data-testid="stColumn"]:first-child [data-testid="stPageLink"] a p { color:#fff !important; }
</style>""", unsafe_allow_html=True)
with st.container(key="home_actions"):
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
_n = lambda rows, **kv: sum(1 for s in rows if all(s.get(k) == v for k, v in kv.items()))  # noqa: E731
mine = [s for s in submissions if s.get("author") == user]
if role == "Creator":           # my own drafts and where they are
    cards = [
        (len(mine), "My drafts", "✎", "#E8F6F2", "#0B5E52"),
        (_n(mine, status="pending"), "Waiting for approval", "⧗", "#FFF4E0", "#8A4B06"),
        (_n(mine, status="rejected"), "Sent back to me", "↩", "#FDECEC", "#B42318"),
        (_n(mine, status="approved"), "Approved", "✓", "#E8F6F2", "#0B5E52"),
        (stats.get("reviews_today", d), "Checks today", "◎", "#EEF2FF", "#3C4FB8"),
    ]
elif role == "Admin":           # facts and guidelines
    cards = [
        (stats.get("expired_facts", d), "Expired facts", "!", "#FDECEC", "#B42318"),
        (stats.get("expiring_facts", d), "Expiring in 30 days", "◷", "#FFF7E6", "#9A5B00"),
        (unclear, "Guidelines that look unclear", "?", "#EEF2FF", "#3C4FB8"),
        (len(facts), "Facts in the register", "≡", "#E8F6F2", "#0B5E52"),
        (len(submissions), "Drafts in the workspace", "✎", "#F3F5F9", "#5A6480"),
    ]
else:                           # Manager: the sign-off desk
    cards = [
        (len(queue), "Waiting for you", "⧗", "#FFF4E0", "#8A4B06"),
        (_n(submissions, decided_by=user, status="approved"), "Approved by you", "✓", "#E8F6F2", "#0B5E52"),
        (_n(submissions, decided_by=user, status="rejected"), "Sent back by you", "↩", "#FDECEC", "#B42318"),
        (unclear, "Guidelines that look unclear", "?", "#EEF2FF", "#3C4FB8"),
        (stats.get("reviews_today", d), "Checks today", "◎", "#F3F5F9", "#5A6480"),
    ]
theme.stat_cards(cards)
st.write("")

left, right = st.columns([1.75, 1], gap="large")

with left:
    # needs attention
    title = {"Creator": "Returned to you or waiting", "Admin": "Drafts waiting for a Manager"}.get(
        role, "Waiting for your decision")
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
            st.page_link(PAGE_APPROVALS if role in ("Manager", "Reviewer") else "pages/History.py",
                         label="Open the full list →")
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
        st.button("Hide this guide", key="tour_hide", on_click=st.session_state.__setitem__, args=("tour_hidden", True))
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

    # fact health: Admins see every fact; everyone else sees the facts their own team owns (they may renew those)
    team = st.session_state.get("team", "")
    pool = facts if role == "Admin" else [f for f in facts if team and f.get("owner") == team]
    risky = [f for f in pool if f["status"] != "valid"][:4]
    frows = "".join(
        f'<div class="iw-row"><span class="iw-dot" style="background:{"#D93025" if f["status"] == "expired" else "#B45309"}"></span>'
        f'<div class="t"><b>{html.escape(f["id"])} · {html.escape(f["statement"])}</b>'
        f'<small>{html.escape(f["owner"])} · {"expired" if f["status"] == "expired" else "expires"} {html.escape(f["expires_on"])}</small></div></div>'
        for f in risky)
    if role == "Admin":
        fh_title, fh_sub = "Fact health", (f'{stats.get("expired_facts", 0)} expired · '
                                          f'{stats.get("expiring_facts", 0)} expiring in 30 days')
    else:
        fh_title = "Facts your team owns"
        fh_sub = (f"{len(pool)} owned by {html.escape(team)} · {len(risky)} need attention" if team
                  else "You do not own any facts")
    st.markdown(f'<div class="iw-panel"><h3>{fh_title}</h3><div class="sub">{fh_sub}</div>{frows or empty}</div>',
                unsafe_allow_html=True)
    if risky and role != "Admin":
        try:
            st.page_link("pages/Fact_Register.py", label="Renew your team's facts →")
        except Exception:
            pass

if stats.get("seeded_at"):
    st.caption(f"Demo workspace: sample history was loaded on {stats['seeded_at']} UTC and comes back automatically "
               "if the free host restarts.")
theme.ai_banner()
theme.footer()
