"""Fact Register (Round 3, Improvement 2): every approved fact sorted by risk, with renewal."""
import datetime as dt
import html
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
import pandas as pd
import streamlit as st
import services
import theme

st.set_page_config(page_title="inkwise.ai", page_icon="✒️", layout="wide")
theme.render_shell()
ss = st.session_state

st.title("Fact Register")
st.caption("Approved facts with an owner and an expiry date. Expired facts are flagged in every review "
           "until the owner re-verifies them.")

LABEL = {"expired": ("Expired", "bad"), "expiring_soon": ("Expiring soon", "open"), "valid": ("Valid", "ok")}

try:
    owners = services.fact_owners()
    all_facts = services.fact_register()
except services.BackendNotConnected as e:
    theme.not_connected(e)
    st.stop()
except Exception as e:
    st.error(f"The fact register could not load ({type(e).__name__}). Check data/brand_kit/facts.json.")
    st.stop()

n_exp = sum(f["status"] == "expired" for f in all_facts)
n_soon = sum(f["status"] == "expiring_soon" for f in all_facts)
theme.metric_row([
    (len(all_facts), "Facts", ""),
    (n_exp, "Expired", "warn" if n_exp else ""),
    (n_soon, "Expiring in 30 days", "warn" if n_soon else ""),
    (len(all_facts) - n_exp - n_soon, "Valid", "ok"),
])

f1, f2, f3 = st.columns([1.2, 1.2, 2])
status_pick = f1.selectbox("Status", ["All", "Expired", "Expiring soon", "Valid"])
owner_pick = f2.selectbox("Owner", ["All owners"] + owners)
query = f3.text_input("Search", placeholder="Search facts by id or wording").strip().lower()

status_key = {"All": None, "Expired": "expired", "Expiring soon": "expiring_soon", "Valid": "valid"}[status_pick]
facts = [f for f in all_facts
         if (status_key is None or f["status"] == status_key)
         and (owner_pick == "All owners" or f["owner"] == owner_pick)
         and (not query or query in f"{f['id']} {f['statement']} {f['owner']}".lower())]

if not all_facts:
    theme.empty_state("No facts in the brand kit yet. Add them to data/brand_kit/facts.json.")
    st.stop()
if not facts:
    st.warning("No facts match those filters.")
    st.stop()


def days_text(f) -> str:
    d = f["days_left"]
    if d is None:
        return "Does not expire"
    if d < 0:
        return f"{-d} day{'s' if d != -1 else ''} ago"
    if d == 0:
        return "Today"
    return f"in {d} day{'s' if d != 1 else ''}"


rows = [{"ID": f["id"], "Status": LABEL[f["status"]][0], "Fact": f["statement"], "Owner": f["owner"],
         "Expires": f["expires_on"] or "—", "When": days_text(f),
         "Last renewed": f"{f['renewed_at']} by {f['renewed_by']}" if f["renewed_by"] else ""}
        for f in facts]
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
             column_config={"Fact": st.column_config.TextColumn(width="large")})

st.markdown('<div class="iw-section">Renew or re-verify a fact</div>', unsafe_allow_html=True)
role = ss.get("role", "Creator")
user = ss.get("user", "")
if role == "Creator" and not ss.get("team"):
    st.info("Renewals are made by the team that owns a fact, or by an admin. You can read the register and see who to ask.")

at_risk = [f for f in facts if f["status"] != "valid"] or facts
pick = st.selectbox("Fact", [f"{f['id']} · {f['statement'][:80]}" for f in at_risk])
fact = at_risk[[f"{f['id']} · {f['statement'][:80]}" for f in at_risk].index(pick)]
allowed = services.can_renew(user, role, fact["owner"])

with st.container(border=True):
    label, cls = LABEL[fact["status"]]
    st.markdown(f"**{fact['id']}** · <span class='iw-pill {cls}'>{label}</span> · owner **{html.escape(fact['owner'])}** · "
                f"source: {html.escape(fact['source'])}", unsafe_allow_html=True)
    st.write(fact["statement"])
    if fact["renewed_by"]:
        st.caption(f"Last renewed {fact['renewed_at']} UTC by {fact['renewed_by']}"
                   + (f" · “{fact['renew_note']}”" if fact["renew_note"] else ""))
    if not allowed:
        st.caption(f"Only {fact['owner']} or an admin can renew this fact. Sign in as `ravi` (Admin) to try it.")
    with st.form(f"renew_{fact['id']}", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        new_date = c1.date_input("New expiry date", value=dt.date.today() + dt.timedelta(days=180),
                                 min_value=dt.date.today() + dt.timedelta(days=1))
        note = c2.text_input("Verification note", placeholder="e.g. confirmed against the Q3 2026 investor update")
        go = st.form_submit_button("Renew and re-check open drafts", type="primary", disabled=not allowed)
    if go:
        try:
            out = services.renew_fact(fact["id"], user, role, new_date.isoformat(), note)
        except Exception as e:
            st.error(str(e))
        else:
            n = len(out.get("rechecked", []))
            st.success(f"{fact['id']} now expires on {out['expires_on']}. "
                       f"{n} open draft{'s' if n != 1 else ''} re-checked, {out.get('cleared', 0)} finding(s) cleared. "
                       "Logged in the audit trail.")
            st.rerun()

st.markdown('<div class="iw-section">Renewal history</div>', unsafe_allow_html=True)
try:
    log = services.global_audit(50, "fact_renewed") + services.global_audit(50, "rechecked")
except Exception:
    log = []
log.sort(key=lambda a: a["at"], reverse=True)
if not log:
    theme.empty_state("No renewals yet. The first renewal will appear here with who did it and when.")
else:
    for a in log[:20]:
        st.markdown(f"- `{a['at'][:16].replace('T', ' ')}` **{html.escape(a['user'])}** · "
                    f"{a['action'].replace('_', ' ')} · {html.escape(a['detail'])}"
                    + (f" · “{html.escape(a['title'])}”" if a.get("title") else ""))

theme.ai_banner()
