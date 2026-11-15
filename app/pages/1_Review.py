import html
import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
import streamlit as st
import services
import theme
try:  # optional: dictation needs app/voice_input.py; the page must work without it
    import voice_input
except ImportError:
    voice_input = None
import review_helpers as rh

InputError = getattr(services, "InputError", ())

st.set_page_config(page_title="inkwise.ai", layout="wide")
theme.render_shell()
ss = st.session_state
STATUS_CLS = {"open": "open", "accepted": "ok", "edited": "ok", "rejected": "bad"}
ss.setdefault("rv_findings", None)
ss.setdefault("rv_ai_error", None)
ss.setdefault("rv_voice_error", None)
if ss.get("rv_flash"):
    st.toast(ss.pop("rv_flash"))


VERB = {"accepted": "✓ Accepted", "edited": "✎ Edited", "rejected": "✕ Rejected"}


def _focus_next(fid):
    """After a decision, open the next undecided finding so the creator can click straight through."""
    open_ids = [f["id"] for f in ss.rv_findings if f["status"] == "open"]
    later = [i for i in open_ids if i > fid] or open_ids
    ss.rv_focus = later[0] if later else None


def set_status(fid, status):
    for f in ss.rv_findings:
        if f["id"] == fid:
            f["status"] = status
            ss.rv_flash = f"{VERB.get(status, status)}: finding {f.get('n', '')} ({f['source_id']}). Logged when you send it."
    _focus_next(fid)


def toggle_edit(fid):
    ss[f"editing_{fid}"] = not ss.get(f"editing_{fid}", False)


def save_edit(fid):
    for f in ss.rv_findings:
        if f["id"] == fid:
            f["suggested_fix"], f["status"] = ss[f"edit_{fid}"], "edited"
            ss.rv_flash = f"✎ Edited: finding {f.get('n', '')} ({f['source_id']}) now uses your wording."
    ss[f"editing_{fid}"] = False
    _focus_next(fid)


def use_revised(text):
    ss.rv_text = text                      # allowed: we are inside a callback
    ss.rv_findings, ss.rv_focus = None, None
    ss.rv_flash = "Revised copy moved into the editor. Run the check again to confirm it is clean."


def transcribe_voice():
    audio = ss.get("rv_voice")
    if audio is None:
        return
    try:
        ss.rv_text = f'{ss.get("rv_text", "")} {voice_input.transcribe(audio.getvalue(), audio.type or "audio/wav")}'.strip()
        ss.rv_voice_error = None
    except Exception as e:
        ss.rv_voice_error = f"Could not transcribe ({type(e).__name__}). Try again or type instead."


SAMPLE_BANNER = Path(__file__).resolve().parents[1] / "assets" / "sample_banner.png"


def image_uploaded():
    up = ss.get(f"rv_image_{ss.get('rv_up_n', 0)}")
    if up is not None:
        ss.rv_img_bytes, ss.rv_img_name = up.getvalue(), up.name


def use_sample_banner():
    ss.rv_img_bytes, ss.rv_img_name = SAMPLE_BANNER.read_bytes(), "Sample banner (Diwali launch)"


def remove_image():
    ss.rv_img_bytes, ss.rv_img_name = None, None
    ss.rv_up_n = ss.get("rv_up_n", 0) + 1          # a new key empties the uploader


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

    mark = VERB.get(f["status"], "○ Open") + (" · 🖼 image" if f.get("where") == "image" else "")
    with st.expander(f'{mark} · {f["n"]} · {str(f["category"]).replace("_", " ")} · “{short}” · {f["source_id"]}{flag}',
                     expanded=editing or ss.get("rv_focus") == fid):
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


theme.page_header("Pre-publication check", "Check a draft before it goes live",
                  "Inkwise checks your copy against Lumora's approved facts, glossary and guidelines. "
                  "Every finding shows the source it relies on, and you decide what changes.")

theme.journey()

review_ready = True
try:
    services.check("review")
