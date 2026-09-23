import streamlit as st

from src.root_cause import RootCauseAnalysis


def render_analysis(analysis: RootCauseAnalysis) -> None:
    st.markdown("#### Causa raiz provável")
    if analysis.root_cause is None:
        st.success("Nenhuma anomalia relevante.")
        return
    st.markdown("**CAUSA RAIZ PROVÁVEL**")
    st.write(analysis.root_cause)
    st.markdown("**EVIDÊNCIAS**")
    for evidence in analysis.evidences:
        st.write(f"• {evidence}")
    st.markdown("**IMPACTO**")
    for service, status in analysis.impact:
        st.write(f"• {service}: {status}")
    st.markdown("**AÇÃO RECOMENDADA**")
    for index, action in enumerate(analysis.actions, start=1):
        st.write(f"{index}. {action}")
