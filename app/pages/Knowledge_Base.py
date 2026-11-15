import html
import json
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

st.markdown("""<style>
.st-key-kb_focus { background:#fff; border:1px solid #12917F; border-radius:16px; padding:16px 20px;
  box-shadow:inset 4px 0 0 #12917F, 0 8px 24px rgba(18,145,127,.10); margin-bottom:10px; }
.kb-f-eb { font-size:.66rem; letter-spacing:.16em; font-weight:700; color:#12917F; }
.kb-f-t { font-size:1.15rem; color:#1B2A4E; font-weight:650; margin:4px 0 6px; }
.kb-f-b { font-size:.95rem; color:#1B2A4E; line-height:1.55; background:#F4F8F7; border-radius:10px; padding:10px 12px; }
.kb-f-m { font-size:.78rem; color:#5A6480; margin-top:8px; }
.kb-sw { display:flex; flex-wrap:wrap; gap:12px; margin:6px 0 14px; }
.kb-sw div { width:150px; border:1px solid #E2E7F0; border-radius:12px; overflow:hidden; background:#fff; }
.kb-sw i { display:block; height:46px; }
.kb-sw b { display:block; font-size:.78rem; color:#1B2A4E; padding:6px 10px 0; }
.kb-sw small { display:block; font-size:.7rem; color:#5A6480; padding:0 10px 8px; font-family:monospace; }
</style>""", unsafe_allow_html=True)

theme.page_header("Brand kit", "Brand kit",
                  "The guidelines, approved facts, glossary and image rules every review is checked against.")

try:
    kb = services.get_knowledge_base()
except services.BackendNotConnected as e:
    theme.not_connected(e)
    st.stop()
except Exception as e:
    st.error(f"The brand kit files could not be read ({type(e).__name__}: {e}). Check the JSON in data/brand_kit/.")
    st.stop()

try:
    visual = json.loads((Path(__file__).resolve().parents[2] / "data" / "brand_kit" / "visual.json").read_text("utf-8"))
except Exception:
    visual = {"palette": [], "rules": []}

# ---------------------------------------------------------------- opened from a finding (one click from Review)

focus = ss.get("kb_focus")
if focus:
    entry = (next((g for g in kb["guidelines"] if g["id"] == focus), None)
             or next((f for f in kb["facts"] if f["id"] == focus), None)
             or next((t for t in kb["glossary"] if t["id"] == focus), None)
             or next((r for r in visual.get("rules", []) if r["id"] == focus), None))
    with st.container(key="kb_focus"):
        if not entry:
            st.markdown(f'<div class="kb-f-eb">OPENED FROM A FINDING</div><div class="kb-f-t">{html.escape(focus)}</div>'
                        '<div class="kb-f-m">This source is not in the brand kit any more.</div>', unsafe_allow_html=True)
        else:
            kind = ("Guideline" if focus.startswith("G") else "Approved fact" if focus.startswith("F") else
                    "Glossary term" if focus.startswith("T") else "Image rule")
            if focus.startswith("G"):
                body, meta = entry["text"], f'Category: {entry.get("category", "")}'
                if entry.get("text") != entry.get("original_text"):
                    meta += " · reworded after Guideline insights"
                title = entry["title"]
            elif focus.startswith("F"):
                body, title = entry["text"], "Approved fact"
                state = ("expired on " if entry["expired"] else "valid until ") + str(entry["expires"]) if entry["expires"] \
                    else "does not expire"
                meta = f'Owner: {entry.get("owner", "")} · {state} · Source: {entry.get("source", "")}'
            elif focus.startswith("T"):
                title, body = f'Use “{entry["use"]}”', f'Avoid: {entry["avoid"]}'
                meta = entry.get("note", "")
            else:
                title, body, meta = entry["title"], entry["rule"], "Checked on images, without AI"
            st.markdown(f'<div class="kb-f-eb">OPENED FROM A FINDING · {kind.upper()}</div>'
                        f'<div class="kb-f-t">{html.escape(focus)} · {html.escape(str(title))}</div>'
                        f'<div class="kb-f-b">{html.escape(str(body))}</div>'
                        f'<div class="kb-f-m">{html.escape(str(meta))}</div>', unsafe_allow_html=True)
        c1, c2, _ = st.columns([1.2, 1, 3])
        try:
            c1.page_link("pages/1_Review.py", label="← Back to my review", width="stretch")
        except Exception:
            pass
        c2.button("Close", key="kb_close", on_click=ss.pop, args=("kb_focus", None), width="stretch")

