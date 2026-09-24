import streamlit as st

from src.chart_data import latency_data, severity_data, unavailable_link_count, utilization_data
from src.config import DEFAULT_SEED, DOWN_LINKS_SHOWN
from src.event_data import event_rows
from src.kpis import compute_kpis
from src.models import Scenario
from src.root_cause import analyze
from src.simulation_state import change_seed, initial_state, resample, restore, simulate
from src.ui.badges import render_real_badge, render_simulation_badge
from src.ui.cards import render_kpis
from src.ui.charts import latency_figure, severity_figure, utilization_figure
from src.ui.event_table import render_event_table
from src.ui.peeringdb import render_peeringdb
from src.ui.real_data import render_real_data
from src.ui.ripestat import render_ripestat
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
restore_clicked = st.sidebar.button(
    "Restaurar ambiente",
    disabled=state.sample.scenario == Scenario.NORMAL and not state.active_incidents,
)
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

noc_tab, real_tab, peering_tab, ripestat_tab = st.tabs(
    [
        "Laboratório NOC (sintético)",
        "Internet pública — RIPE Atlas (dados reais)",
        "Internet pública — PeeringDB (dados reais)",
        "Internet pública — RIPEstat (dados reais)",
    ],
    key="main_tabs",
    on_change="rerun",
)
with noc_tab:
    if noc_tab.open:
        render_simulation_badge()
        st.caption(
            "Laboratório de observabilidade e análise de incidentes com dados 100% sintéticos"
        )
        kpis = compute_kpis(sample)
        render_kpis(
            (
                (
                    "Disponibilidade",
                    f"{kpis.availability:.1f}%",
                    "equipamentos alcançáveis",
                ),
                ("Alertas ativos", str(kpis.active_alerts)),
                ("Incidentes críticos", str(kpis.critical_incidents)),
                ("Serviços impactados", str(kpis.impacted_services)),
                (
                    "Latência média",
                    f"{kpis.mean_latency:.1f} ms" if kpis.mean_latency is not None else "N/D",
                ),
            )
        )
        if kpis.mean_latency is None:
            st.caption("Latência média: nenhum serviço alcançável a partir da Internet.")
        st.caption(f"Eventos no histórico: {len(state.history)}")
        analysis = analyze(sample)
        topology_column, analysis_column = st.columns([2, 1])
        with topology_column:
            st.markdown("#### Topologia da rede")
            st.plotly_chart(
                topology_figure(
                    sample.nodes,
                    sample.links,
                    analysis.component_kind,
                    analysis.component_nodes,
                ),
                width="stretch",
            )
        with analysis_column:
            render_analysis(analysis)

        latency_column, utilization_column, severity_column = st.columns(3)
        with latency_column:
            st.markdown("#### Latência fim a fim")
            st.plotly_chart(latency_figure(latency_data(sample)), width="stretch")
        with utilization_column:
            st.markdown("#### Utilização de links")
            st.plotly_chart(utilization_figure(utilization_data(sample.links)), width="stretch")
            unavailable = unavailable_link_count(sample.links)
            if unavailable > DOWN_LINKS_SHOWN:
                st.caption(
                    f"{unavailable} links indisponíveis; mostrando os {DOWN_LINKS_SHOWN} principais."
                )
        with severity_column:
            st.markdown("#### Incidentes ativos")
            st.plotly_chart(severity_figure(severity_data(state.active_incidents)), width="stretch")

        st.subheader("Eventos recentes")
        render_event_table(event_rows(state.history))

with real_tab:
    if real_tab.open:
        render_real_badge()
        render_real_data()

with peering_tab:
    if peering_tab.open:
        render_real_badge("PeeringDB")
        render_peeringdb()

with ripestat_tab:
    if ripestat_tab.open:
        render_real_badge("RIPEstat")
        render_ripestat()
