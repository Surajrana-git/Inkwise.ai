import html
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
import streamlit as st
import services
import theme

st.set_page_config(page_title="inkwise.ai", page_icon="✒️", layout="wide")
theme.render_shell()
ss = st.session_state

STATUS_CLS = {"open": "open", "accepted": "ok", "edited": "ok", "rejected": "bad"}

ss.setdefault("rv_findings", None)   # None = review not run yet


# ---------- callbacks ----------
def set_status(fid, status):
    for f in ss.rv_findings:
        if f["id"] == fid:
            f["status"] = status


def toggle_edit(fid):
    ss[f"editing_{fid}"] = not ss.get(f"editing_{fid}", False)


def save_edit(fid):
    for f in ss.rv_findings:
        if f["id"] == fid:
            f["suggested_fix"] = ss[f"edit_{fid}"]
            f["status"] = "edited"
    ss[f"editing_{fid}"] = False


def pill(text, cls):
    return f'<span class="iw-pill {cls}">{html.escape(str(text))}</span>'


def render_card(f):
    fid = f["id"]
    with st.container(border=True):
        src_cls = "bad" if f["source_id"] == "UNVERIFIED" else "ok"
        by = "Rule check" if f["checked_by"] == "rule" else "AI"
        st.markdown(
            f'{pill(f["category"].replace("_", " "), "open")} {pill(f["source_id"], src_cls)} '
            f'{pill(f["status"], STATUS_CLS.get(f["status"], "open"))} {pill(by, "ok")}',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="margin:8px 0"><mark style="background:#FFE6B8;padding:1px 6px;'
            f'border-radius:4px">{html.escape(f["span"])}</mark></div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**Why:** {f['why']}")
        st.caption(f"Source: {f['source_text']}")
        st.markdown(f"**Suggested fix:** {f['suggested_fix']}")
        st.progress(min(max(float(f["confidence"]), 0.0), 1.0),
                    text=f"Confidence {int(float(f['confidence']) * 100)}%")

        if ss.get(f"editing_{fid}"):
            st.text_area("Your version", value=f["suggested_fix"], key=f"edit_{fid}")
            st.button("Save edit", key=f"save_{fid}", on_click=save_edit, args=(fid,), type="primary")
        else:
            b1, b2, b3, _ = st.columns([1, 1, 1, 3])
            b1.button("Accept", key=f"acc_{fid}", on_click=set_status, args=(fid, "accepted"),
                      use_container_width=True)
            b2.button("Edit", key=f"edt_{fid}", on_click=toggle_edit, args=(fid,),
                      use_container_width=True)
            b3.button("Reject", key=f"rej_{fid}", on_click=set_status, args=(fid, "rejected"),
                      use_container_width=True)


# ---------- page ----------
st.title("Review")
st.caption("Paste your content, decide on each finding, then send it for approval.")

review_ready = True
try:
    services.check("review")
except services.BackendNotConnected as e:
    review_ready = False
    theme.not_connected(e)

left, right = st.columns([1, 1.3], gap="large")

with left:
    st.text_input("Title", key="rv_title", placeholder="e.g. Spring launch email")
    st.text_area("Your content", key="rv_text", height=280, placeholder="Paste your text here...")
    run = st.button("Run review", type="primary", use_container_width=True, disabled=not review_ready)
    if run:
        if not ss.rv_text.strip():
            st.warning("Paste some text first, then run the review.")
        else:
            try:
                with st.spinner("Checking against your brand kit..."):
                    ss.rv_findings = services.review_text(ss.rv_text)
                    ss.rv_reviewed_text = ss.rv_text
            except services.BackendNotConnected as e:
                theme.not_connected(e)
            except Exception as e:
                st.error(f"The review could not finish ({type(e).__name__}: {e}). Try again in a moment.")

with right:
    findings = ss.rv_findings
    if findings is None:
        st.info("Findings appear here after you run a review.")
    elif not findings:
        st.success("No issues found. This text matches your brand kit.")
    else:
        n_open = sum(f["status"] == "open" for f in findings)
        n_ok = sum(f["status"] in ("accepted", "edited") for f in findings)
        n_rej = sum(f["status"] == "rejected" for f in findings)
        m = st.columns(4)
        m[0].metric("Findings", len(findings))
        m[1].metric("Open", n_open)
        m[2].metric("Accepted", n_ok)
        m[3].metric("Rejected", n_rej)

        for f in findings:
            render_card(f)

        if n_open:
            st.caption(f"Decide on {n_open} open finding(s) to send this for approval.")
        if st.button("Send for approval", type="primary", disabled=n_open > 0):
            title = ss.get("rv_title") or "Untitled review"
            try:
                services.submit_for_approval(title, ss.rv_reviewed_text, findings, ss.user)
                ss.rv_findings = None
                st.toast("Sent to Approvals", icon="✅")
                st.success("Sent for approval.")
                st.page_link("pages/Approvals.py", label="Go to Approvals", icon="✅")
            except services.BackendNotConnected as e:
                theme.not_connected(e)

theme.ai_banner()