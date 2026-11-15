"""History: every draft that was sent, who decided what, audit reports (PDF / CSV) and an activity timeline."""
import html
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
import pandas as pd
import streamlit as st
import services
import theme

st.set_page_config(page_title="inkwise.ai", page_icon="✒️", layout="wide")
theme.render_shell()
ss = st.session_state

st.markdown("""<style>
.st-key-hs_filters, .st-key-hs_detail, .st-key-hs_timeline { background:#fff; border:1px solid #E2E7F0; border-radius:16px;
  padding:14px 18px; box-shadow:0 1px 2px rgba(20,24,33,.03), 0 8px 24px rgba(20,24,33,.04); }
.st-key-hs_filters [data-testid="stHorizontalBlock"] { align-items:flex-end; }
[class*="st-key-hs_item_"] { background:#fff; border:1px solid #E2E7F0; border-radius:16px; padding:16px 18px 12px;
  box-shadow:0 1px 2px rgba(20,24,33,.03); gap:6px; transition:box-shadow .15s ease, border-color .15s ease; }
[class*="st-key-hs_item_"]:hover { border-color:#CBD8E8; box-shadow:0 8px 24px rgba(20,24,33,.06); }
[class*="st-key-hs_item_sel_"] { border-color:#12917F; box-shadow:inset 3px 0 0 #12917F, 0 8px 24px rgba(18,145,127,.08); }
[class*="st-key-hs_item_"] [data-testid="stPageLink"] a { border:1px solid #CFD8E6 !important; border-radius:8px !important;
  background:#fff !important; justify-content:center; min-height:36px; }
[class*="st-key-hs_item_"] [data-testid="stPageLink"] a p { font-weight:600 !important; color:#1B2A4E !important; font-size:.84rem !important; }
.hs-top { display:flex; align-items:center; gap:10px; }
.hs-top h4 { margin:0 !important; padding:0 !important; font-size:1.02rem !important; color:#1B2A4E !important; flex:1; }
.hs-id { font-size:.74rem; color:#8A93A6; }
.hs-badge { font-size:.7rem; font-weight:700; padding:4px 10px; border-radius:999px; white-space:nowrap; }
.hs-badge.approved { background:#E8F6F2; color:#0B5E52; } .hs-badge.rejected { background:#FDECEC; color:#B42318; }
.hs-badge.pending { background:#FFF4E0; color:#8A4B06; }
.hs-grid { display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; margin:12px 0 8px; }
.hs-grid small { display:block; font-size:.66rem; letter-spacing:.08em; color:#8A93A6; font-weight:700; }
.hs-grid b { font-size:.84rem; color:#1B2A4E; font-weight:600; }
.hs-grid span { display:block; font-size:.74rem; color:#5A6480; }
.hs-chips { display:flex; flex-wrap:wrap; gap:6px; margin:2px 0 8px; }
.hs-chips i { font-style:normal; font-size:.7rem; font-weight:600; padding:2px 9px; border-radius:999px; }
.hs-comment { font-size:.8rem; color:#33415C; background:#F7F8FB; border-radius:10px; padding:8px 10px; margin:0 0 8px; }
.st-key-hs_list .stButton button { min-height:36px; }
.hs-h { display:flex; justify-content:space-between; align-items:baseline; margin:0 0 8px; }
.hs-h b { color:#1B2A4E; font-size:1rem; } .hs-h small { color:#5A6480; font-size:.76rem; }
.hs-day { font-size:.72rem; font-weight:700; color:#1A4FB0; margin:12px 0 4px; }
.hs-ev { display:flex; gap:10px; padding:6px 0; }
.hs-ev i { width:9px; height:9px; border-radius:50%; margin-top:5px; flex:none; }
.hs-ev b { font-size:.8rem; color:#1B2A4E; font-weight:600; display:block; }
.hs-ev small { font-size:.72rem; color:#5A6480; }
.hs-ev .t { margin-left:auto; font-size:.7rem; color:#8A93A6; white-space:nowrap; }
.hs-empty { text-align:center; padding:36px 10px; color:#5A6480; background:#fff; border:1px dashed #CBD3E1; border-radius:16px; }
.hs-empty b { display:block; color:#1B2A4E; font-size:1.02rem; margin-bottom:4px; }
</style>""", unsafe_allow_html=True)

