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

st.title("Approvals")
st.caption("Everything waiting for a decision. Approve it or send it back with a comment.")

try:
    pending = services.list_submissions("pending")
except services.BackendNotConnected as e:
    theme.not_connected(e)
    st.stop()

can_decide = ss.role in ("Manager", "Reviewer", "Admin")
if not can_decide:
    st.info("You are signed in as Creator. Switch to Manager, Reviewer or Admin in the sidebar to decide.")

if not pending:
    st.success("Nothing is waiting. New submissions from Review will show up here.")

for s in pending:
    with st.container(border=True):
        h1, h2 = st.columns([5, 1])
        h1.markdown(f"**{html.escape(s['title'])}**")
        h1.caption(f"{s['id']} · by {s['author']} · {s['submitted_at']} · version {s['version']}")
        h2.markdown('<span class="iw-pill open">Pending</span>', unsafe_allow_html=True)

        n_acc = sum(f["status"] in ("accepted", "edited") for f in s["findings"])
        n_rej = sum(f["status"] == "rejected" for f in s["findings"])
        st.caption(f"{len(s['findings'])} findings · {n_acc} accepted · {n_rej} rejected")

        with st.expander("See text and findings"):
            st.markdown("**Original text**")
            st.write(s["text"])
            for f in s["findings"]:
                st.markdown(
                    f"**{f['status'].title()}** · `{f['source_id']}` · "
                    f"“{f['span']}” → {f['suggested_fix']}"
                )

        comment = st.text_input("Comment (optional)", key=f"c_{s['id']}")
        a, b, _ = st.columns([1, 1, 4])

        decision = None
        if a.button("Approve", key=f"ap_{s['id']}", type="primary", disabled=not can_decide,
                    use_container_width=True):
            decision = ("approved", "✅", "Approved")
        elif b.button("Reject", key=f"rj_{s['id']}", disabled=not can_decide,
                      use_container_width=True):
            decision = ("rejected", "❌", "Rejected")

        if decision:
            status, icon, label = decision
            try:
                services.decide_submission(s["id"], status, comment, ss.user, ss.role)
            except Exception as e:
                st.error(str(e))
            else:
                st.toast(f"{label} {s['title']}", icon=icon)
                st.rerun()

theme.ai_banner()