"""Help Centre: answers a judge or new user needs without the team in the room."""
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

st.markdown("""<style>
.hc-hero { position:relative; border-radius:20px; padding:34px 36px 30px; margin:4px 0 22px; overflow:hidden;
  background:linear-gradient(120deg, #EAF5F2 0%, #F3F6FB 55%, #EEF2FB 100%); border:1px solid #E2E7F0; }
.hc-hero .eb { font-size:.68rem; letter-spacing:.18em; font-weight:700; color:#12917F; }
.hc-hero h1 { font-family:'Instrument Serif', Georgia, serif !important; font-weight:400 !important; font-size:2.6rem !important;
  color:#1B2A4E !important; margin:4px 0 4px !important; padding:0 !important; line-height:1.1 !important; }
.hc-hero p { color:#5A6480; margin:0; max-width:640px; }
.hc-hero .art { position:absolute; right:34px; top:22px; display:flex; gap:10px; opacity:.9; }
.hc-hero .art i { display:block; width:54px; height:54px; border-radius:16px; font-style:normal; font-size:1.5rem;
  display:flex; align-items:center; justify-content:center; box-shadow:0 6px 18px rgba(27,42,78,.08); }
.st-key-hc_search input { min-height:48px; border-radius:12px !important; font-size:.95rem !important; }
.hc-h { display:flex; justify-content:space-between; align-items:baseline; margin:20px 0 10px; }
.hc-h b { font-size:1.15rem; color:#1B2A4E; } .hc-h small { color:#5A6480; font-size:.8rem; }
.st-key-hc_start, .st-key-hc_guide, .st-key-hc_faq, .st-key-hc_method, .st-key-hc_help1, .st-key-hc_help2 {
  background:#fff; border:1px solid #E2E7F0; border-radius:16px; padding:18px 20px;
  box-shadow:0 1px 2px rgba(20,24,33,.03), 0 8px 24px rgba(20,24,33,.04); }
.hc-acc { display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; }
.hc-acc div { border:1px solid #EEF0F4; border-radius:12px; padding:12px 14px; background:#FCFCFD; }
.hc-acc b { display:block; color:#1B2A4E; font-size:.92rem; } .hc-acc small { color:#5A6480; font-size:.76rem; line-height:1.4; }
.hc-acc i { font-style:normal; font-size:.62rem; font-weight:700; letter-spacing:.08em; padding:2px 8px; border-radius:999px;
  display:inline-block; margin-bottom:6px; }
.st-key-hc_topics .stButton button { width:100%; min-height:96px; text-align:left; justify-content:flex-start;
  background:#fff !important; border:1px solid #E2E7F0 !important; border-radius:14px !important; padding:14px 16px 14px 70px !important;
  position:relative; box-shadow:0 1px 2px rgba(20,24,33,.03); }
.st-key-hc_topics .stButton button:hover { border-color:#12917F !important; box-shadow:0 8px 24px rgba(18,145,127,.10); }
.st-key-hc_topics .stButton button[kind="primary"] { border:1px solid #12917F !important; background:#F0F8F6 !important; box-shadow:inset 3px 0 0 #12917F !important; }
.st-key-hc_topics .stButton button[kind="primary"]::before { background:#fff !important; color:#0B5E52; box-shadow:0 0 0 1px #CFE9E2; }
.st-key-hc_topics .stButton button p { text-align:left; color:#5A6480 !important; font-size:.78rem; font-weight:400 !important; line-height:1.4; }
.st-key-hc_topics .stButton button p strong { display:block; color:#1B2A4E; font-size:.95rem; font-weight:650; margin-bottom:3px; }
.st-key-hc_topics .stButton button::before { content:var(--ic); position:absolute; left:16px; top:50%; transform:translateY(-50%);
  width:40px; height:40px; border-radius:12px; background:var(--bg); display:flex; align-items:center; justify-content:center;
  font-size:1.15rem; }
.st-key-hc_topics .stButton button::after { content:"›"; position:absolute; right:16px; top:50%; transform:translateY(-50%);
  color:#8A93A6; font-size:1.4rem; }
.hc-steps { counter-reset:s; margin:6px 0 4px; }
.hc-steps div { counter-increment:s; display:flex; gap:12px; padding:9px 0; border-top:1px solid #F0F2F6; font-size:.86rem;
  color:#33415C; line-height:1.45; }
.hc-steps div:first-child { border-top:none; }
.hc-steps div::before { content:counter(s); flex:none; width:24px; height:24px; border-radius:50%; background:#E8F6F2; color:#0B5E52;
  font-weight:700; font-size:.78rem; display:flex; align-items:center; justify-content:center; }
.hc-tip { background:#F3F6FB; border-radius:10px; padding:10px 12px; font-size:.8rem; color:#33415C; margin-top:8px; }
.hc-m { display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; }
.hc-m div { border:1px solid #EEF0F4; border-radius:12px; padding:14px; background:#FCFCFD; font-size:.8rem; color:#33415C; line-height:1.5; }
.hc-m b { display:block; color:#1B2A4E; font-size:.92rem; margin-bottom:4px; }
.hc-m ul { margin:4px 0 0 16px; padding:0; } .hc-m li { margin:2px 0; }
.hc-cta b { display:block; color:#1B2A4E; font-size:1.05rem; } .hc-cta small { color:#5A6480; font-size:.82rem; }
.hc-empty { color:#5A6480; font-size:.86rem; padding:8px 2px; }
</style>""", unsafe_allow_html=True)

