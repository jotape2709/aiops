from html import escape

import streamlit as st

SIMULATION_BADGE_TEXT = "SIMULACAO NOC — dados 100% sinteticos"
REAL_BADGE_PREFIX = "DADOS PUBLICOS REAIS"


def _render_badge(text: str, css_class: str) -> None:
    st.markdown(
        f'<div class="data-source-badge {css_class}">{escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_simulation_badge() -> None:
    _render_badge(SIMULATION_BADGE_TEXT, "badge-simulation")


def render_real_badge(source: str = "RIPE Atlas") -> None:
    _render_badge(f"{REAL_BADGE_PREFIX} — {source}", "badge-real")