except services.BackendNotConnected as e:
    review_ready = False
    theme.not_connected(e)

st.markdown("""<style>
.st-key-rv_samples [data-testid="stHorizontalBlock"] { gap:8px !important; flex-wrap:wrap; }
.st-key-rv_samples [data-testid="stColumn"] { flex:0 0 auto !important; width:auto !important; min-width:0 !important; }
.st-key-rv_samples button { border-radius:999px !important; background:#fff !important; border:1px solid #E2E7F0 !important;
  padding:6px 14px 6px 28px !important; min-height:34px !important; position:relative; }
.st-key-rv_samples button p { font-size:.8rem !important; font-weight:600 !important; color:#1B2A4E !important; white-space:nowrap; }
.st-key-rv_samples button:hover { border-color:#12917F !important; }
.st-key-rv_samples button::before { content:""; position:absolute; left:12px; top:50%; transform:translateY(-50%);
  width:8px; height:8px; border-radius:50%; background:var(--dot,#B45309); }
.st-key-smp_launch button { --dot:#D93025; } .st-key-smp_fees button { --dot:#D93025; }
.st-key-smp_update button { --dot:#B45309; } .st-key-smp_clean button { --dot:#12917F; }
.st-key-rv_draft, .st-key-rv_results { background:#fff; border:1px solid #E2E7F0; border-radius:16px; padding:18px 20px 16px;
  box-shadow:0 1px 2px rgba(20,24,33,.03), 0 8px 24px rgba(20,24,33,.04); }
.rv-h { display:flex; align-items:center; justify-content:space-between; margin-bottom:6px; }
.rv-h b { font-size:1rem; color:#1B2A4E; } .rv-h small { color:#5A6480; font-size:.76rem; }
.rv-chips { display:flex; flex-wrap:wrap; gap:6px; margin:2px 0 10px; }
.rv-chip { font-size:.7rem; font-weight:600; padding:3px 9px; border-radius:999px; background:#F3F5F9; color:#33415C; }
.rv-chip.ok { background:#E8F6F2; color:#0B5E52; }
.rv-count { text-align:right; font-size:.72rem; color:#8A93A6; margin:-6px 0 6px; }
.rv-bundle { border:1px dashed #CBD3E1; border-radius:12px; padding:10px 12px 4px; margin:6px 0 12px; background:#FAFBFC; }
.rv-bundle .lbl { font-size:.66rem; letter-spacing:.14em; font-weight:700; color:#8A93A6; }
.rv-bundle b { display:block; color:#1B2A4E; font-size:.86rem; margin:2px 0 0; }
.rv-checks { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:6px; }
.rv-checks div { border:1px solid #EEF0F4; border-radius:12px; padding:12px; background:#FCFCFD; }
.rv-checks b { display:block; color:#1B2A4E; font-size:.86rem; } .rv-checks small { color:#5A6480; font-size:.76rem; line-height:1.4; }
.rv-checks i { font-style:normal; font-size:.62rem; font-weight:700; letter-spacing:.08em; padding:2px 7px; border-radius:999px;
  display:inline-block; margin-bottom:6px; }
.rv-sum { display:flex; gap:10px; flex-wrap:wrap; margin:2px 0 12px; }
.rv-sum div { flex:1; min-width:110px; border-radius:12px; padding:10px 12px; }
.rv-sum b { display:block; font-size:1.35rem; line-height:1.1; } .rv-sum small { font-size:.72rem; }
.rv-sum div.done { opacity:.55; } .rv-sum s { opacity:.6; font-size:.8rem; margin-left:4px; text-decoration:none; }
.st-key-rv_view [role="radiogroup"] { gap:4px; }
</style>""", unsafe_allow_html=True)


def load_sample(sample):
    ss.rv_text = sample["text"]
    ss.rv_title = sample["title"].split(" (")[0]


