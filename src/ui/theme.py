import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """<style>
        .stApp { background: #0b1020; color: #e8ecf7; }
        [data-testid="stSidebar"] { background: #111a2d; }
        .noc-card { background: #172239; border: 1px solid #2b3852;
            border-radius: 12px; padding: 16px; min-height: 94px; }
        .noc-label { color: #b6c5dd; font-size: 0.82rem; }
        .noc-value { color: #eaf4ff; font-size: 1.65rem; font-weight: 700; }
        </style>""",
        unsafe_allow_html=True,
    )