# ---------------------------------------------------------------- content

TOPICS = [
    {"key": "check", "icon": "✎", "bg": "#E8F6F2", "title": "Check a draft",
     "sub": "Paste copy or load a sample, then run the pre-publication check.",
     "page": "pages/1_Review.py", "as": "asha",
     "steps": ["Sign in as Asha (Creator) and open Check a draft. Pick a sample draft (for example “Launch post”), paste your own copy, or import a PDF or "
               "Word file (up to 12,000 characters).",
               "Optionally add the campaign image, or press “Use sample banner”.",
               "Press “Run pre-publication check”. Rule checks run first; Gemini then looks for claims, tone and "
               "messaging issues, limited to the guidelines it is shown.",
               "Each finding is highlighted in your text and numbered. Open one to see why it was flagged and the exact "
               "source it relies on."],
     "tip": "Red underline: claim or expired fact. Amber: tone or terminology. Blue: accessibility."},
    {"key": "decide", "icon": "✓", "bg": "#E8EEFB", "title": "Accept, edit or reject",
     "sub": "Decide on every finding and watch the draft update live.",
     "page": "pages/1_Review.py", "as": "asha",
     "steps": ["Accept applies the suggested fix. Edit lets you write your own version. Reject keeps your wording.",
               "The draft at the top updates after every click: removed text is struck out, fixes are green, rejected "
               "findings stay with a dotted underline.",
               "Switch to “Final copy” to read the clean text, or “Use this version in the editor” to check it again.",
               "When every finding is decided, “Send for approval” sends it to a Manager with all your decisions."],
     "tip": "Every decision is logged and feeds Guideline insights, so a rule people keep rejecting gets noticed."},
    {"key": "approve", "icon": "⧗", "bg": "#FFF4E0", "title": "Approvals and sign-off",
     "sub": "How a Manager reviews and signs off a draft.",
     "page": "pages/Approvals.py", "as": "meera",
     "steps": ["Sign in as Meera (Manager) and open Approval queue. The queue shows each draft as “Ready” or “Needs a look”.",
               "Readiness checks show whether every finding was decided and whether any expired fact or unsupported "
               "claim was kept.",
               "Read the Changes or Final copy view and the table of what the creator decided. The bell (top right) "
               "tells you when a new draft arrives.",
               "Approve, or Send back with a comment (a comment is required so the creator knows what to change)."],
     "tip": "Only Managers sign off, and nobody can approve their own draft. Admins look after facts and the brand kit."},
    {"key": "facts", "icon": "◷", "bg": "#FDECEC", "title": "Fact freshness",
     "sub": "Approved facts have owners and expiry dates.",
     "page": "pages/Fact_Register.py", "as": "ravi",
     "steps": ["Every approved fact (for example F01, “2 million registered users”) has an owner and an expiry date.",
               "A draft that repeats an expired fact gets an EXPIRED finding naming the owner to ask.",
               "In the Fact Register an Admin renews a fact with a new date; the impact preview shows which open drafts "
               "cite it.",
               "After a renewal those drafts are re-checked straight away, and the renewal is logged."],
     "tip": "Facts expiring within 30 days are shown as EXPIRING so they can be renewed in time."},
    {"key": "image", "icon": "▣", "bg": "#F3E9FB", "title": "Image checks",
     "sub": "Brand colours, readable text, logo, and the words in the image.",
     "page": "pages/1_Review.py", "as": "asha",
     "steps": ["Add a PNG or JPEG (up to 5 MB) next to the copy, or use the sample banner.",
               "Colours are compared with the Lumora palette (rule V01) and text contrast is measured against WCAG AA "
               "4.5:1 (rule V02). These run without AI.",
               "With AI connected, Gemini reads the text and checks for the Lumora logo (V03); the normal copy rules "
               "then run on that text, so an expired figure on a banner is caught too.",
               "The image is shown with numbered boxes that match the findings, and the Manager sees it in the Approval queue."],
     "tip": "Without AI, contrast is an estimate and the finding says so. Text in the image is only read with AI."},
    {"key": "insights", "icon": "▤", "bg": "#E8F6F2", "title": "Guideline insights",
     "sub": "See which rules are unclear, and fix their wording.",
     "page": "pages/Insights.py", "as": "meera",
     "steps": ["Sign in as a Manager or Admin and open Insights.",
               "Guidelines that reviewers keep overriding are listed with their override rate.",
               "Ask for a clearer wording; Inkwise drafts one from the decisions people made.",
               "An Admin accepts the new wording, and the change is logged."],
     "tip": "Insights uses real decisions from the audit log, not guesses."},
]


