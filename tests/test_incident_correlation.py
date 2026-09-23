from dataclasses import replace

from src.incident_engine import correlate, generate_alerts
from src.models import Scenario, Severity, Status
from src.synthetic_data import generate_sample


def test_alerts_from_same_link_form_one_stable_incident() -> None:
    sample = generate_sample(42, Scenario.LINK_DEGRADED)
    alerts = generate_alerts(sample.nodes, sample.links, sample.cpu_series)
    incidents = correlate(alerts, sample)
    assert len(alerts) == 2
    assert len(incidents) == 1
    assert incidents[0].severity == Severity.WARNING
    assert incidents[0].affected_services == ("API", "DATABASE", "WEB")
    assert incidents == correlate(alerts, sample)
    assert incidents[0].id.startswith("INC-")


def test_critical_incident_counts_causes() -> None:
    for scenario in (Scenario.LINK_DOWN, Scenario.CORE_SWITCH_DOWN, Scenario.CPU_HIGH):
        sample = generate_sample(42, scenario)
        alerts = generate_alerts(sample.nodes, sample.links, sample.cpu_series)
        incidents = correlate(alerts, sample)
        assert len(incidents) == 1
        assert incidents[0].severity == Severity.CRITICAL


def test_each_incident_has_its_own_topology_impact() -> None:
    sample = generate_sample(42, Scenario.LINK_DEGRADED)
    nodes = tuple(
        replace(node, cpu=92.0, status=Status.DEGRADED) if node.id == "SRV-API-01" else node
        for node in sample.nodes
    )
    series = {**sample.cpu_series, "SRV-API-01": (92.0,) * 12}
    combined = replace(sample, nodes=nodes, cpu_series=series)
    incidents = correlate(generate_alerts(nodes, sample.links, series), combined)
    by_cause = {incident.cause: incident.affected_services for incident in incidents}
    assert by_cause["RTR-EDGE-01--FW-CORE-01"] == ("API", "DATABASE", "WEB")
    assert by_cause["SRV-API-01"] == ("API",)
