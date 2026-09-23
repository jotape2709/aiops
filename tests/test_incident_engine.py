from dataclasses import replace

from src.incident_engine import generate_alerts
from src.models import Scenario, Severity, Status
from src.synthetic_data import generate_sample


def test_thresholds_and_deterministic_ids() -> None:
    sample = generate_sample(42)
    node = replace(sample.nodes[1], packet_loss=10, latency=80, cpu=95, memory=85)
    alerts = generate_alerts((node,), ())
    assert {alert.metric: alert.severity for alert in alerts} == {
        "packet_loss": Severity.CRITICAL,
        "latency": Severity.WARNING,
        "cpu": Severity.CRITICAL,
        "memory": Severity.WARNING,
    }
    assert alerts == generate_alerts((node,), ())


def test_down_suppresses_redundant_node_metrics_and_deduplicates() -> None:
    sample = generate_sample(42)
    node = replace(sample.nodes[1], status=Status.DOWN, cpu=99)
    alerts = generate_alerts((node, node), ())
    assert len(alerts) == 1
    assert alerts[0].id == "ALERT-RTR-EDGE-01-STATUS"


def test_core_down_has_only_root_cause_alert() -> None:
    sample = generate_sample(42, Scenario.CORE_SWITCH_DOWN)
    alerts = generate_alerts(sample.nodes, sample.links)
    assert len(alerts) == 1
    assert alerts[0].id == "ALERT-SW-CORE-01-STATUS"
    assert alerts[0].severity == Severity.CRITICAL