def faq_items() -> list[tuple[str, str]]:
    ev = {}
    try:
        ev = services.eval_summary()
    except Exception:
        pass
    acc = (f"On our labelled test set ({ev.get('samples', '100')} samples, rules + Gemini) Inkwise found "
           f"{ev.get('recall', 'most')} of the planted errors ({ev.get('recall_detail', '')}); "
           f"{ev.get('precision', '')} of its findings matched a labelled error and {ev.get('citation', '')} cited the "
           f"labelled source. Home shows the breakdown by type." if ev else
           "We measure recall, precision and citation accuracy on a labelled test set; Home shows the latest numbers.")
    return [
        ("What does UNVERIFIED mean?",
         "The AI thinks a claim needs support but no approved fact or guideline in the brand kit backs it. "
         "Inkwise never invents a source: if the AI cannot quote words from the source it cites, the finding is "
         "marked UNVERIFIED and its confidence is capped."),
        ("How do I know a finding is right?",
         "Every finding shows the exact guideline, fact or glossary entry it relies on, with the matching words "
         "highlighted. Rule findings (glossary, expiry, readability, colours, contrast) are deterministic; AI findings "
         "show a confidence bar."),
        ("Does Inkwise change my text on its own?",
         "No. Findings are suggestions. Nothing changes until a person accepts or edits it, and a Manager signs off "
         "before anything counts as approved."),
        ("What is sent to the AI?",
         "Only the text being checked, after personal data (names, emails, phone numbers and similar) is masked, plus "
         "the brand-kit entries relevant to it. Images are sent to Gemini only to read their text and logo. "
         "Lumora and all demo data are fictional."),
        ("What happens if the AI is not connected?",
         "The header shows “AI not connected”. Rule checks still run (glossary, expired facts, readability, image "
         "colours and contrast) and the page says what was skipped. A call that hangs is abandoned after a few seconds."),
        ("Why do people see different tabs?",
         "Each person works in their own workspace and only sees what their job needs. Asha (Creator) checks and sends "
         "drafts, Meera (Manager) signs them off and watches unclear guidelines, Ravi (Admin) keeps facts and the brand "
         "kit current. If you open another person's page, Inkwise says whose it is and offers to continue as them. "
         "Fact owners can still renew their own team's facts from the link on their Home."),
        ("Why can’t an Admin approve drafts?",
         "Separation of duties: Admins keep facts and the brand kit current; Managers sign off content. Nobody can "
         "approve their own draft, so every published piece has a second pair of eyes."),
        ("Which demo accounts can I use?",
         "Asha Menon (Creator), Meera Kapoor (Manager) and Ravi Sharma (Admin). Pick one on the sign-in page, or switch "
         "at any time from the name in the top-right corner. No password is needed for the demo accounts."),
        ("Which files can I check?",
         "Copy: up to 12,000 characters, typed, pasted or imported from a PDF, Word (.docx), .txt or .md file up to "
         "5 MB. Images: PNG or JPEG up to 5 MB."),
        ("How accurate is it?", acc),
        ("Where is the full record of what happened?",
         "My drafts (Creator) and All drafts (Manager, Admin) list every draft with who wrote it, who decided and when, and lets you download an audit report "
         "as PDF or the whole history as CSV. Check a draft also shows each draft’s timeline."),
        ("How do notifications work?",
         "The bell in the top-right corner shows what needs you. A Manager is told when a creator sends a draft "
         "for approval; the creator is told when it is approved or sent back, with the comment; an Admin is told "
         "about expired or expiring facts and guidelines that look unclear. New items also pop up once when you "
         "sign in or switch person, and each one opens the right page."),
        ("Can I check a PDF or Word file?",
         "Yes. On Check a draft, use “Import from a PDF, Word or text file”. The text is put in the box so you can edit "
         "it before the check. Scanned PDFs (pictures of text) and old .doc files are not read; the page says so."),
        ("What happens if I refresh the page?",
         "You stay signed in as the same demo person on the same page. A draft you were typing and decisions you "
         "had not sent yet are not saved, so send for approval before you leave."),
        ("Can I undo a decision?",
         "Yes, before you send it: press another button on the same finding (for example Reject after Accept). "
         "After sending, a Manager can send the draft back with a comment."),
        ("Is this connected to real customer data?",
         "No. This is a demo workspace for the fictional brand Lumora. All drafts, facts and people are synthetic."),
    ]


