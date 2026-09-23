from src.chart_data import LinkUtilization, UtilizationBand, severity_data, utilization_data
from src.config import CONGESTION_THRESHOLD_PCT
from src.models import Scenario
from src.simulation_state import initial_state, simulate
from src.ui.charts import BAND_COLORS, severity_figure, utilization_figure


def test_band_colors_cover_every_member() -> None:
    assert set(BAND_COLORS) == set(UtilizationBand)
    for band in UtilizationBand:
        assert BAND_COLORS[band].startswith("#")


def test_severity_figure_renders_real_severity_data_empty() -> None:
    payload = severity_figure(severity_data(())).to_plotly_json()
    assert list(payload["data"][0]["x"]) == ["Crítico", "Aviso"]
    assert list(payload["data"][0]["y"]) == [0, 0]
    annotations = payload["layout"].get("annotations", [])
    assert any(item["text"] == "Nenhum incidente ativo" for item in annotations)


def test_severity_figure_renders_real_severity_data_with_incidents() -> None:
    state = simulate(initial_state(42), Scenario.LINK_DOWN)
    assert state.active_incidents
    payload = severity_figure(severity_data(state.active_incidents)).to_plotly_json()
    assert list(payload["data"][0]["x"]) == ["Crítico", "Aviso"]
    assert sum(payload["data"][0]["y"]) == len(state.active_incidents)
    assert not payload["layout"].get("annotations")


def test_utilization_empty_state_shows_message() -> None:
    payload = utilization_figure(()).to_plotly_json()
    assert payload["data"] == []
    annotations = payload["layout"]["annotations"]
    assert [item["text"] for item in annotations] == ["Nenhum link monitorado"]
    assert payload["layout"]["xaxis"]["showgrid"] is False
    assert payload["layout"]["xaxis"]["showticklabels"] is False


def test_utilization_with_data_keeps_bars_and_congestion_line() -> None:
    data = (
        LinkUtilization("CORE → ACC1", "SW-CORE-01 ↔ SW-ACCESS-01", 0.0, UtilizationBand.DOWN),
        LinkUtilization("EDGE1 → FW", "RTR-EDGE-01 ↔ FW-CORE-01", 42.0, UtilizationBand.NORMAL),
    )
    payload = utilization_figure(data).to_plotly_json()
    assert len(payload["data"]) == 2
    assert payload["data"][0]["text"] == ["Indisponível"]
    assert payload["layout"]["shapes"]
    texts = [item["text"] for item in payload["layout"].get("annotations", [])]
    assert f"Congestionamento {CONGESTION_THRESHOLD_PCT:.0f}%" in texts


def test_utilization_renders_real_band_data_from_core() -> None:
    state = simulate(initial_state(42), Scenario.CORE_SWITCH_DOWN)
    payload = utilization_figure(utilization_data(state.sample.links)).to_plotly_json()
    assert payload["data"]
