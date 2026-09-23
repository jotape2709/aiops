from dataclasses import dataclass

from src.incident_engine import generate_alerts
from src.models import NodeType, Severity
from src.network_topology import unreachable_from_internet
from src.synthetic_data import Sample


@dataclass(frozen=True)
class Kpis:
    availability: float
    active_alerts: int
    critical_incidents: int
    impacted_services: int
    mean_latency: float


def compute_kpis(sample: Sample) -> Kpis:
    unreachable, services = unreachable_from_internet(sample.nodes, sample.links)
    monitored = [node for node in sample.nodes if node.type != NodeType.INTERNET]
    reachable_count = sum(node.id not in unreachable for node in monitored)
    alerts = generate_alerts(sample.nodes, sample.links)
    return Kpis(
        availability=100.0 * reachable_count / len(monitored),
        active_alerts=len(alerts),
        critical_incidents=sum(alert.severity == Severity.CRITICAL for alert in alerts),
        impacted_services=len(services),
        mean_latency=sum(sample.latency_series) / len(sample.latency_series),
    )
