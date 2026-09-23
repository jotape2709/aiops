from dataclasses import dataclass, replace
from hashlib import sha256

from src.config import CPU_HIGH_THRESHOLD, CPU_PERSISTENCE_POINTS, THRESHOLDS
from src.models import Link, Node, NodeType, Severity, Status
from src.network_topology import affected_services, unreachable_from_internet
from src.synthetic_data import Sample


@dataclass(frozen=True)
class Alert:
    id: str
    host: str
    metric: str
    severity: Severity
    value: float | str


@dataclass(frozen=True)
class Incident:
    id: str
    cause: str
    severity: Severity
    alerts: tuple[Alert, ...]
    affected_services: tuple[str, ...]


def _severity(metric: str, value: float) -> Severity | None:
    warning, critical = THRESHOLDS[metric]
    if value >= critical:
        return Severity.CRITICAL
    if value >= warning:
        return Severity.WARNING
    return None


def _persistent_high_cpu(series: tuple[float, ...]) -> bool:
    consecutive = 0
    for value in series:
        consecutive = consecutive + 1 if value > CPU_HIGH_THRESHOLD else 0
        if consecutive >= CPU_PERSISTENCE_POINTS:
            return True
    return False


def generate_alerts(
    nodes: tuple[Node, ...],
    links: tuple[Link, ...],
    cpu_series: dict[str, tuple[float, ...]] | None = None,
) -> tuple[Alert, ...]:
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
            if metric == "cpu" and _persistent_high_cpu((cpu_series or {}).get(node.id, ())):
                severity = Severity.CRITICAL
            if severity is not None:
                add(Alert(f"ALERT-{node.id}-{metric.upper()}", node.id, metric, severity, value))
    for link in links:
        if {link.source, link.target} & down_nodes:
            continue
        host = f"{link.source}--{link.target}"
        if link.status == Status.DOWN:
            add(Alert(f"ALERT-{host}-STATUS", host, "status", Severity.CRITICAL, "DOWN"))
            continue
        for metric in ("latency", "packet_loss"):
            value = getattr(link, metric)
            severity = _severity(metric, value)
            if severity is not None:
                add(Alert(f"ALERT-{host}-{metric.upper()}", host, metric, severity, value))
    return tuple(alerts)


def correlate(alerts: tuple[Alert, ...], sample: Sample) -> tuple[Incident, ...]:
    groups: dict[str, list[Alert]] = {}
    for alert in alerts:
        groups.setdefault(alert.host, []).append(alert)
    incidents = []
    for cause, group in groups.items():
        digest = sha256(cause.encode("utf-8")).hexdigest()[:10].upper()
        severity = (
            Severity.CRITICAL
            if any(alert.severity == Severity.CRITICAL for alert in group)
            else Severity.WARNING
        )
        isolated_nodes = tuple(
            node if node.id == cause else replace(node, status=Status.UP) for node in sample.nodes
        )
        isolated_links = tuple(
            link if f"{link.source}--{link.target}" == cause else replace(link, status=Status.UP)
            for link in sample.links
        )
        affected = tuple(
            sorted(
                service
                for service, status in affected_services(isolated_nodes, isolated_links).items()
                if status != Status.UP
            )
        )
        incidents.append(Incident(f"INC-{digest}", cause, severity, tuple(group), affected))
    return tuple(incidents)
