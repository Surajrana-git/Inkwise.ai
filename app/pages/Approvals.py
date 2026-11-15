"""Approvals: a manager's sign-off desk. Queue on the left, the selected draft on the right."""
import html
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
import streamlit as st
import services
import theme
import review_helpers as rh

st.set_page_config(page_title="inkwise.ai", page_icon="✒️", layout="wide")
theme.render_shell()
ss = st.session_state
role, user = ss.get("role", "Creator"), ss.get("user", "")
APPROVER = role in ("Manager", "Reviewer")
if ss.get("ap_flash"):
    st.toast(ss.pop("ap_flash"))

st.markdown("""<style>
.st-key-ap_queue, .st-key-ap_detail, .st-key-ap_recent { background:#fff; border:1px solid #E2E7F0; border-radius:16px;
  padding:16px 16px 12px; box-shadow:0 1px 2px rgba(20,24,33,.03), 0 8px 24px rgba(20,24,33,.04); }
.ap-h { display:flex; justify-content:space-between; align-items:baseline; margin:0 0 8px; }
.ap-h b { color:#1B2A4E; font-size:1rem; } .ap-h small { color:#5A6480; font-size:.76rem; }
.st-key-ap_queue .stButton button { width:100%; justify-content:flex-start; text-align:left; border-radius:12px !important;
  border:1px solid #EEF0F4 !important; background:#FCFCFD !important; padding:10px 12px 10px 14px !important;
  min-height:64px; position:relative; box-shadow:none !important; }
.st-key-ap_queue .stButton button:hover { border-color:#12917F !important; background:#fff !important; }
.st-key-ap_queue .stButton button p { text-align:left; font-size:.76rem; color:#5A6480 !important; line-height:1.35;
  font-weight:400 !important; }
.st-key-ap_queue .stButton button p strong { display:block; color:#1B2A4E; font-size:.9rem; font-weight:650; margin-bottom:2px; }
.st-key-ap_queue .stButton button[kind="primary"] { background:#F0F8F6 !important; border:1px solid #12917F !important;
  box-shadow:inset 3px 0 0 #12917F !important; }
.ap-top { display:flex; gap:14px; align-items:flex-start; justify-content:space-between; }
.ap-top h3 { font-family:'Instrument Serif', Georgia, serif !important; font-weight:400 !important; font-size:1.7rem !important;
  color:#1B2A4E !important; margin:0 !important; padding:0 !important; line-height:1.15 !important; }
.ap-meta { display:flex; flex-wrap:wrap; gap:14px; align-items:center; margin:8px 0 14px; font-size:.78rem; color:#5A6480; }
.ap-av { width:30px; height:30px; border-radius:50%; background:#1B2A4E; color:#fff; font-weight:700; font-size:.7rem;
  display:inline-flex; align-items:center; justify-content:center; margin-right:8px; }
.ap-who { display:inline-flex; align-items:center; color:#1B2A4E; font-weight:600; font-size:.84rem; }
.ap-badge { font-size:.72rem; font-weight:700; padding:5px 11px; border-radius:999px; white-space:nowrap; }
.ap-badge.ok { background:#E8F6F2; color:#0B5E52; } .ap-badge.warn { background:#FFF4E0; color:#8A4B06; }
.ap-badge.bad { background:#FDECEC; color:#B42318; } .ap-badge.mute { background:#F3F5F9; color:#33415C; }
.ap-checks { display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; margin:0 0 14px; }
.ap-checks div { border-radius:12px; padding:10px 12px; border:1px solid #EEF0F4; background:#FCFCFD; }
.ap-checks b { display:block; font-size:.82rem; color:#1B2A4E; margin-top:2px; }
.ap-checks small { font-size:.72rem; color:#5A6480; }
.ap-checks .ok i { color:#12917F; } .ap-checks .warn { background:#FFFAF0; border-color:#F6DFB5; } .ap-checks .warn i { color:#B45309; }
.ap-checks i { font-style:normal; font-weight:700; }
.ap-lbl { font-size:.66rem; letter-spacing:.14em; font-weight:700; color:#8A93A6; margin:6px 0 6px; }
.ap-tbl { width:100%; border-collapse:separate; border-spacing:0; font-size:.8rem; margin-bottom:6px; }
.ap-tbl th { text-align:left; font-size:.64rem; letter-spacing:.12em; color:#8A93A6; font-weight:700; padding:6px 8px;
  border-bottom:1px solid #EEF0F4; }
.ap-tbl td { padding:9px 8px; border-bottom:1px solid #F3F4F7; vertical-align:top; color:#1B2A4E; }
.ap-tbl td small { color:#5A6480; } .ap-tbl code { font-size:.72rem; background:#F3F5F9; padding:1px 5px; border-radius:5px; }
.ap-st { font-size:.68rem; font-weight:700; padding:2px 8px; border-radius:999px; white-space:nowrap; }
.ap-st.accepted, .ap-st.edited { background:#E8F6F2; color:#0B5E52; } .ap-st.rejected { background:#F3F5F9; color:#5A6480; }
.ap-st.open { background:#FFF4E0; color:#8A4B06; }
.ap-note { border-radius:12px; padding:12px 14px; font-size:.84rem; margin:6px 0 10px; }
.ap-note.lock { background:#F3F5F9; color:#33415C; } .ap-note.lock b { color:#1B2A4E; }
.st-key-ap_decide { border-top:1px solid #EEF0F4; padding-top:12px; margin-top:6px; }
.st-key-ap_decide .stButton button { min-height:44px; font-weight:650; }
.st-key-ap_back button { background:#fff !important; color:#B42318 !important; border:1px solid #F3B4B0 !important; }
.st-key-ap_back button:hover { background:#FDECEC !important; }
.ap-empty { text-align:center; padding:40px 10px; color:#5A6480; }
.ap-empty b { display:block; color:#1B2A4E; font-size:1.05rem; margin:8px 0 4px; }
</style>""", unsafe_allow_html=True)

