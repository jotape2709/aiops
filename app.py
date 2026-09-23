import streamlit as st

from src.config import DEFAULT_SEED
from src.kpis import compute_kpis
from src.models import Scenario
from src.root_cause import analyze
from src.simulation_state import change_seed, initial_state, resample, restore, simulate
from src.ui.cards import render_kpis
from src.ui.real_data import render_real_data
from src.ui.root_cause import render_analysis
from src.ui.theme import apply_theme
from src.ui.topology import topology_figure

SCENARIO_LABELS = {
    Scenario.LINK_DEGRADED: "Link degradado",
    Scenario.LINK_DOWN: "Link down",
    Scenario.CORE_SWITCH_DOWN: "Core switch down",
    Scenario.CPU_HIGH: "CPU alta",
}

st.set_page_config(page_title="AIOps Network Operations Center", layout="wide")
apply_theme()

if "selected_scenario" not in st.session_state:
    st.session_state.selected_scenario = Scenario.LINK_DEGRADED
if "seed" not in st.session_state:
    st.session_state.seed = DEFAULT_SEED
if "sample_index" not in st.session_state:
    st.session_state.sample_index = 0
if "simulation_state" not in st.session_state:
    st.session_state.simulation_state = initial_state(DEFAULT_SEED)

st.sidebar.title("AIOps NOC")
choice = st.sidebar.selectbox(
    "Cenário a simular",
    options=[scenario for scenario in Scenario if scenario != Scenario.NORMAL],
    format_func=lambda item: SCENARIO_LABELS[item],
    key="selected_scenario",
)
seed = st.sidebar.number_input("Seed", min_value=0, step=1, key="seed")
state = st.session_state.simulation_state
if seed != state.sample.seed:
    st.session_state.sample_index = 0
    state = change_seed(state, seed)
simulate_clicked = st.sidebar.button("Simular incidente", disabled=choice == state.sample.scenario)
restore_clicked = st.sidebar.button("Restaurar ambiente")
regenerate_clicked = st.sidebar.button("Gerar nova amostra")

if simulate_clicked:
    state = simulate(state, choice)
elif restore_clicked:
    state = restore(state)
elif regenerate_clicked:
    st.session_state.sample_index += 1
    state = resample(state, st.session_state.sample_index)
st.session_state.simulation_state = state
if simulate_clicked or restore_clicked or regenerate_clicked:
    st.rerun()
sample = state.sample
st.sidebar.caption(f"Amostra #{st.session_state.sample_index + 1}")
st.sidebar.caption(f"Cenário ativo: {SCENARIO_LABELS.get(sample.scenario, 'Normal')}")

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
                (
                    "Latência média",
                    f"{kpis.mean_latency:.1f} ms" if kpis.mean_latency is not None else "N/D",
                ),
            )
        )
        st.caption(f"Eventos no histórico: {len(state.history)}")
        analysis = analyze(sample)
        topology_column, analysis_column = st.columns([2, 1])
        with topology_column:
            st.subheader("Topologia da rede")
            st.plotly_chart(
                topology_figure(sample.nodes, sample.links, analysis.component_id),
                width="stretch",
            )
        with analysis_column:
            render_analysis(analysis)

with real_tab:
    if real_tab.open:
        render_real_data()
