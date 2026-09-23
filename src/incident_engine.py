from dataclasses import dataclass

from src.config import THRESHOLDS
from src.models import Link, Node, NodeType, Severity, Status
from src.network_topology import unreachable_from_internet


@dataclass(frozen=True)
class Alert:
    id: str
    host: str
    metric: str
    severity: Severity
    value: float | str


def _severity(metric: str, value: float) -> Severity | None:
    warning, critical = THRESHOLDS[metric]
    if value >= critical:
        return Severity.CRITICAL
    if value >= warning:
        return Severity.WARNING
    return None


def generate_alerts(nodes: tuple[Node, ...], links: tuple[Link, ...]) -> tuple[Alert, ...]:
    unreachable = set()
    if any(node.id == "INTERNET" for node in nodes):
        unreachable, _ = unreachable_from_internet(nodes, links)
    down_nodes = {node.id for node in nodes if node.status == Status.DOWN}
    alerts: list[Alert] = []
    seen: set[tuple[str, str]] = set()

    def add(alert: Alert) -> None:
        key = (alert.host, alert.metric)
        if key not in seen:
            seen.add(key)
            alerts.append(alert)

    for node in nodes:
        if node.type == NodeType.INTERNET:
            continue
        if node.type == NodeType.SERVICE and node.id in unreachable:
            continue
        if node.status == Status.DOWN:
            add(Alert(f"ALERT-{node.id}-STATUS", node.id, "status", Severity.CRITICAL, "DOWN"))
            continue
        for metric in THRESHOLDS:
            value = getattr(node, metric)
            if value is None:
                continue
            severity = _severity(metric, value)
            if severity is not None:
                add(Alert(f"ALERT-{node.id}-{metric.upper()}", node.id, metric, severity, value))
    for link in links:
        if link.status == Status.DOWN and not ({link.source, link.target} & down_nodes):
            host = f"{link.source}--{link.target}"
            add(Alert(f"ALERT-{host}-STATUS", host, "status", Severity.CRITICAL, "DOWN"))
    return tuple(alerts)
