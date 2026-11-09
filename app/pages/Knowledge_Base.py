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

st.title("Knowledge Base")
st.caption("The brand rules every review is checked against.")

try:
    kb = services.get_knowledge_base()
except services.BackendNotConnected as e:
    theme.not_connected(e)
    st.stop()
except Exception as e:
    st.error(f"The brand kit files could not be read ({type(e).__name__}: {e}). Check the JSON in data/brand_kit/.")
    st.stop()

q = st.text_input("Search", placeholder="Search guidelines, facts and glossary").strip().lower()


def match(*values) -> bool:
    return not q or q in " ".join(str(v) for v in values).lower()


guidelines = [g for g in kb["guidelines"] if match(g["id"], g["title"], g["text"])]
facts = [f for f in kb["facts"] if match(f["id"], f["text"])]
glossary = [t for t in kb["glossary"] if match(t["id"], t["avoid"], t["use"], t["note"])]

m = st.columns(3)
m[0].metric("Guidelines", len(kb["guidelines"]))
m[1].metric("Facts", len(kb["facts"]))
m[2].metric("Expired facts", sum(f["expired"] for f in kb["facts"]))

tab_g, tab_f, tab_t = st.tabs(["Guidelines", "Facts", "Glossary"])

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
            f'<p>{html.escape(str(f["text"]))}</p></div>',
            unsafe_allow_html=True,
        )

with tab_t:
    if not glossary:
        st.info("No glossary terms match your search.")
    else:
        df = pd.DataFrame(glossary).rename(
            columns={"id": "ID", "avoid": "Avoid", "use": "Use instead", "note": "Note"})
        st.dataframe(df, use_container_width=True, hide_index=True)