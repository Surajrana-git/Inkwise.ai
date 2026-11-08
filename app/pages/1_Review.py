"""Review page. Owner: Aashi (Step 5).
Uses MOCK findings until Riyana's engine/review.py is ready (Step 4).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from engine.schemas import CheckedBy, Category, Finding

st.title("Review content")

MOCK = [
    Finding(id="f-001", category=Category.CLAIM, span="the fastest payments app in India",
            source_id="UNVERIFIED", why="No approved fact supports this superlative claim.",
            suggested_fix="a fast, reliable way to pay", confidence=0.82, checked_by=CheckedBy.AI),
    Finding(id="f-002", category=Category.TERMINOLOGY, span="LumoraPay", source_id="T01",
            source_text="Approved: 'Lumora Pay' (two words)", why="Banned variant of a product name.",
            suggested_fix="Lumora Pay", confidence=1.0, checked_by=CheckedBy.RULE),
]

text = st.text_area("Paste your content", height=180)
if st.button("Review", type="primary", disabled=not text.strip()):
    st.session_state["findings"] = MOCK  # TODO Step 5: engine.review.review_text(text).findings

for f in st.session_state.get("findings", []):
    with st.container(border=True):
        badge = "⚠️ UNVERIFIED" if not f.is_verified else f"Source {f.source_id}"
        st.markdown(f"**{f.category.value.replace('_', ' ').title()}** · {badge} · "
                    f"confidence {f.confidence:.0%} · checked by {f.checked_by.value}")
        st.markdown(f"Flagged: `{f.span}`")
        if f.source_text:
            st.caption(f.source_text)
        st.write(f.why)
        st.success(f"Suggested fix: {f.suggested_fix}")
