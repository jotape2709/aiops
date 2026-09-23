from dataclasses import dataclass
from enum import Enum

from src.config import (
    CONGESTION_THRESHOLD_PCT,
    DOWN_LINKS_SHOWN,
    SLO_CRITICAL_FACTOR,
    SLO_WARNING_FACTOR,
)
from src.incident_engine import Incident
from src.models import SEVERITY_LABELS_PT, Link, Scenario, Severity, Status
from src.synthetic_data import Sample, generate_sample


class UtilizationBand(str, Enum):
    NORMAL = "Normal"
    CONGESTED = "Congestionado"
    DEGRADED = "Degradado"
    DOWN = "Indisponível"


@dataclass(frozen=True)
class LatencyData:
    """Série temporal de latência fim a fim em ms e limiares de SLO.

    points: pares (índice da amostra 1..N, latência em ms).
    warning: limiar de SLO aviso em ms (fator do baseline).
    critical: limiar de SLO crítico em ms (fator do baseline).
    """

    points: tuple[tuple[int, float], ...]
    warning: float
    critical: float


@dataclass(frozen=True)
class LinkUtilization:
    """Utilização de enlace de rede.

    label: rótulo encurtado para visualização em gráficos (ex: EDGE1 → FW).
    host: identificador completo de origem e destino (ex: RTR-EDGE-01 ↔ FW-CORE-01).
    utilization: utilização percentual da capacidade do enlace (0.0 a 100.0%).
    band: classificação operacional da utilização (Normal, Congestionado, Degradado, Indisponível).
    """

    label: str
    host: str
    utilization: float
    band: UtilizationBand


@dataclass(frozen=True)
class SeverityData:
    critical: int
    warning: int


def unavailable_link_count(links: tuple[Link, ...]) -> int:
    return sum(link.status == Status.DOWN for link in links)


def latency_data(sample: Sample) -> LatencyData:
    baseline = generate_sample(sample.seed, Scenario.NORMAL, sample.variant)
    baseline_mean = sum(baseline.latency_series) / len(baseline.latency_series)
    warning = baseline_mean * SLO_WARNING_FACTOR
    critical = baseline_mean * SLO_CRITICAL_FACTOR
    return LatencyData(
        tuple(enumerate(sample.latency_series, start=1)),
        warning,
        critical,
    )


def short_node_id(node_id: str) -> str:
    names = {
        "INTERNET": "NET",
        "RTR-EDGE-01": "EDGE1",
        "RTR-EDGE-02": "EDGE2",
        "FW-CORE-01": "FW",
        "SW-CORE-01": "CORE",
        "SW-ACCESS-01": "ACC1",
        "SW-ACCESS-02": "ACC2",
        "SRV-WEB-01": "WEB-SRV",
        "SRV-DB-01": "DB-SRV",
        "SRV-API-01": "API-SRV",
        "DATABASE": "DB",
    }
    return names.get(node_id, node_id)


def short_link_label(source: str, target: str) -> str:
    return f"{short_node_id(source)} → {short_node_id(target)}"


_short_node = short_node_id


def utilization_data(links: tuple[Link, ...], limit: int = 8) -> tuple[LinkUtilization, ...]:
    down = sorted(
        (link for link in links if link.status == Status.DOWN),
        key=lambda item: (item.source, item.target),
    )[:DOWN_LINKS_SHOWN]
    active = sorted(
        (link for link in links if link.status != Status.DOWN),
        key=lambda link: (-link.utilization, link.source, link.target),
    )
    ordered = (down + active)[:limit]
    return tuple(
        LinkUtilization(
            short_link_label(link.source, link.target),
            f"{link.source} ↔ {link.target}",
            link.utilization,
            UtilizationBand.DOWN
            if link.status == Status.DOWN
            else UtilizationBand.DEGRADED
            if link.status == Status.DEGRADED
            else UtilizationBand.CONGESTED
            if link.utilization >= CONGESTION_THRESHOLD_PCT
            else UtilizationBand.NORMAL,
        )
        for link in ordered
    )


def severity_data(incidents: tuple[Incident, ...]) -> tuple[tuple[str, int], ...]:
    critical = sum(item.severity == Severity.CRITICAL for item in incidents)
    warning = sum(item.severity == Severity.WARNING for item in incidents)
    return (
        (SEVERITY_LABELS_PT[Severity.CRITICAL], critical),
        (SEVERITY_LABELS_PT[Severity.WARNING], warning),
    )
