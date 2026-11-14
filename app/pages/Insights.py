"""Guideline Clarity Insights (Round 3, Improvement 3). Manager and Admin only.

Uses only decisions logged in this workspace. Thresholds: docs/clarity_thresholds.md.
"""
import datetime as dt
import html
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
import pandas as pd
import plotly.express as px
import streamlit as st
import services
import theme

st.set_page_config(page_title="inkwise.ai", page_icon="✒️", layout="wide")
theme.render_shell()
ss = st.session_state

st.title("Insights")
st.caption("Which guidelines reviewers keep overriding, which mistakes keep coming back, and what to do about it. "
           "Built only from decisions logged in this workspace.")

if ss.get("flash"):
    st.success(ss.pop("flash"))

role = ss.get("role", "Creator")
if role not in ("Manager", "Admin"):
    st.info("Insights is for Managers and Admins. Sign in as `meera` (Manager) or `ravi` (Admin) to see it.")
    st.stop()

try:
    th = services.clarity_thresholds()
except services.BackendNotConnected as e:
    theme.not_connected(e)
    st.stop()

# ---------------------------------------------------------------- filters
f1, f2, f3 = st.columns([1.4, 1.4, 1.2])
today = dt.date.today()
rng = f1.date_input("Date range", value=(today - dt.timedelta(days=30), today), max_value=today)
if isinstance(rng, (tuple, list)) and len(rng) == 2:
    d_from, d_to = rng
else:
    d_from, d_to = today - dt.timedelta(days=30), today
role_pick = f2.selectbox("Decisions by", ["Everyone", "Creator", "Manager", "Reviewer", "Admin"])
group_pick = f3.selectbox("Repeat issues by", ["Category", "Creator"])
role_arg = None if role_pick == "Everyone" else role_pick.lower()

try:
    stats = services.guideline_stats(d_from.isoformat(), d_to.isoformat(), role_arg)
    repeats = services.repeat_issues(group_pick.lower(), d_from.isoformat(), d_to.isoformat())
except Exception as e:
    st.error(f"Insights could not load ({type(e).__name__}: {e}).")
    st.stop()

if not stats:
    theme.empty_state("No decisions in this range. Widen the dates, or run a review and decide on its findings.")
    st.stop()

unclear = [s for s in stats if s["unclear"]]
decided = sum(s["decided"] for s in stats)
theme.metric_row([
    (len(stats), "Guidelines with findings", ""),
    (decided, "Decisions in range", ""),
    (len(unclear), "Likely unclear", "warn" if unclear else "ok"),
    (sum(1 for r in repeats if r.get("repeat")) if group_pick == "Creator" else len(repeats), "Repeat issues", ""),
])

# ---------------------------------------------------------------- charts
st.markdown('<div class="iw-section">Override and reject rate per guideline</div>', unsafe_allow_html=True)
st.caption(f"Override = the creator edited the suggested fix. Reject = the finding was rejected. "
           f"A guideline is flagged when it was shown ≥ {th['min_shown']} times and override ≥ {th['override_rate']:.0%} "
           f"or reject ≥ {th['reject_rate']:.0%}.")
chart_rows = []
for s in stats:
    if s["decided"] == 0:
        continue
    chart_rows.append({"Guideline": s["source_id"], "Rate": "Override (edited)", "Value": s["override_rate"], "Decisions": s["decided"]})
    chart_rows.append({"Guideline": s["source_id"], "Rate": "Reject", "Value": s["reject_rate"], "Decisions": s["decided"]})
if chart_rows:
    df = pd.DataFrame(chart_rows)
    fig = px.bar(df, x="Guideline", y="Value", color="Rate", barmode="group", hover_data=["Decisions"],
                 color_discrete_map={"Override (edited)": theme.AMBER, "Reject": theme.RED})
    fig.update_layout(yaxis_tickformat=".0%", yaxis_title="Share of decisions", xaxis_title="",
                      legend_title="", height=360, margin=dict(l=10, r=10, t=10, b=10),
                      plot_bgcolor="white", paper_bgcolor="white", font=dict(color=theme.INK))
    fig.add_hline(y=th["reject_rate"], line_dash="dot", line_color=theme.RED, opacity=0.5)
    fig.add_hline(y=th["override_rate"], line_dash="dot", line_color=theme.AMBER, opacity=0.5)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
else:
    theme.empty_state("Findings were shown in this range, but nobody has decided on them yet.")

