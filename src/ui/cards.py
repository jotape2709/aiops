from html import escape

import streamlit as st


def render_kpis(values: tuple[tuple[str, str], ...]) -> None:
    for column, (label, value) in zip(st.columns(5), values, strict=True):
        with column:
            st.markdown(
                f'<div class="noc-card"><div class="noc-label">{escape(label)}</div>'
                f'<div class="noc-value">{escape(value)}</div></div>',
                unsafe_allow_html=True,
            )
