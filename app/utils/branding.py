import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="INKWISE AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).parent
LOGO_PATH = BASE_DIR / "inkwise_logo.jpg"

st.markdown("""
<style>
.stApp {
    background-color: #F5F7FA;
}
[data-testid="stSidebar"] {
    background-color: #101D35;
}
[data-testid="stSidebar"] * {
    color: white !important;
}
.main-title {
    font-size: 36px;
    font-weight: 700;
    color: #142440;
}
.subtitle {
    color: #718096;
    font-size: 16px;
}
.metric-card {
    background: white;
    padding: 24px;
    border-radius: 12px;
    border: 1px solid #E5EAF1;
}
.metric-label {
    color: #718096;
    font-size: 14px;
}
.metric-value {
    color: #142440;
    font-size: 30px;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=170)

    st.markdown("## INKWISE AI")
    st.caption("Intelligent Content Governance")

    st.divider()

    st.page_link("Home.py", label="Dashboard", icon="🏠")
    st.page_link("branding.py", label="Branding", icon="🎨")
    st.page_link("_Approvals.py", label="Approvals", icon="✅")
    st.page_link("_History.py", label="History", icon="📋")
    st.page_link("_Knowledge_Base.py", label="Knowledge Base", icon="📚")

    st.divider()
    st.caption("INKWISE AI | Content Intelligence")

st.markdown('<div class="main-title">Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Welcome to your intelligent content governance workspace.</div>',
    unsafe_allow_html=True
)

st.write("")

col1, col2, col3, col4 = st.columns(4)

metrics = [
    ("Total Content", "128"),
    ("Pending Reviews", "12"),
    ("Approved Content", "96"),
    ("Flagged Items", "24")
]

for col, (label, value) in zip([col1, col2, col3, col4], metrics):
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.write("")
st.subheader("Quick Actions")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🎨  Manage Branding", use_container_width=True):
        st.switch_page("branding.py")

with col2:
    if st.button("✅  Review Approvals", use_container_width=True):
        st.switch_page("_Approvals.py")

with col3:
    if st.button("📚  Knowledge Base", use_container_width=True):
        st.switch_page("_Knowledge_Base.py")

st.write("")
st.subheader("Workspace Overview")

st.info(
    "Use the navigation panel to manage brand guidelines, "
    "review content approvals, access historical records, "
    "and explore your knowledge base."
)