q = st.text_input("Search", placeholder="Search guidelines, facts, glossary and image rules").strip().lower()


def match(*values) -> bool:
    return not q or q in " ".join(str(v) for v in values).lower()


guidelines = [g for g in kb["guidelines"] if match(g["id"], g["title"], g["text"])]
facts = [f for f in kb["facts"] if match(f["id"], f["text"], f.get("owner", ""))]
glossary = [t for t in kb["glossary"] if match(t["id"], t["avoid"], t["use"], t["note"])]
vrules = [r for r in visual.get("rules", []) if match(r["id"], r["title"], r["rule"])]

theme.stat_cards([
    (len(kb["guidelines"]), "Guidelines", "§", "#E8EEFB", "#1A4FB0"),
    (len(kb["facts"]), "Approved facts", "✓", "#E8F6F2", "#0B5E52"),
    (sum(f["expired"] for f in kb["facts"]), "Expired facts", "!", "#FDECEC", "#B42318"),
    (len(kb["glossary"]), "Glossary terms", "Aa", "#FFF4E0", "#8A4B06"),
])
st.write("")

tab_g, tab_f, tab_t, tab_v = st.tabs(["Guidelines", "Facts", "Glossary", "Image rules"])

with tab_g:
    if not guidelines:
        st.info("No guidelines match your search.")
    for g in guidelines:
        st.markdown(
            f'<div class="iw-card"><h4><span class="iw-pill ok">{g["id"]}</span> '
            f'{html.escape(str(g["title"]))}</h4><p>{html.escape(str(g["text"]))}</p></div>',
            unsafe_allow_html=True,
        )

with tab_f:
    if not facts:
        st.info("No facts match your search.")
    for f in facts:
        if f["expired"]:
            tag = f'<span class="iw-pill bad">Expired {f["expires"]}</span>'
        elif f["expires"]:
            tag = f'<span class="iw-pill ok">Valid until {f["expires"]}</span>'
        else:
            tag = '<span class="iw-pill ok">No expiry</span>'
        st.markdown(
            f'<div class="iw-card"><h4><span class="iw-pill open">{f["id"]}</span> {tag}</h4>'
            f'<p>{html.escape(str(f["text"]))}</p>'
            f'<p style="font-size:.78rem;color:#5A6480;margin:0">Owner: {html.escape(str(f.get("owner", "")))}'
            f' · Source: {html.escape(str(f.get("source", "")))}</p></div>',
            unsafe_allow_html=True,
        )

with tab_t:
    if not glossary:
        st.info("No glossary terms match your search.")
    else:
        df = pd.DataFrame(glossary).rename(
            columns={"id": "ID", "avoid": "Avoid", "use": "Use instead", "note": "Note"})
        st.dataframe(df, width="stretch", hide_index=True)

with tab_v:
    st.markdown('<div style="font-size:.86rem;color:#5A6480;margin:2px 0 6px">The Lumora palette. White, black and '
                'greys are always allowed.</div><div class="kb-sw">'
                + "".join(f'<div><i style="background:{html.escape(c["hex"])}"></i><b>{html.escape(c["name"])}</b>'
                          f'<small>{html.escape(c["hex"])}</small></div>' for c in visual.get("palette", []))
                + "</div>", unsafe_allow_html=True)
    if not vrules:
        st.info("No image rules match your search.")
    for r in vrules:
        st.markdown(f'<div class="iw-card"><h4><span class="iw-pill ok">{r["id"]}</span> {html.escape(r["title"])}</h4>'
                    f'<p>{html.escape(r["rule"])}</p></div>', unsafe_allow_html=True)

theme.footer()