# ---------------------------------------------------------------- repeat issues
st.markdown(f'<div class="iw-section">Repeat issues by {group_pick.lower()}</div>', unsafe_allow_html=True)
if not repeats:
    theme.empty_state("No findings in this range.")
elif group_pick == "Category":
    dfc = pd.DataFrame(repeats)
    dfc["Category"] = dfc["category"].str.replace("_", " ").str.title()
    figc = px.bar(dfc, x="count", y="Category", orientation="h", hover_data=["creators"],
                  labels={"count": "Findings", "creators": "Creators"}, color_discrete_sequence=[theme.TEAL])
    figc.update_layout(height=max(220, 40 * len(dfc) + 60), margin=dict(l=10, r=10, t=10, b=10), yaxis_title="",
                       plot_bgcolor="white", paper_bgcolor="white", font=dict(color=theme.INK),
                       yaxis=dict(categoryorder="total ascending"))
    st.plotly_chart(figc, width="stretch", config={"displayModeBar": False})
    st.caption("Hover a bar to see how many different creators raised that category.")
else:
    st.caption(f"A creator who gets the same category {th['repeat_min']} or more times in the range is marked as a repeat.")
    dfr = pd.DataFrame([{"Creator": r["creator"], "Category": r["category"].replace("_", " ").title(),
                         "Findings": r["count"], "Repeat": "Yes" if r["repeat"] else ""} for r in repeats])
    st.dataframe(dfr, hide_index=True, width="stretch")

# ---------------------------------------------------------------- likely unclear
st.markdown('<div class="iw-section">Likely unclear guidelines</div>', unsafe_allow_html=True)
if not unclear:
    st.success("No guideline crosses the threshold in this range.")
for s in unclear:
    with st.container(border=True):
        h1, h2 = st.columns([5, 1.3])
        h1.markdown(f"**{s['source_id']} · {html.escape(s['title'])}**")
        h1.caption(f"{s['reason']} · shown {s['shown']}, accepted {s['accepted']}, edited {s['edited']}, rejected {s['rejected']}")
        h2.markdown('<span class="iw-pill bad">Likely unclear</span>', unsafe_allow_html=True)
        if s["accepted_rewording"]:
            st.markdown("**Current wording (accepted rewording):**")
            theme.source_quote(s["accepted_rewording"], s["source_id"], f"accepted by {s['accepted_by']}")
        key = f"rw_{s['source_id']}"
        if s["source_id"].startswith("G"):
            if st.button("Suggest clearer wording", key=f"sug_{s['source_id']}"):
                try:
                    with st.spinner("Drafting a clearer wording..."):
                        ss[key] = services.suggest_rewording(s["source_id"])
                except Exception as e:
                    st.error(f"Could not draft a rewording ({type(e).__name__}).")
            suggested = ss.get(key) or s["suggested_rewording"]
            if suggested:
                text = st.text_area("Suggested wording (edit before accepting)", value=suggested, key=f"txt_{s['source_id']}",
                                    height=90)
                if role == "Admin":
                    if st.button("Accept this wording", key=f"acc_{s['source_id']}", type="primary"):
                        try:
                            services.accept_rewording(s["source_id"], text, ss.user, role)
                        except Exception as e:
                            st.error(str(e))
                        else:
                            ss["flash"] = (f"{s['source_id']} reworded and logged in the audit trail. "
                                           "The new wording is used from the next review.")
                            st.rerun()
                else:
                    st.caption("Only an admin can accept a new wording. Sign in as `ravi` to accept it.")
        else:
            st.caption("Facts and glossary terms are not reworded here; renew facts in the Fact Register.")

# ---------------------------------------------------------------- full table
with st.expander("All guidelines in range"):
    dft = pd.DataFrame([{"ID": s["source_id"], "Title": s["title"], "Shown": s["shown"], "Decided": s["decided"],
                         "Accepted": s["accepted"], "Edited": s["edited"], "Rejected": s["rejected"],
                         "Override rate": f"{s['override_rate']:.0%}", "Reject rate": f"{s['reject_rate']:.0%}",
                         "Likely unclear": "Yes" if s["unclear"] else ""} for s in stats])
    st.dataframe(dft, hide_index=True, width="stretch")
    st.download_button("Download CSV", dft.to_csv(index=False).encode("utf-8"),
                       file_name="inkwise_insights.csv", mime="text/csv")

theme.ai_banner()
