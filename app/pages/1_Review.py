import html
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
import streamlit as st
import services
import theme

st.set_page_config(page_title="inkwise.ai", layout="wide")
theme.render_shell()
ss = st.session_state

STATUS_CLS = {"open": "open", "accepted": "ok", "edited": "ok", "rejected": "bad"}

ss.setdefault("rv_findings", None)
ss.setdefault("rv_ai_error", None)


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


def locate(findings, text):
    lowered = text.lower()
    for f in findings:
        span = f.get("span_text") or ""
        if f.get("start") is None or f.get("end") is None:
            idx = text.find(span) if span else -1
            if idx < 0 and span:
                idx = lowered.find(span.lower())
            if idx >= 0:
                f["start"], f["end"] = idx, idx + len(span)
            else:
                f["start"], f["end"] = None, None
    findings.sort(key=lambda x: (x["start"] is None, x["start"] or 0))
    for n, f in enumerate(findings, 1):
        f["n"] = n
    return findings


def render_row(f):
    fid = f["id"]
    editing = ss.get(f"editing_{fid}", False)
    category = str(f["category"]).replace("_", " ")
    span = str(f["span_text"])
    short = span if len(span) <= 40 else span[:37] + "..."
    short = short.replace("[", "\\[").replace("*", "\\*").replace("_", "\\_")
    label = f'{f["n"]} · {category} · “{short}” · {f["source_id"]} · {f["status"]}'
    with st.expander(label, expanded=editing):
        st.markdown(
            f'{theme.checker_tag(f["checked_by"])} '
            f'<span class="iw-pill {STATUS_CLS.get(f["status"], "open")}">{html.escape(f["status"])}</span>',
            unsafe_allow_html=True,
        )
        if f["why"]:
            st.markdown(f"**Why:** {f['why']}")
        theme.source_quote(f["source_text"], f["source_id"], f.get("owner", ""))
        if f["suggested_fix"] and not editing:
            st.markdown(f"**Suggested fix:** {f['suggested_fix']}")
        if f["checked_by"] == "ai":
            conf = min(max(float(f["confidence"]), 0.0), 1.0)
            st.progress(conf, text=f"Confidence {int(conf * 100)}%")

        if editing:
            st.text_area("Your version", value=f["suggested_fix"], key=f"edit_{fid}")
            st.button("Save edit", key=f"save_{fid}", on_click=save_edit, args=(fid,), type="primary")
        else:
            b1, b2, b3, _ = st.columns([1, 1, 1, 3])
            b1.button("Accept", key=f"acc_{fid}", on_click=set_status, args=(fid, "accepted"),
                      type="primary", width="stretch")
            b2.button("Edit", key=f"edt_{fid}", on_click=toggle_edit, args=(fid,),
                      width="stretch")
            b3.button("Reject", key=f"rej_{fid}", on_click=set_status, args=(fid, "rejected"),
                      width="stretch")


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
    run = st.button("Run review", type="primary", width="stretch", disabled=not review_ready)
    if run:
        if not ss.rv_text.strip():
            st.warning("Paste some text first, then run the review.")
        else:
            try:
                with st.spinner("Checking against your brand kit..."):
                    result = services.review_text_full(ss.rv_text)
                    ss.rv_reviewed_text = ss.rv_text
                    ss.rv_ai_error = result["ai_error"]
                    ss.rv_findings = locate(result["findings"], ss.rv_reviewed_text)
            except services.BackendNotConnected as e:
                theme.not_connected(e)
            except Exception as e:
                st.error(f"The review could not finish ({type(e).__name__}: {e}). Try again in a moment.")

with right:
    findings = ss.rv_findings
    if findings is None:
        theme.empty_state("Findings appear here after you run a review.")
    else:
        if ss.rv_ai_error:
            st.warning("AI review unavailable, rule checks only.")
        if not findings:
            st.success("No issues found. This text matches your brand kit.")
        else:
            n_open = sum(f["status"] == "open" for f in findings)
            n_ok = sum(f["status"] in ("accepted", "edited") for f in findings)
            n_rej = sum(f["status"] == "rejected" for f in findings)
            theme.metric_row([
                (len(findings), "Total", ""),
                (n_open, "Open", "warn" if n_open else ""),
                (n_ok, "Done", "ok"),
                (n_rej, "Rejected", ""),
            ])

            st.markdown('<div class="iw-section">Your text</div>', unsafe_allow_html=True)
            located = [f for f in findings if f["start"] is not None]
            st.markdown(theme.highlight_html(ss.rv_reviewed_text, located), unsafe_allow_html=True)
            st.caption("Red: claim or expired fact. Amber: tone or terminology. Blue: accessibility.")

            st.markdown('<div class="iw-section">Findings</div>', unsafe_allow_html=True)
            for f in findings:
                render_row(f)

            if n_open:
                st.caption(f"Decide on {n_open} open finding(s) to send this for approval.")
            if st.button("Send for approval", type="primary", disabled=n_open > 0):
                title = ss.get("rv_title") or "Untitled review"
                try:
                    services.submit_for_approval(title, ss.rv_reviewed_text, findings, ss.user)
                    ss.rv_findings = None
                    ss.rv_ai_error = None
                    st.toast("Sent to Approvals")
                    st.success("Sent for approval.")
                    st.page_link("pages/Approvals.py", label="Go to Approvals")
                except services.BackendNotConnected as e:
                    theme.not_connected(e)

theme.ai_banner()