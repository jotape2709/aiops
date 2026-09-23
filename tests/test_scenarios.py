from src.incident_engine import generate_alerts
from src.kpis import compute_kpis
from src.models import Scenario, Severity, Status
from src.network_topology import affected_services, unreachable_from_internet
from src.synthetic_data import generate_sample


def test_all_scenarios_are_reproducible() -> None:
    for scenario in Scenario:
        assert generate_sample(42, scenario, 2) == generate_sample(42, scenario, 2)


def test_link_degraded_has_partial_impact_and_warning() -> None:
    sample = generate_sample(42, Scenario.LINK_DEGRADED)
    link = next(
        link for link in sample.links if {link.source, link.target} == {"RTR-EDGE-01", "FW-CORE-01"}
    )
    backup = next(
        link for link in sample.links if {link.source, link.target} == {"RTR-EDGE-02", "FW-CORE-01"}
    )
    assert link.status == Status.DEGRADED
    assert link.latency >= 80 and 3 <= link.packet_loss < 10
    assert backup.utilization > link.utilization
    _, unavailable = unreachable_from_internet(sample.nodes, sample.links)
    assert not unavailable
    assert all(node.status == Status.UP for node in sample.nodes)
    assert {
        service
        for service, status in affected_services(sample.nodes, sample.links).items()
        if status == Status.DEGRADED
    } == {"WEB", "DATABASE", "API"}
    alerts = generate_alerts(sample.nodes, sample.links, sample.cpu_series)
    assert len(alerts) == 2
    assert all(alert.severity == Severity.WARNING for alert in alerts)
    assert compute_kpis(sample).impacted_services == 3


def test_link_down_uses_cross_link_and_degrades_web() -> None:
    sample = generate_sample(42, Scenario.LINK_DOWN)
    _, unavailable = unreachable_from_internet(sample.nodes, sample.links)
    assert not unavailable
    assert affected_services(sample.nodes, sample.links)["WEB"] == Status.DEGRADED
    cross_link = next(
        link
        for link in sample.links
        if {link.source, link.target} == {"SW-ACCESS-01", "SW-ACCESS-02"}
    )
    assert cross_link.utilization >= 85
    alerts = generate_alerts(sample.nodes, sample.links, sample.cpu_series)
    assert len(alerts) == 1 and alerts[0].severity == Severity.CRITICAL
    assert compute_kpis(sample).impacted_services == 1


def test_cpu_high_persistence_changes_severity() -> None:
    sample = generate_sample(42, Scenario.CPU_HIGH)
    assert len(sample.cpu_series["SRV-API-01"]) == 12
    assert all(value > 90 for value in sample.cpu_series["SRV-API-01"])
    assert next(node.status for node in sample.nodes if node.id == "SRV-API-01") == Status.DEGRADED
    assert affected_services(sample.nodes, sample.links)["API"] == Status.DEGRADED
    persistent = generate_alerts(sample.nodes, sample.links, sample.cpu_series)
    short = generate_alerts(sample.nodes, sample.links, {"SRV-API-01": (91.0, 92.0, 93.0, 20.0)})
    assert len(persistent) == len(short) == 1
    assert persistent[0].severity == Severity.CRITICAL
    assert short[0].severity == Severity.WARNING
    assert compute_kpis(sample).impacted_services == 1


def test_core_down_remains_critical_with_three_unavailable_services() -> None:
    sample = generate_sample(42, Scenario.CORE_SWITCH_DOWN)
    _, unavailable = unreachable_from_internet(sample.nodes, sample.links)
    assert unavailable == {"WEB", "DATABASE", "API"}
    kpis = compute_kpis(sample)
    assert kpis.critical_incidents == 1
    assert kpis.impacted_services == 3


def test_cpu_persistence_uses_series_of_the_alerting_node() -> None:
    from dataclasses import replace

    sample = generate_sample(42)
    router = next(node for node in sample.nodes if node.id == "RTR-EDGE-01")
    high = replace(router, cpu=91.0)
    alerts = generate_alerts((high,), (), {router.id: (91.0,) * 12})
    assert len(alerts) == 1 and alerts[0].severity == Severity.CRITICAL
