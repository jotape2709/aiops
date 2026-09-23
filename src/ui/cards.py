from html import escape

import streamlit as st


def kpi_card_html(label: str, value: str, hint: str | None = None) -> str:
    hint_html = f'<div class="noc-hint">{escape(hint)}</div>' if hint else ""
    return (
        f'<div class="noc-card"><div class="noc-label">{escape(label)}</div>'
        f'<div class="noc-value">{escape(value)}</div>{hint_html}</div>'
    )


def render_kpis(values: tuple[tuple[str, ...], ...]) -> None:
    for column, item in zip(st.columns(5), values, strict=True):
        with column:
            st.markdown(kpi_card_html(*item), unsafe_allow_html=True)