samples = services.demo_samples() if hasattr(services, "demo_samples") else []
if samples:
    st.markdown('<div style="font-size:.78rem;color:#5A6480;margin:-4px 0 6px">Start from a sample draft:</div>',
                unsafe_allow_html=True)
    with st.container(key="rv_samples"):
        for scol, smp in zip(st.columns(len(samples)), samples):
            nice = smp["title"].replace(" (", " · ").rstrip(")")
            scol.button(nice, key=f"smp_{smp['id']}", on_click=load_sample, args=(smp,))
st.write("")

try:
    kb = services.get_knowledge_base()
    kit = f"{len(kb['guidelines'])} guidelines · {len(kb['facts'])} facts · {len(kb['glossary'])} terms"
except Exception:
    kit = "brand kit"

left, right = st.columns([1.05, 1], gap="large")

with left, st.container(key="rv_draft"):
    st.markdown('<div class="rv-h"><b>Draft</b><small>Lumora brand kit · ' + html.escape(kit) + '</small></div>'
                '<div class="rv-chips"><span class="rv-chip ok">● Personal data masked before AI</span>'
                '<span class="rv-chip">Synthetic demo brand</span></div>', unsafe_allow_html=True)
    t1, t2 = st.columns([1.6, 1])
    t1.text_input("Campaign title", key="rv_title", placeholder="e.g. Diwali launch post")
    t2.selectbox("Channel", ["Social post", "Email", "Push notification", "Web page", "Paid ad"], key="rv_channel")
    st.text_area("Copy to check", key="rv_text", height=230,
                 placeholder="Paste the copy you want to publish, or pick a sample draft above.")
    txt = ss.get("rv_text") or ""
    st.markdown(f'<div class="rv-count">{len(txt.split())} words · {len(txt):,} / 12,000 characters</div>',
                unsafe_allow_html=True)
    if voice_input is not None:
        st.audio_input("Dictate", key="rv_voice", on_change=transcribe_voice,
                       help="Tap the mic, speak, then stop. The text is added above and you can edit it.")
    st.markdown('<div class="rv-bundle"><span class="lbl">ONE CAMPAIGN · TEXT AND IMAGE</span>'
                '<b>Add the creative for this campaign (optional)</b></div>', unsafe_allow_html=True)
    if ss.get("rv_img_bytes"):
        c_img, c_meta = st.columns([1.3, 1])
        c_img.image(ss.rv_img_bytes, width="stretch")
        c_meta.markdown(f'<div style="font-size:.8rem;color:#1B2A4E;font-weight:600">{html.escape(ss.rv_img_name or "Image")}'
                        f'</div><div style="font-size:.74rem;color:#5A6480;margin:2px 0 8px">'
                        f'{len(ss.rv_img_bytes) / 1024:,.0f} KB · checked with the copy: brand colours, readable text, '
                        f'and the copy rules on any words in the image</div>', unsafe_allow_html=True)
        c_meta.button("Remove image", key="rv_img_rm", on_click=remove_image)
    else:
        u1, u2 = st.columns([2.2, 1], vertical_alignment="center")
        u1.file_uploader("Image", type=["png", "jpg", "jpeg"], key=f"rv_image_{ss.get('rv_up_n', 0)}",
                         label_visibility="collapsed", on_change=image_uploaded,
                         help="A poster, banner or social image, up to 5 MB.")
        u2.button("Use sample banner", key="rv_img_sample", on_click=use_sample_banner, width="stretch")
    if ss.rv_voice_error:
        st.warning(ss.rv_voice_error)
    has_img = bool(ss.get("rv_img_bytes"))
    label = "Run pre-publication check" + (" · copy + image" if has_img and txt.strip() else
                                           " · image only" if has_img else "")
    run = st.button(label, key="rv_run", type="primary", width="stretch",
                    disabled=not review_ready or not (txt.strip() or has_img))
    if run:
        try:
            with st.spinner("Checking against the Lumora brand kit..."):
                found, errors = [], []
                if txt.strip():
                    result = services.review_text_full(ss.rv_text)
                    found += result["findings"]
                    errors.append(result["ai_error"])
                ss.rv_img_result = None
                if has_img:
                    img_res = services.review_image(ss.rv_img_bytes, "image")
                    found += img_res["findings"]
                    errors.append(img_res["ai_error"])
                    ss.rv_img_result = {k: img_res[k] for k in ("text", "lines", "stored", "ai_error")}
                    ss.rv_img_result["bytes"] = ss.rv_img_bytes
                ss.rv_reviewed_text = ss.rv_text if txt.strip() else ""
                ss.rv_ai_error = "\n".join(dict.fromkeys(e for e in errors if e)) or None
                ss.rv_findings = rh.locate(found, ss.rv_reviewed_text)
                ss.rv_focus = ss.rv_findings[0]["id"] if ss.rv_findings else None
        except InputError as e:            # empty or too long text
            st.warning(str(e))
        except services.BackendNotConnected as e:
            theme.not_connected(e)
        except Exception as e:
            st.error(f"The check could not finish ({type(e).__name__}: {e}). Try again in a moment.")