theme.page_header("Approval desk", "Approval queue",
                  "Read what the creator changed, check it is safe to publish, then approve it or send it back.")

try:
    subs = services.list_submissions()
except services.BackendNotConnected as e:
    theme.not_connected(e)
    st.stop()


def _mins(stamp: str):
    """Minutes since a 'YYYY-MM-DD HH:MM' UTC stamp, or None."""
    try:
        t = datetime.strptime((stamp or "")[:16], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int((datetime.now(timezone.utc) - t).total_seconds() // 60)


def _age(stamp: str) -> str:
    m = _mins(stamp)
    if m is None:
        return stamp or ""
    if m < 60:
        return f"{max(m, 1)} min ago"
    if m < 60 * 24:
        return f"{m // 60} h ago"
    return f"{m // 1440} days ago" if m >= 2880 else "yesterday"


def readiness(s: dict) -> dict:
    fs = s["findings"]
    open_n = sum(f["status"] == "open" for f in fs)
    kept_expired = sum(f["category"] == "outdated_fact" and f["status"] == "rejected" for f in fs)
    kept_unver = sum(f["source_id"] == "UNVERIFIED" and f["status"] == "rejected" for f in fs)
    edited = sum(f["status"] == "edited" for f in fs)
    risks = open_n + kept_expired + kept_unver
    return {"open": open_n, "expired": kept_expired, "unver": kept_unver, "edited": edited,
            "ready": risks == 0, "label": "Ready to approve" if risks == 0 else "Needs a look"}


pending = [s for s in subs if s["status"] == "pending"]
decided = [s for s in subs if s["status"] in ("approved", "rejected")]
ready_n = sum(readiness(s)["ready"] for s in pending)
week = sum(1 for d in decided if (_mins(d.get("decided_at")) or 10**9) <= 7 * 1440)
theme.stat_cards([
    (len(pending), "Waiting for sign-off", "⧗", "#FFF4E0", "#8A4B06"),
    (ready_n, "Ready to approve", "✓", "#E8F6F2", "#0B5E52"),
    (len(pending) - ready_n, "Need a closer look", "!", "#FDECEC", "#B42318"),
    (week, "Decided in the last 7 days", "◷", "#E8EEFB", "#1A4FB0"),
])
st.write("")

if not APPROVER:
    who = "Admins look after facts and the brand kit" if role == "Admin" else "Creators send drafts here"
    st.markdown(f'<div class="ap-note lock"><b>View only.</b> {who}; a Manager signs off. Nobody can approve '
                f'their own draft, so every published piece has a second pair of eyes.</div>', unsafe_allow_html=True)

if pending and ss.get("ap_sel") not in [s["id"] for s in pending]:
    ss.ap_sel = pending[0]["id"]

left, right = st.columns([1.05, 2.4], gap="medium")
with left, st.container(key="ap_queue"):
    st.markdown(f'<div class="ap-h"><b>Queue</b><small>{len(pending)} waiting · oldest first</small></div>',
                unsafe_allow_html=True)
    if not pending:
        st.markdown('<div class="ap-empty">✓<b>All caught up</b>New drafts from Review land here.</div>',
                    unsafe_allow_html=True)
    for s in sorted(pending, key=lambda x: x["submitted_at"]):
        r = readiness(s)
        dot = "🟢" if r["ready"] else "🟠"
        lbl = (f"**{s['title']}** {dot} {r['label']} · {theme.full_name(s['author'])} · "
               f"{_age(s['submitted_at'])} · {len(s['findings'])} findings")
        st.button(lbl, key=f"q_{s['id']}", type="primary" if s["id"] == ss.get("ap_sel") else "secondary",
                  width="stretch", on_click=ss.__setitem__, args=("ap_sel", s["id"]))

with right, st.container(key="ap_detail"):
    s = next((x for x in pending if x["id"] == ss.get("ap_sel")), None)
    if not s:
        st.markdown('<div class="ap-empty">☕<b>Nothing to sign off</b>When a creator sends a draft for approval, '
                    'it appears in the queue with everything they decided.</div>', unsafe_allow_html=True)
    else:
        r = readiness(s)
        badge = "ok" if r["ready"] else "warn"
        author = theme.full_name(s["author"])
        st.markdown(
            f'<div class="ap-top"><h3>{html.escape(s["title"])}</h3>'
            f'<span class="ap-badge {badge}">{r["label"]}</span></div>'
            f'<div class="ap-meta"><span class="ap-who"><span class="ap-av">{theme._initials(author)}</span>'
            f'{html.escape(author)}</span><span>Sent {html.escape(_age(s["submitted_at"]))} '
            f'({html.escape(s["submitted_at"])} UTC)</span><span>Version {s["version"]}</span>'
            f'<span>#{html.escape(s["id"])}</span></div>', unsafe_allow_html=True)

        def chk(ok, title, sub):
            return (f'<div class="{"ok" if ok else "warn"}"><i>{"✓" if ok else "!"}</i>'
                    f'<b>{title}</b><small>{sub}</small></div>')
        st.markdown(
            '<div class="ap-checks">'
            + chk(r["open"] == 0, "Every finding decided", f'{len(s["findings"]) - r["open"]} of {len(s["findings"])} decided')
            + chk(r["expired"] == 0, "No expired facts kept",
                  "Expired figures were removed or fixed" if not r["expired"] else f'{r["expired"]} kept by the creator')
            + chk(r["unver"] == 0, "No unsupported claims",
                  "Unverified claims were fixed" if not r["unver"] else f'{r["unver"]} kept without a source')
            + chk(True, "Creator's own wording", f'{r["edited"]} fix(es) rewritten by the creator' if r["edited"]
                  else "All fixes are Inkwise suggestions")
            + '</div>', unsafe_allow_html=True)

        fs = [dict(f, span_text=f.get("span", "")) for f in s["findings"]]
        rh.locate(fs, s["text"])
        img_b = services.submission_image(s["id"])
        if img_b:
            img_fs = [f for f in fs if f.get("where") == "image"]
            st.markdown(f'<div class="ap-lbl">CAMPAIGN IMAGE · {len(img_fs)} FINDING(S)</div>', unsafe_allow_html=True)
            st.image(theme.annotated_image(img_b, img_fs), width="stretch")
        segs, final, _manual = rh.revision(s["text"], fs)
        view = st.radio("Draft view", ["Changes", "Final copy", "Original"], horizontal=True, key=f"ap_view_{s['id']}",
                        label_visibility="collapsed")
        if view == "Final copy":
            st.markdown(f'<div class="iw-text">{html.escape(final)}</div>', unsafe_allow_html=True)
            st.caption(f"{len(final.split())} words · what will be published if you approve")
        elif view == "Original":
            st.markdown(f'<div class="iw-text">{html.escape(s["text"])}</div>', unsafe_allow_html=True)
        else:
            st.markdown(theme.live_html(segs), unsafe_allow_html=True)
            st.markdown(theme.LIVE_LEGEND, unsafe_allow_html=True)

        rows = "".join(
            f'<tr><td><b>{f["n"]}</b></td><td><span class="ap-st {f["status"]}">{f["status"]}</span></td>'
            f'<td>{html.escape(str(f["category"]).replace("_", " "))}{"<br><small>🖼 image</small>" if f.get("where") == "image" else ""}</td>'
            f'<td>“{html.escape(f.get("span", ""))}”<br><small>→ {html.escape(f.get("suggested_fix", ""))}</small></td>'
            f'<td><code>{html.escape(f["source_id"])}</code><br><small>{html.escape(f.get("why", ""))}</small></td></tr>'
            for f in fs)
        st.markdown('<div class="ap-lbl">WHAT THE CREATOR DECIDED</div>'
                    f'<table class="ap-tbl"><tr><th>#</th><th>DECISION</th><th>TYPE</th><th>TEXT → FIX</th>'
                    f'<th>SOURCE</th></tr>{rows}</table>', unsafe_allow_html=True)

        with st.container(key="ap_decide"):
            own = s["author"] == user
            if own:
                st.markdown('<div class="ap-note lock"><b>This is your own draft.</b> Another manager has to sign it off.'
                            '</div>', unsafe_allow_html=True)
            elif APPROVER:
                comment = st.text_area("Comment for the creator", key=f"c_{s['id']}", height=80,
                                       placeholder="Optional when approving. Required when sending back: say what to change.")
                a, b, _sp = st.columns([1.3, 1.3, 2])
                decision = None
                with a:
                    if st.button("✓  Approve and publish", key="ap_ok", type="primary", width="stretch"):
                        decision = ("approved", "Approved")
                with b, st.container(key="ap_back"):
                    if st.button("↩  Send back", key="ap_rj", width="stretch"):
                        decision = ("rejected", "Sent back")
                if decision:
                    status, label = decision
                    if status == "rejected" and not (comment or "").strip():
                        st.error("Add a comment so the creator knows what to change.")
                    else:
                        try:
                            services.decide_submission(s["id"], status, comment, user, role)
                        except Exception as e:
                            st.error(str(e))
                        else:
                            ss.ap_flash = f"{label}: {s['title']}"
                            st.rerun()

st.write("")
with st.container(key="ap_recent"):
    st.markdown(f'<div class="ap-h"><b>Recently decided</b><small>{len(decided)} in total · every decision is in History'
                '</small></div>', unsafe_allow_html=True)
    rows = []
    for d in decided[:8]:
        ok = d["status"] == "approved"
        rows.append(
            f'<tr><td><b>{html.escape(d["title"])}</b></td><td>{html.escape(theme.full_name(d["author"]))}</td>'
            f'<td><span class="ap-badge {"ok" if ok else "bad"}">{"Approved" if ok else "Sent back"}</span></td>'
            f'<td>{html.escape(theme.full_name(d.get("decided_by", "")))}<br><small>{html.escape(_age(d.get("decided_at", "")))}'
            f'</small></td><td><small>{html.escape(d.get("comment") or "—")}</small></td></tr>')
    st.markdown('<table class="ap-tbl"><tr><th>DRAFT</th><th>WRITTEN BY</th><th>DECISION</th><th>DECIDED BY</th>'
                f'<th>COMMENT</th></tr>{"".join(rows)}</table>', unsafe_allow_html=True)

theme.ai_banner()
theme.footer()