def match(q: str, *parts) -> bool:
    return not q or all(w in " ".join(parts).lower() for w in q.lower().split())


# ---------------------------------------------------------------- hero + search

st.markdown('<div class="hc-hero"><div class="eb">SUPPORT</div><h1>Help Centre</h1>'
            '<p>Answers, step-by-step guides and how Inkwise works, so you can use every part of it on your own.</p>'
            '<div class="art"><i style="background:#fff">?</i><i style="background:#E8F6F2">✓</i>'
            '<i style="background:#FFF4E0">💡</i></div></div>', unsafe_allow_html=True)
if theme.DEMO_VIDEO.exists():
    with st.container(key="hc_video"):
        st.markdown('<div class="hc-h" style="margin-top:0"><b>Watch the demo</b>'
                    '<small>recorded from this app, with voice-over</small></div>', unsafe_allow_html=True)
        v1, v2 = st.columns([1.6, 1], gap="large")
        with v1:
            st.markdown("**The whole journey** · 2½ minutes: Asha checks and sends a draft, Meera approves it, "
                        "Ravi renews a fact.")
            theme.demo_video(caption=False)
        with v2:
            st.markdown("**One person at a time** · about a minute each")
            for tab, role in zip(st.tabs(["Creator · Asha", "Manager · Meera", "Admin · Ravi"]),
                                 ("Creator", "Manager", "Admin")):
                with tab:
                    theme.role_video(role)
with st.container(key="hc_search"):
    q = st.text_input("Search help", key="hc_q", placeholder="Search for help, e.g. “expired”, “approve”, “image”, “AI”",
                      label_visibility="collapsed")

# ---------------------------------------------------------------- start here: demo accounts