with right, st.container(key="rv_results"):
    findings = ss.rv_findings
    if findings is None:
        st.markdown(
            '<div class="rv-h"><b>Findings</b><small>appear here after a check</small></div>'
            '<div class="rv-checks">'
            '<div><i style="background:#FFF4E0;color:#8A4B06">RULE</i><b>Terminology</b>'
            '<small>Banned product names and variants from the glossary.</small></div>'
            '<div><i style="background:#FDECEC;color:#B42318">RULE</i><b>Fact freshness</b>'
            '<small>Facts past their expiry date, with the owner to ask.</small></div>'
            '<div><i style="background:#E8F6F2;color:#0B5E52">AI + SOURCES</i><b>Claims, tone, messaging</b>'
            '<small>Gemini, limited to cited guidelines; anything unsupported is UNVERIFIED.</small></div>'
            '<div><i style="background:#EEF2FF;color:#3C4FB8">RULE</i><b>Readability</b>'
            '<small>Hard-to-read sentences for an everyday audience.</small></div>'
            '</div>', unsafe_allow_html=True)
    else:
        if ss.rv_ai_error:
            for msg in ss.rv_ai_error.split("\n"):
                st.warning(msg if "image" in msg else
                           "AI review unavailable right now, so only rule checks ran. Try again in a minute.")
        if not findings:
            st.success("No issues found. This campaign matches the Lumora brand kit."
                        if ss.get("rv_img_result") else "No issues found. This copy matches the Lumora brand kit.")
        else:
            MUST = ("claim", "outdated_fact", "terminology")
            is_open = [f for f in findings if f["status"] == "open"]
            must = sum(f["category"] in MUST for f in findings)
            must_left = sum(f["category"] in MUST for f in is_open)
            sugg_left = len(is_open) - must_left
            unver = sum(f["source_id"] == "UNVERIFIED" for f in findings)
            unver_left = sum(f["source_id"] == "UNVERIFIED" for f in is_open)
            n_open = len(is_open)
            n_done = len(findings) - n_open

            def tile(bg, fg, left, total, label):
                cls = ' class="done"' if total and not left else ""
                of = f"<s>of {total}</s>" if left != total else ""
                return (f'<div{cls} style="background:{bg};color:{fg}"><b>{left}{of}</b>'
                        f'<small>{label}{" · all done ✓" if total and not left else ""}</small></div>')

            st.markdown(
                f'<div class="rv-h"><b>Findings</b><small>{n_done} of {len(findings)} decided</small></div>'
                f'<div class="rv-sum">'
                + tile("#FDECEC", "#B42318", must_left, must, "must fix left")
                + tile("#FFF4E0", "#8A4B06", sugg_left, len(findings) - must, "suggestions left")
                + tile("#F3F5F9", "#33415C", unver_left, unver, "unverified claims left")
                + f'<div style="background:#E8F6F2;color:#0B5E52"><b>{n_done}<s>of {len(findings)}</s></b>'
                  f'<small>decided</small></div></div>',
                unsafe_allow_html=True)
            if ss.rv_reviewed_text:
                segs, revised, manual = rh.revision(ss.rv_reviewed_text, findings)
                view = st.radio("View", ["Live changes", "Final copy", "Original"], horizontal=True,
                                key="rv_view", label_visibility="collapsed")
                if view == "Original":
                    st.markdown(theme.highlight_html(ss.rv_reviewed_text, rh.highlight_items(findings)),
                                unsafe_allow_html=True)
                    st.caption("Red: claim or expired fact · Amber: tone or terminology · Purple: accessibility")
                elif view == "Final copy":
                    st.markdown(f'<div class="iw-text">{html.escape(revised) or "<i>(empty)</i>"}</div>',
                                unsafe_allow_html=True)
                    st.caption(f"{len(revised.split())} words · your draft with every accepted and edited fix applied"
                               + (" · open findings are still in the original wording" if n_open else ""))
                    st.button("Use this version in the editor", key="rv_use", on_click=use_revised, args=(revised,),
                              disabled=revised.strip() == ss.rv_reviewed_text.strip())
                else:
                    st.markdown(theme.live_html(segs), unsafe_allow_html=True)
                    st.markdown(
                        '<div class="rv-legend">'
                        '<span><i style="background:#FDECEC;border:1px solid #F3B4B0"></i>removed</span>'
                        '<span><i style="background:#DDF3EC"></i>fix applied ✓</span>'
                        '<span><i style="border-bottom:2px dotted #9AA3B5"></i>rejected, kept as written ✕</span>'
                        '<span><i style="background:#FFF4E0;border-bottom:2px dashed #B45309"></i>needs your rewrite ✎</span>'
                        '<span><i style="border-bottom:2px wavy #D93025"></i>still open</span></div>',
                        unsafe_allow_html=True)
                if manual:
                    st.info(f"Finding {', '.join(str(m) for m in manual)} gives advice rather than new wording. "
                            "Use Edit to write your own version, or rewrite it in the editor.")
            img = ss.get("rv_img_result")
            img_fs = [f for f in findings if f.get("where") == "image"]
            if img:
                n_img_open = sum(f["status"] == "open" for f in img_fs)
                st.markdown(f'<div class="rv-h" style="margin-top:10px"><b>Campaign image</b><small>{len(img_fs)} finding(s)'
                            f' · {len(img_fs) - n_img_open} decided</small></div>', unsafe_allow_html=True)
                st.image(theme.annotated_image(img["bytes"], img_fs), width="stretch")
                how = ("Text read by Gemini earlier and stored for this sample" if img.get("stored") else
                       f"{len(img['lines'])} line(s) of text read by Gemini" if img.get("lines") else
                       "Text in the image not read (AI not connected)")
                st.caption(f"{how} · colours and contrast measured on the image itself · numbers match the findings below")
                if img.get("text"):
                    with st.expander("Text found in the image"):
                        st.write(img["text"])
            txt_fs = [f for f in findings if f.get("where") != "image"]
            if txt_fs and img_fs:
                st.markdown('<div class="ap-lbl" style="font-size:.66rem;letter-spacing:.14em;font-weight:700;'
                            'color:#8A93A6;margin:10px 0 4px">IN THE COPY</div>', unsafe_allow_html=True)
            for f in txt_fs:
                render_row(f)
            if img_fs:
                st.markdown('<div class="ap-lbl" style="font-size:.66rem;letter-spacing:.14em;font-weight:700;'
                            'color:#8A93A6;margin:10px 0 4px">IN THE IMAGE</div>', unsafe_allow_html=True)
            for f in img_fs:
                render_row(f)
            if n_open:
                st.caption(f"Decide on {n_open} open finding(s) to send this for approval.")
            if st.button("Send for approval", type="primary", disabled=n_open > 0, width="stretch"):
                try:
                    title = ss.get("rv_title") or "Untitled draft"
                    body = ss.rv_reviewed_text or ("[Image only] " + ((img or {}).get("text") or "campaign image"))
                    sid = services.submit_for_approval(f"{title} · {ss.get('rv_channel', 'Draft')}", body,
                                                       findings, ss.user)
                    if img:
                        services.save_submission_image(sid, img["bytes"])
                    ss.rv_findings, ss.rv_ai_error = None, None
                    st.toast("Sent to Approvals")
                    st.success("Sent for approval. A manager will see it in Approvals.")
                except services.BackendNotConnected as e:
                    theme.not_connected(e)

