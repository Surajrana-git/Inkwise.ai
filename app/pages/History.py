import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
import pandas as pd
import streamlit as st
import services
import theme

st.set_page_config(page_title="inkwise.ai", page_icon="✒️", layout="wide")
theme.render_shell()

st.title("History")
st.caption("Earlier reviews and who decided what.")

try:
    all_subs = services.list_submissions()
except services.BackendNotConnected as e:
    theme.not_connected(e)
    st.stop()

decided = [s for s in all_subs if s["status"] != "pending"]

if not decided:
    st.info("No decisions yet. Approved and rejected reviews appear here.")
    st.page_link("pages/1_Review.py", label="Start a review", icon="📝")
    st.stop()

m = st.columns(3)
m[0].metric("Decided", len(decided))
m[1].metric("Approved", sum(s["status"] == "approved" for s in decided))
m[2].metric("Rejected", sum(s["status"] == "rejected" for s in decided))

f1, f2 = st.columns([1, 2])
status_filter = f1.selectbox("Status", ["All", "Approved", "Rejected"])
query = f2.text_input("Search", placeholder="Search by title, author or comment")

rows = []
for s in decided:
    if status_filter != "All" and s["status"] != status_filter.lower():
        continue
    blob = f"{s['title']} {s['author']} {s['comment']}".lower()
    if query and query.lower() not in blob:
        continue
    rows.append({
        "ID": s["id"], "Title": s["title"], "Author": s["author"], "Submitted": s["submitted_at"],
        "Decision": s["status"].title(), "Decided by": s["decided_by"],
        "Decided at": s["decided_at"], "Comment": s["comment"], "Findings": len(s["findings"]),
    })

if not rows:
    st.warning("Nothing matches those filters. Clear the search or change the status.")
else:
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="inkwise_history.csv", mime="text/csv")

    st.markdown('<div class="iw-section">Details</div>', unsafe_allow_html=True)
    pick = st.selectbox("Open a review", [r["ID"] for r in rows])
    s = next(x for x in decided if x["id"] == pick)
    with st.container(border=True):
        st.markdown(f"**{s['title']}** · {s['status'].title()} by {s['decided_by']}")
        st.write(s["text"])
        if s["comment"]:
            st.caption(f"Comment: {s['comment']}")
        for f in s["findings"]:
            st.markdown(f"- **{f['status'].title()}** · `{f['source_id']}` · “{f['span']}” → {f['suggested_fix']}")