if match(q, "demo accounts sign in start person role creator manager admin asha meera ravi"):
    with st.container(key="hc_start"):
        st.markdown('<div class="hc-h" style="margin-top:0"><b>Start here: the three demo people</b>'
                    '<small>switch any time from your name, top right</small></div>'
                    '<div class="hc-acc">'
                    '<div><i style="background:#E3F3F0;color:#0B5E52">CREATOR</i><b>Asha Menon</b>'
                    '<small>Writes and checks campaign copy, decides on findings, sends drafts for approval.</small></div>'
                    '<div><i style="background:#E8EEFB;color:#1A4FB0">MANAGER</i><b>Meera Kapoor</b>'
                    '<small>Approves or sends back drafts, sees Guideline insights.</small></div>'
                    '<div><i style="background:#F3E9FB;color:#6B2FA3">ADMIN</i><b>Ravi Sharma</b>'
                    '<small>Keeps facts current in the Fact Register and manages the brand kit.</small></div>'
                    '</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- topics

topics = [t for t in TOPICS if match(q, t["title"], t["sub"], " ".join(t["steps"]), t["tip"])]
st.markdown(f'<div class="hc-h"><b>Help topics</b><small>{len(topics)} guide(s) · pick one for step-by-step help</small></div>',
            unsafe_allow_html=True)
if not topics:
    st.markdown('<div class="hc-empty">No guide matches that search. Try the questions below, or clear the search.</div>',
                unsafe_allow_html=True)
else:
    if ss.get("hc_topic") not in [t["key"] for t in topics]:
        ss.hc_topic = topics[0]["key"]
    css = "".join(f'.st-key-hc_t_{t["key"]} button {{ --ic:"{t["icon"]}"; --bg:{t["bg"]}; }}' for t in topics)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    with st.container(key="hc_topics"):
        for row in range(0, len(topics), 3):
            cols = st.columns(3)
            for col, t in zip(cols, topics[row:row + 3]):
                with col:
                    st.button(f"**{t['title']}** {t['sub']}", key=f"hc_t_{t['key']}", width="stretch",
                              type="primary" if ss.hc_topic == t["key"] else "secondary",
                              on_click=ss.__setitem__, args=("hc_topic", t["key"]))
    t = next(x for x in topics if x["key"] == ss.hc_topic)
    with st.container(key="hc_guide"):
        g1, g2 = st.columns([2.2, 1], gap="large")
        with g1:
            st.markdown(f'<div class="hc-h" style="margin-top:0"><b>{html.escape(t["title"])}</b>'
                        f'<small>step by step</small></div><div class="hc-steps">'
                        + "".join(f"<div><span>{html.escape(s)}</span></div>" for s in t["steps"])
                        + f'</div><div class="hc-tip">💡 {html.escape(t["tip"])}</div>', unsafe_allow_html=True)
        with g2:
            who = theme.full_name(t["as"])
            st.markdown(f'<div class="hc-cta" style="margin-top:6px"><b>Try it now</b>'
                        f'<small>Opens the right page as {html.escape(who)}.</small></div>', unsafe_allow_html=True)
            if st.button(f"Go as {who.split()[0]}", key="hc_go", type="primary", width="stretch"):
                if ss.get("user") == t["as"] or theme.switch_user(t["as"]):
                    try:
                        st.switch_page(t["page"])
                    except Exception:
                        st.rerun()

# ---------------------------------------------------------------- FAQ

faqs = [(qq, a) for qq, a in faq_items() if match(q, qq, a)]
st.markdown(f'<div class="hc-h"><b>Frequently asked questions</b><small>{len(faqs)} answer(s)</small></div>',
            unsafe_allow_html=True)
with st.container(key="hc_faq"):
    if not faqs:
        st.markdown('<div class="hc-empty">No answer matches that search yet. Clear the search, or ask the team '
                    'below.</div>', unsafe_allow_html=True)
    for qq, a in faqs:
        with st.expander(qq, expanded=bool(q) and len(faqs) <= 3):
            st.write(a)

# ---------------------------------------------------------------- methodology

if match(q, "methodology how it works rules ai gemini evidence limitations privacy responsible disclosure"):
    st.markdown('<div class="hc-h" id="methodology"><b>How Inkwise works</b>'
                '<small>methodology, responsible AI and known limitations</small></div>', unsafe_allow_html=True)
    with st.container(key="hc_method"):
        st.markdown(
            '<div class="hc-m">'
            '<div><b>How a check works</b><ul>'
            '<li>Rules first: glossary terms, expired facts, readability, image colours and contrast.</li>'
            '<li>Then Gemini, shown only the brand-kit entries relevant to the text.</li>'
            '<li>Each AI finding must quote words from the source it cites; otherwise it is UNVERIFIED.</li>'
            '<li>A person decides every finding; a Manager signs off.</li></ul></div>'
            '<div><b>Responsible AI and privacy</b><ul>'
            '<li>Personal data is masked before any text reaches the AI.</li>'
            '<li>The model used is disclosed with each review.</li>'
            '<li>Every decision, renewal and approval is in the audit log.</li>'
            '<li>Lumora and all demo data are fictional.</li></ul></div>'
            '<div><b>Known limitations</b><ul>'
            '<li>AI checks need Gemini; without it only rule checks run.</li>'
            '<li>Image contrast without AI is an estimate.</li>'
            '<li>Demo sign-in only: no real accounts or passwords yet.</li>'
            '<li>One workspace and one brand kit per deployment.</li></ul></div>'
            '</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- still need help / quick start

st.write("")
h1, h2 = st.columns(2, gap="medium")
with h1, st.container(key="hc_help1"):
    st.markdown('<div class="hc-cta"><b>💬 Still need help?</b><small>Tell DECODIANS what went wrong or what is '
                'unclear; we read every report.</small></div>', unsafe_allow_html=True)
    st.link_button("Report an issue on GitHub", "https://github.com/Surajrana-git/Inkwise.ai/issues", width="stretch")
with h2, st.container(key="hc_help2"):
    st.markdown('<div class="hc-cta"><b>📘 Quick start: the 3-minute story</b><small>Five steps that show the whole '
                'product, each as the right person.</small></div>', unsafe_allow_html=True)
    if st.button("Start the guided story", key="hc_tour", width="stretch"):
        ss.journey_hidden = False
        if ss.get("user") == "asha" or theme.switch_user("asha"):
            try:
                st.switch_page("pages/1_Review.py")
            except Exception:
                st.rerun()

theme.footer()