# ---------------------------------------------------------------- all drafts, with who checked and who decided
st.markdown("""<style>
.dr-wrap { background:#fff; border:1px solid #E2E7F0; border-radius:16px; overflow:hidden; margin-top:6px;
  box-shadow:0 1px 2px rgba(20,24,33,.03), 0 8px 24px rgba(20,24,33,.04); }
.dr-t { width:100%; border-collapse:collapse; font-size:.82rem; }
.dr-t th { text-align:left; font-size:.66rem; letter-spacing:.12em; color:#8A93A6; font-weight:700; padding:12px 14px;
  background:#FAFBFC; border-bottom:1px solid #EEF0F4; }
.dr-t td { padding:12px 14px; border-bottom:1px solid #F2F4F7; vertical-align:top; color:#33415C; }
.dr-t tr:last-child td { border-bottom:none; }
.dr-t td b { color:#1B2A4E; font-weight:600; display:block; } .dr-t td small { color:#8A93A6; font-size:.72rem; }
.dr-n { display:inline-block; font-weight:700; font-size:.72rem; padding:2px 8px; border-radius:999px; margin:0 4px 3px 0; }
.dr-st { font-weight:700; font-size:.7rem; padding:3px 9px; border-radius:999px; white-space:nowrap; }
.tl { border-left:2px solid #E2E7F0; margin:6px 0 4px 6px; padding-left:16px; }
.tl div { position:relative; padding:6px 0; font-size:.82rem; color:#33415C; }
.tl div::before { content:""; position:absolute; left:-22px; top:11px; width:10px; height:10px; border-radius:50%;
  background:var(--c,#8A93A6); border:2px solid #fff; box-shadow:0 0 0 1px #E2E7F0; }
.tl b { color:#1B2A4E; } .tl small { color:#8A93A6; margin-left:6px; }
</style>""", unsafe_allow_html=True)