theme.page_header("Audit", "History",
                  "Every draft that was sent: who wrote it, what Inkwise found, who decided and when. "
                  "Download a PDF audit report for any draft, or the whole list as CSV.")

try:
    subs = services.list_submissions()
except services.BackendNotConnected as e:
    theme.not_connected(e)
    st.stop()

NO_FINDINGS = '<i style="background:#E8F6F2;color:#0B5E52">no findings</i>'
STATUS_LABEL = {"approved": "Approved", "rejected": "Sent back", "pending": "Waiting for sign-off"}
NAMES = {**{u: theme.full_name(u) for u in theme.FULL_NAMES}, "inkwise-ai": "Inkwise check", "system": "System"}


def ago(stamp: str) -> str:
    try:
        t = datetime.strptime(stamp[:16], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return stamp
    m = int((datetime.now(timezone.utc) - t).total_seconds() // 60)
    return (f"{max(m, 1)} min ago" if m < 60 else f"{m // 60} h ago" if m < 1440 else
            "yesterday" if m < 2880 else f"{m // 1440} days ago")


n_app = sum(s["status"] == "approved" for s in subs)
n_rej = sum(s["status"] == "rejected" for s in subs)
n_wait = sum(s["status"] == "pending" for s in subs)
theme.stat_cards([
    (len(subs), "Drafts sent for approval", "▤", "#E8EEFB", "#1A4FB0"),
    (n_app, "Approved", "✓", "#E8F6F2", "#0B5E52"),
    (n_rej, "Sent back with a comment", "↩", "#FDECEC", "#B42318"),
    (n_wait, "Waiting for sign-off", "⧗", "#FFF4E0", "#8A4B06"),
])
st.write("")

if not subs:
    st.markdown('<div class="hs-empty"><b>Nothing here yet</b>Drafts appear here once they are sent for approval '
                'from Review.</div>', unsafe_allow_html=True)
    theme.footer()
    st.stop()

with st.container(key="hs_filters"):
    f1, f2, f3, f4 = st.columns([1.6, 1.1, 1.6, 1])
    status = f1.segmented_control("Status", ["All", "Approved", "Sent back", "Waiting"], default="All", key="hs_status")
    people = sorted({s["author"] for s in subs})
    who_opts = ["Everyone"] + [NAMES.get(p, p) for p in people]
    if ss.get("role") == "Creator" and "hs_who" not in ss and NAMES.get(ss.get("user", "")) in who_opts:
        ss.hs_who = NAMES[ss["user"]]                     # a creator's "My drafts" opens on their own drafts
    who = f2.selectbox("Written by", who_opts, key="hs_who")
    query = f3.text_input("Search", key="hs_q", placeholder="Title, person, comment or #id")
    sort = f4.selectbox("Sort by", ["Newest first", "Oldest first", "Most findings"], key="hs_sort")

want = {"Approved": "approved", "Sent back": "rejected", "Waiting": "pending"}.get(status or "All")
rows = []
for s in subs:
    if want and s["status"] != want:
        continue
    if who != "Everyone" and NAMES.get(s["author"], s["author"]) != who:
        continue
    blob = f"#{s['id']} {s['title']} {NAMES.get(s['author'], s['author'])} {NAMES.get(s['decided_by'], '')} {s['comment']}".lower()
    if query and not all(w in blob for w in query.lower().split()):
        continue
    rows.append(s)
key = {"Newest first": lambda s: s["updated_at"], "Oldest first": lambda s: s["updated_at"],
       "Most findings": lambda s: len(s["findings"])}[sort]
rows.sort(key=key, reverse=sort != "Oldest first")

if rows and ss.get("hs_sel") not in [r["id"] for r in rows]:
    ss.hs_sel = rows[0]["id"]

left, right = st.columns([2.1, 1], gap="medium")

with left:
    st.markdown(f'<div class="hs-h" style="margin-top:6px"><b>Drafts</b><small>{len(rows)} of {len(subs)} shown</small></div>',
                unsafe_allow_html=True)
    if not rows:
        st.markdown('<div class="hs-empty"><b>No drafts match</b>Clear the search or pick another status.</div>',
                    unsafe_allow_html=True)
    shown = rows[: ss.get("hs_limit", 8)]
    with st.container(key="hs_list"):
        for s in shown:
            fs = s["findings"]
            cnt = {k: sum(f["status"] == k for f in fs) for k in ("accepted", "edited", "rejected", "open")}
            img = sum(f.get("where") == "image" for f in fs)
            decided = (f"<b>{html.escape(NAMES.get(s['decided_by'], s['decided_by']))}</b>"
                       f"<span>{html.escape(ago(s['decided_at']))}</span>" if s["decided_by"] else
                       "<b>—</b><span>not decided yet</span>")
            sel = " sel" if s["id"] == ss.get("hs_sel") else ""
            card = st.container(key=f"hs_item_{'sel_' if sel else ''}{s['id']}")
            chips = "".join(f'<i style="background:{bg};color:{fg}">{n} {lbl}</i>' for n, lbl, bg, fg in [
                (cnt["accepted"], "accepted", "#E8F6F2", "#0B5E52"), (cnt["edited"], "edited", "#E8EEFB", "#1A4FB0"),
                (cnt["rejected"], "rejected", "#F3F5F9", "#5A6480"), (cnt["open"], "open", "#FFF4E0", "#8A4B06")] if n)
            card.markdown(
                f'<div class="hs-card"><div class="hs-top"><span class="hs-badge {s["status"]}">'
                f'{STATUS_LABEL.get(s["status"], s["status"])}</span><h4>{html.escape(s["title"])}</h4>'
                f'<span class="hs-id">#{html.escape(s["id"])} · v{s["version"]}</span></div>'
                f'<div class="hs-grid">'
                f'<div><small>WRITTEN BY</small><b>{html.escape(NAMES.get(s["author"], s["author"]))}</b>'
                f'<span>{html.escape(ago(s["submitted_at"]))}</span></div>'
                f'<div><small>INKWISE CHECK</small><b>{len(fs)} finding(s)</b>'
                f'<span>{f"{img} in the image" if img else "copy only"}</span></div>'
                f'<div><small>DECIDED BY</small>{decided}</div>'
                f'<div><small>LAST UPDATE</small><b>{html.escape(s["updated_at"][11:16] or "")} UTC</b>'
                f'<span>{html.escape(s["updated_at"][:10])}</span></div></div>'
                f'<div class="hs-chips">{chips or NO_FINDINGS}</div>'
                + (f'<div class="hs-comment">💬 {html.escape(s["comment"])}</div>' if s["comment"] else "")
                + '</div>', unsafe_allow_html=True)
            b1, b2, _ = card.columns([1, 1, 2.4])
            b1.button("Open details", key=f"hs_open_{s['id']}", type="primary" if sel else "secondary",
                      width="stretch", on_click=ss.__setitem__, args=("hs_sel", s["id"]))
            if s["status"] == "pending" and theme.can_open("pages/Approvals.py", ss.get("role", "")):
                try:
                    b2.page_link("pages/Approvals.py", label="Go to Approvals", width="stretch")
                except Exception:
                    pass
    if len(rows) > len(shown):
        st.button(f"Show {min(8, len(rows) - len(shown))} more", key="hs_more",
                  on_click=ss.__setitem__, args=("hs_limit", ss.get("hs_limit", 8) + 8))
    if rows:
        df = pd.DataFrame([{
            "ID": s["id"], "Title": s["title"], "Written by": NAMES.get(s["author"], s["author"]),
            "Sent (UTC)": s["submitted_at"], "Status": STATUS_LABEL.get(s["status"], s["status"]),
            "Decided by": NAMES.get(s["decided_by"], s["decided_by"]), "Decided at (UTC)": s["decided_at"],
            "Findings": len(s["findings"]), "Comment": s["comment"]} for s in rows])
        st.download_button("⬇  Download this list as CSV", df.to_csv(index=False).encode("utf-8"),
                           file_name="inkwise_history.csv", mime="text/csv", key="hs_csv")

with right:
    s = next((x for x in rows if x["id"] == ss.get("hs_sel")), None)
    with st.container(key="hs_detail"):
        if not s:
            st.markdown('<div class="hs-h"><b>Audit report</b><small>pick a draft</small></div>', unsafe_allow_html=True)
        else:
            trail = services.draft_history(s["id"])
            st.markdown(f'<div class="hs-h"><b>Audit report · #{html.escape(s["id"])}</b>'
                        f'<small>{STATUS_LABEL.get(s["status"], "")}</small></div>'
                        f'<div style="font-size:.84rem;color:#33415C;margin-bottom:8px">{html.escape(s["title"])}</div>',
                        unsafe_allow_html=True)
            try:
                import report_pdf
                pdf = report_pdf.build(s, trail, NAMES)
                st.download_button("⬇  Download audit report (PDF)", pdf, file_name=f"inkwise_audit_{s['id']}.pdf",
                                   mime="application/pdf", type="primary", width="stretch", key="hs_pdf")
            except Exception as e:                   # PyMuPDF missing: say so, keep the page working
                st.caption(f"PDF report unavailable here ({type(e).__name__}); the CSV still works.")
            with st.expander("Text as submitted"):
                st.write(s["text"])
            for f in s["findings"]:
                st.markdown(f'<div style="font-size:.78rem;color:#33415C;margin:3px 0">'
                            f'<b>{html.escape(str(f["status"]).title())}</b> · <code>{html.escape(f["source_id"])}</code>'
                            f' · “{html.escape(f["span"][:60])}”</div>', unsafe_allow_html=True)

    st.write("")
    with st.container(key="hs_timeline"):
        try:
            events = services.global_audit(40)
        except Exception:
            events = []
        events = [e for e in events if e["action"] not in ("signed_in", "seeded")][:14]
        st.markdown('<div class="hs-h"><b>Activity timeline</b><small>latest across the workspace</small></div>',
                    unsafe_allow_html=True)
        COL = {"approved": "#12917F", "changes_requested": "#D93025", "finding_rejected": "#8A93A6",
               "fact_renewed": "#6B2FA3", "reviewed": "#1A73E8"}
        VERB = {"created": "created", "reviewed": "checked", "finding_accepted": "accepted a finding in",
                "finding_edited": "edited a fix in", "finding_rejected": "rejected a finding in", "approved": "approved",
                "changes_requested": "sent back", "fact_renewed": "renewed a fact", "rechecked": "re-checked",
                "guideline_reworded": "reworded a guideline", "new_version": "saved a new version of"}
        out, day = [], None
        for e in events:
            d = e["at"][:10]
            if d != day:
                day = d
                try:
                    label = datetime.strptime(d, "%Y-%m-%d").strftime("%a %d %b %Y")
                except ValueError:
                    label = d
                out.append(f'<div class="hs-day">{label}</div>')
            who = "Inkwise" if e["user"] == "inkwise-ai" else NAMES.get(e["user"], e["user"])
            out.append(f'<div class="hs-ev"><i style="background:{COL.get(e["action"], "#B45309")}"></i><div>'
                       f'<b>{html.escape(who)} {html.escape(VERB.get(e["action"], e["action"].replace("_", " ")))}</b>'
                       f'<small>{html.escape(e.get("title") or e.get("detail") or "")}</small></div>'
                       f'<span class="t">{html.escape(e["at"][11:16])}</span></div>')
        st.markdown("".join(out) or '<div class="hs-empty">No activity yet.</div>', unsafe_allow_html=True)

theme.footer()
