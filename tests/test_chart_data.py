from src.chart_data import latency_data, severity_data, utilization_data
from src.config import SLO_CRITICAL_FACTOR, SLO_WARNING_FACTOR
from src.incident_engine import correlate, generate_alerts
from src.models import Scenario
from src.synthetic_data import generate_sample


def test_latency_data_contains_series_and_configured_thresholds() -> None:
    sample = generate_sample(42)
    data = latency_data(sample)
    assert len(data.points) == 60
    assert data.points[0] == (1, sample.latency_series[0])
    baseline = sum(generate_sample(42).latency_series) / 60
    assert data.warning == baseline * SLO_WARNING_FACTOR
    assert data.critical == baseline * SLO_CRITICAL_FACTOR
    assert latency_data(generate_sample(42, Scenario.CORE_SWITCH_DOWN)).points == ()


def test_normal_slo_has_no_crossings_across_seeds_and_variants() -> None:
    for seed in range(200):
        for variant in range(3):
            data = latency_data(generate_sample(seed, Scenario.NORMAL, variant))
            assert all(value < data.warning for _, value in data.points)


def test_utilization_data_orders_top_eight_and_retains_down_links() -> None:
    normal = utilization_data(generate_sample(42).links)
    assert len(normal) == 8
    assert [item.utilization for item in normal] == sorted(
        (item.utilization for item in normal), reverse=True
    )
    assert all(item.band == "Normal" for item in normal)
    core = utilization_data(generate_sample(42, Scenario.CORE_SWITCH_DOWN).links)
    assert any(item.band == "Indisponível" for item in core)
    degraded = utilization_data(generate_sample(42, Scenario.LINK_DEGRADED).links)
    assert any(item.band == "Degradado" for item in degraded)


def test_severity_counts_only_supplied_active_incidents_and_empty() -> None:
    assert severity_data(()) == (("Crítico", 0), ("Aviso", 0))
    sample = generate_sample(42, Scenario.LINK_DEGRADED)
    incidents = correlate(generate_alerts(sample.nodes, sample.links, sample.cpu_series), sample)
    assert severity_data(incidents) == (("Crítico", 0), ("Aviso", 1))


def test_short_node_and_link_labels() -> None:
    from src.chart_data import short_link_label, short_node_id

    assert short_node_id("RTR-EDGE-01") == "EDGE1"
    assert short_node_id("FW-CORE-01") == "FW"
    assert short_node_id("SW-CORE-01") == "CORE"
    assert short_node_id("UNKNOWN-NODE") == "UNKNOWN-NODE"
    assert short_link_label("RTR-EDGE-01", "FW-CORE-01") == "EDGE1 → FW"


def test_unavailable_link_count_and_bands() -> None:
    from src.chart_data import UtilizationBand, unavailable_link_count
    from src.config import DOWN_LINKS_SHOWN

    normal_sample = generate_sample(42, Scenario.NORMAL)
    assert unavailable_link_count(normal_sample.links) == 0

    core_sample = generate_sample(42, Scenario.CORE_SWITCH_DOWN)
    down_count = unavailable_link_count(core_sample.links)
    assert down_count > DOWN_LINKS_SHOWN

    core_items = utilization_data(core_sample.links)
    assert sum(item.band == UtilizationBand.DOWN for item in core_items) == DOWN_LINKS_SHOWN

    # Bands must belong to UtilizationBand enum
    for scenario in Scenario:
        items = utilization_data(generate_sample(42, scenario).links)
        for item in items:
            assert isinstance(item.band, UtilizationBand)
            assert item.band in {
                UtilizationBand.NORMAL,
                UtilizationBand.CONGESTED,
                UtilizationBand.DEGRADED,
                UtilizationBand.DOWN,
            }