st.write("")
theme.page_header("Workspace", "All drafts",
                  "Every draft in the workspace, who wrote it, what the check found, and who approved or returned it.")
try:
    subs = services.list_submissions()
except Exception:
    subs = []
STATUS = {"pending": ("In review", "#FFF4E0", "#8A4B06"), "approved": ("Approved", "#E8F6F2", "#0B5E52"),
          "rejected": ("Changes requested", "#FDECEC", "#B42318")}
f1, f2 = st.columns([1.2, 3])
pick = f1.selectbox("Show", ["All", "In review", "Approved", "Changes requested"], key="dr_filter")
q = f2.text_input("Search drafts", placeholder="Title, author or approver", key="dr_q").strip().lower()
rows_html, shown = "", []
for s_ in subs:
    lbl, bg, fg = STATUS.get(s_["status"], (s_["status"].title(), "#F3F5F9", "#33415C"))
    if pick != "All" and lbl != pick:
        continue
    blob = f"{s_['title']} {theme.full_name(s_['author'])} {theme.full_name(s_.get('decided_by', ''))}".lower()
    if q and q not in blob:
        continue
    shown.append(s_)
    fs = s_["findings"]
    n_open = sum(f["status"] == "open" for f in fs)
    n_ok = sum(f["status"] in ("accepted", "edited") for f in fs)
    n_rej = sum(f["status"] == "rejected" for f in fs)
    decided = (f'<b>{html.escape(theme.full_name(s_["decided_by"]))}</b><small>{html.escape(s_["decided_at"])} UTC</small>'
               + (f'<small style="display:block">“{html.escape(s_["comment"][:70])}”</small>' if s_.get("comment") else "")
               if s_.get("decided_by") else '<small>Waiting for a manager</small>')
    rows_html += (
        f'<tr><td><b>{html.escape(s_["title"])}</b><small>#{s_["id"]} · v{s_["version"]}</small></td>'
        f'<td><b>{html.escape(theme.full_name(s_["author"]))}</b><small>Creator</small></td>'
        f'<td><b>Inkwise check · {len(fs)} findings</b><small>decided by {html.escape(theme.full_name(s_["author"]))}</small></td>'
        f'<td><span class="dr-n" style="background:#FDECEC;color:#B42318">{n_open} open</span>'
        f'<span class="dr-n" style="background:#E8F6F2;color:#0B5E52">{n_ok} fixed</span>'
        f'<span class="dr-n" style="background:#F3F5F9;color:#5A6480">{n_rej} rejected</span></td>'
        f'<td><span class="dr-st" style="background:{bg};color:{fg}">{lbl}</span></td>'
        f'<td>{decided}</td><td><small>{html.escape(s_.get("updated_at", s_["submitted_at"]))}</small></td></tr>')
