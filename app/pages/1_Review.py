import html
import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
import streamlit as st
import services
import theme
import voice_input
import review_helpers as rh

InputError = getattr(services, "InputError", ())

st.set_page_config(page_title="inkwise.ai", layout="wide")
theme.render_shell()
ss = st.session_state
STATUS_CLS = {"open": "open", "accepted": "ok", "edited": "ok", "rejected": "bad"}
ss.setdefault("rv_findings", None)
ss.setdefault("rv_ai_error", None)
ss.setdefault("rv_voice_error", None)


def set_status(fid, status):
    for f in ss.rv_findings:
        if f["id"] == fid:
            f["status"] = status


def toggle_edit(fid):
    ss[f"editing_{fid}"] = not ss.get(f"editing_{fid}", False)


def save_edit(fid):
    for f in ss.rv_findings:
        if f["id"] == fid:
            f["suggested_fix"], f["status"] = ss[f"edit_{fid}"], "edited"
    ss[f"editing_{fid}"] = False


def transcribe_voice():
    audio = ss.get("rv_voice")
    if audio is None:
        return
    try:
        ss.rv_text = f'{ss.get("rv_text", "")} {voice_input.transcribe(audio.getvalue(), audio.type or "audio/wav")}'.strip()
        ss.rv_voice_error = None
    except Exception as e:
        ss.rv_voice_error = f"Could not transcribe ({type(e).__name__}). Try again or type instead."


def review_image_cb():
    """Gallery image -> services.review_image() (services only, no voice_input)."""
    img = ss.get("rv_image")
    if img is None:
        ss.rv_voice_error = "Choose an image first."
        return
    try:
        # ASSUMPTION: review_image(image_bytes, mime_type). Check the signature in services.py.
        result = services.review_image(img.getvalue(), img.type or "image/png")
        if isinstance(result, dict):
            raw = result.get("findings", [])
            ai_error = result.get("ai_error")
            text = result.get("text") or result.get("extracted_text") or ""
        else:
            raw, ai_error, text = result, None, ""
        text = text or ss.get("rv_text", "")
        ss.rv_text = text                      # allowed: we are inside a callback
        ss.rv_reviewed_text, ss.rv_ai_error = text, ai_error or None
        ss.rv_findings = rh.locate(raw, text)
        ss.rv_voice_error = None
    except InputError as e:
        ss.rv_voice_error = str(e)
    except services.BackendNotConnected as e:
        ss.rv_voice_error = str(e)
    except Exception as e:
        ss.rv_voice_error = f"Could not review the image ({type(e).__name__}). Try another image or type instead."


def fact_index() -> dict:
    """{"F01": {...fact...}} from services.get_knowledge_base(), loaded once per session."""
    if "fact_idx" not in ss:
        try:
            ss.fact_idx = {x["id"]: x for x in services.get_knowledge_base()["facts"]}
        except Exception:
            ss.fact_idx = {}
    return ss.fact_idx


def render_row(f):
    fid = f["id"]
    editing = ss.get(f"editing_{fid}", False)
    span = str(f["span_text"])
    short = (span if len(span) <= 40 else span[:37] + "...").replace("[", "\\[").replace("*", "\\*").replace("_", "\\_")

    fact = fact_index().get(f["source_id"])
    state, days = rh.expiry_state(f, fact)
    flag = " · EXPIRED" if state == "expired" else " · EXPIRING" if state == "expiring" else ""
    owner = f.get("owner") or (fact or {}).get("owner", "")

    with st.expander(f'{f["n"]} · {str(f["category"]).replace("_", " ")} · “{short}” · {f["source_id"]} · {f["status"]}{flag}', expanded=editing):
        st.markdown(
            f'{theme.checker_tag(f["checked_by"])} '
            f'<span class="iw-pill {STATUS_CLS.get(f["status"], "open")}">{html.escape(f["status"])}</span> '
            f'{rh.badge_html(state, days)}',
            unsafe_allow_html=True,
        )
        n_occ = len(f.get("occurrences") or [])
        if n_occ > 1:
            st.caption(f"Appears {n_occ} times in your text. All are highlighted above.")
        if f["why"]:
            st.markdown(f"**Why:** {f['why']}")
        if f["source_text"]:
            st.markdown(rh.quote_html(f["source_text"], f["source_id"], owner, rh.evidence_terms(f)),
                        unsafe_allow_html=True)
        else:
            theme.source_quote(f["source_text"], f["source_id"], owner)
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
            b1.button("Accept", key=f"acc_{fid}", on_click=set_status, args=(fid, "accepted"), type="primary", width="stretch")
            b2.button("Edit", key=f"edt_{fid}", on_click=toggle_edit, args=(fid,), width="stretch")
            b3.button("Reject", key=f"rej_{fid}", on_click=set_status, args=(fid, "rejected"), width="stretch")


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
    st.audio_input("Dictate", key="rv_voice", on_change=transcribe_voice, help="Tap the mic, speak, then stop. The text is added above and you can edit it.")
    st.file_uploader("Image from gallery", type=["png", "jpg", "jpeg"], key="rv_image", help="Upload a poster, screenshot or product photo, then tap Review image.")
    st.button("Review image", key="rv_image_btn", on_click=review_image_cb, width="stretch", disabled=not review_ready)
    if ss.rv_voice_error:
        st.warning(ss.rv_voice_error)
    if st.button("Run review", type="primary", width="stretch", disabled=not review_ready):
        try:
            with st.spinner("Checking against your brand kit..."):
                result = services.review_text_full(ss.rv_text)
                ss.rv_reviewed_text, ss.rv_ai_error = ss.rv_text, result["ai_error"]
                ss.rv_findings = rh.locate(result["findings"], ss.rv_reviewed_text)
        except InputError as e:            # empty or too long text
            st.warning(str(e))
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
            theme.metric_row([(len(findings), "Total", ""), (n_open, "Open", "warn" if n_open else ""), (n_ok, "Done", "ok"), (n_rej, "Rejected", "")])
            st.markdown('<div class="iw-section">Your text</div>', unsafe_allow_html=True)
            # every occurrence of every finding, not just the first one
            st.markdown(theme.highlight_html(ss.rv_reviewed_text, rh.highlight_items(findings)), unsafe_allow_html=True)
            st.caption("Red: claim or expired fact. Amber: tone or terminology. Purple: accessibility.")
            st.markdown('<div class="iw-section">Findings</div>', unsafe_allow_html=True)
            for f in findings:
                render_row(f)
            if n_open:
                st.caption(f"Decide on {n_open} open finding(s) to send this for approval.")
            if st.button("Send for approval", type="primary", disabled=n_open > 0):
                try:
                    services.submit_for_approval(ss.get("rv_title") or "Untitled review", ss.rv_reviewed_text, findings, ss.user)
                    ss.rv_findings, ss.rv_ai_error = None, None
                    st.toast("Sent to Approvals")
                    st.success("Sent for approval.")
                    st.page_link("pages/Approvals.py", label="Go to Approvals")
                except services.BackendNotConnected as e:
                    theme.not_connected(e)

theme.ai_banner()