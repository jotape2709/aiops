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
        .noc-hint { color: #8fa3c4; font-size: 0.72rem; margin-top: 4px; }
        .data-source-badge { display: inline-flex; align-items: center; gap: 8px;
            padding: 5px 14px; border-radius: 999px; border: 1px solid;
            font-size: 0.78rem; font-weight: 700; letter-spacing: 0.05em;
            margin: 0 0 6px 0; }
        .data-source-badge::before { content: ""; width: 8px; height: 8px;
            border-radius: 50%; background: currentColor;
            box-shadow: 0 0 6px currentColor; }
        .badge-simulation { color: #d9c9ff; border-color: #9b7bff;
            background: rgba(155, 123, 255, 0.12); }
        .badge-real { color: #9df0d5; border-color: #33d6a6;
            background: rgba(51, 214, 166, 0.10); }
        </style>""",
        unsafe_allow_html=True,
    )