if rows_html:
    st.markdown('<div class="dr-wrap"><table class="dr-t"><tr><th>DRAFT</th><th>AUTHOR</th><th>CHECKED</th>'
                '<th>FINDINGS</th><th>STATUS</th><th>APPROVED / RETURNED BY</th><th>UPDATED</th></tr>'
                + rows_html + '</table></div>', unsafe_allow_html=True)
else:
    theme.empty_state("No drafts match. Clear the search or pick another status.")

if shown:
    st.write("")
    opts = {f"#{x['id']} · {x['title']}": x for x in shown}
    sel = st.selectbox("Open a draft to see its full trail", list(opts), key="dr_open")
    d_ = opts[sel]
    COLORS = {"created": "#3C4FB8", "reviewed": "#12917F", "finding_accepted": "#12917F", "finding_edited": "#B45309",
              "finding_rejected": "#D93025", "approved": "#12917F", "changes_requested": "#D93025",
              "rechecked": "#12917F", "new_version": "#3C4FB8"}
    VERB = {"created": "created the draft", "reviewed": "ran the Inkwise check", "finding_accepted": "accepted a finding",
            "finding_edited": "edited a suggested fix", "finding_rejected": "rejected a finding",
            "approved": "approved it", "changes_requested": "sent it back", "rechecked": "re-checked it after a fact renewal",
            "new_version": "saved a new version"}
    try:
        hist = [h for h in services.draft_history(d_["id"]) if h["kind"] == "event"]
    except Exception:
        hist = []
    who = lambda u: "Inkwise" if u in ("inkwise-ai", "system") else theme.full_name(u)
    tl = "".join(f'<div style="--c:{COLORS.get(h["action"], "#8A93A6")}"><b>{html.escape(who(h["user"]))}</b> '
                 f'{html.escape(VERB.get(h["action"], h["action"].replace("_", " ")))}'
                 f'<small>{html.escape(h["at"][:16].replace("T", " "))} UTC · {html.escape(h.get("detail", ""))}</small></div>'
                 for h in hist)
    c1, c2 = st.columns([1, 1.2], gap="large")
    with c1:
        st.markdown(f'<div class="iw-panel"><h3>Trail</h3><div class="sub">From the audit log, oldest first</div>'
                    f'<div class="tl">{tl or "<small>No events yet.</small>"}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="iw-panel"><h3>{html.escape(d_["title"])}</h3><div class="sub">by '
                    f'{html.escape(theme.full_name(d_["author"]))}</div><div class="iw-text">{html.escape(d_["text"])}</div>'
                    '</div>', unsafe_allow_html=True)
        for f in d_["findings"]:
            st.markdown(f'- **{f["status"].title()}** · `{f["source_id"]}` · “{f["span"]}” → {f["suggested_fix"]}')

theme.ai_banner()
theme.footer()
