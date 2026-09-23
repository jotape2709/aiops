import streamlit as st

from src.config import DEFAULT_SEED
from src.kpis import compute_kpis
from src.models import Scenario
from src.synthetic_data import Sample, generate_sample
from src.ui.cards import render_kpis
from src.ui.real_data import render_real_data
from src.ui.theme import apply_theme
from src.ui.topology import topology_figure

st.set_page_config(page_title="AIOps Network Operations Center", layout="wide")
apply_theme()

if "scenario" not in st.session_state:
    st.session_state.scenario = Scenario.NORMAL
if "seed" not in st.session_state:
    st.session_state.seed = DEFAULT_SEED
if "sample_index" not in st.session_state:
    st.session_state.sample_index = 0
if "sample" not in st.session_state:
    st.session_state.sample = generate_sample(DEFAULT_SEED, Scenario.NORMAL)

st.sidebar.title("AIOps NOC")
choice = st.sidebar.selectbox(
    "Cenário",
    options=list(Scenario),
    format_func=lambda item: "Normal" if item == Scenario.NORMAL else "Core switch down",
    key="scenario",
)
seed = st.sidebar.number_input("Seed", min_value=0, step=1, key="seed")
regenerate = st.sidebar.button("Gerar nova amostra")
sample: Sample = st.session_state.sample
if sample.scenario != choice or sample.seed != seed:
    st.session_state.sample_index = 0
elif regenerate:
    st.session_state.sample_index += 1
if (
    sample.scenario != choice
    or sample.seed != seed
    or sample.variant != st.session_state.sample_index
):
    sample = generate_sample(seed, choice, st.session_state.sample_index)
    st.session_state.sample = sample
st.sidebar.caption(f"Amostra #{st.session_state.sample_index + 1}")

st.title("AIOps Network Operations Center")
st.caption("Laboratório sintético de NOC + dados públicos reais da Internet, em abas separadas")

noc_tab, real_tab = st.tabs(
    ["Laboratório NOC (sintético)", "Internet pública — RIPE Atlas (dados reais)"],
    key="main_tabs",
    on_change="rerun",
)
with noc_tab:
    if noc_tab.open:
        st.caption(
            "Laboratório de observabilidade e análise de incidentes com dados 100% sintéticos"
        )
        kpis = compute_kpis(sample)
        render_kpis(
            (
                ("Disponibilidade", f"{kpis.availability:.1f}%"),
                ("Alertas ativos", str(kpis.active_alerts)),
                ("Incidentes críticos", str(kpis.critical_incidents)),
                ("Serviços impactados", str(kpis.impacted_services)),
                ("Latência média", f"{kpis.mean_latency:.1f} ms"),
            )
        )
        st.subheader("Topologia da rede")
        st.plotly_chart(topology_figure(sample.nodes, sample.links), width="stretch")

with real_tab:
    if real_tab.open:
        render_real_data()
