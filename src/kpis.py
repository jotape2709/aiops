from dataclasses import dataclass

from src.incident_engine import correlate, generate_alerts
from src.models import NodeType, Severity, Status
from src.network_topology import affected_services, unreachable_from_internet
from src.synthetic_data import Sample


@dataclass(frozen=True)
class Kpis:
    """Indicadores-chave de desempenho (KPIs) da operação de rede NOC.

    availability: percentual (0.0 a 100.0%) de nós monitorados alcançáveis a partir da INTERNET;
        nós com estado DEGRADED contam como disponíveis (apenas nós inalcançáveis/DOWN reduzem a disponibilidade).
    active_alerts: quantidade total de alertas gerados pelas regras de limiares.
    critical_incidents: quantidade de incidentes correlacionados de severidade crítica.
    impacted_services: quantidade de serviços de negócio com estado diferente de UP (Degradado ou Indisponível).
    mean_latency: latência média fim a fim em ms calculada sobre os serviços alcançáveis,
        ou None caso nenhum serviço de negócio esteja alcançável a partir da INTERNET.
    """

    availability: float
    active_alerts: int
    critical_incidents: int
    impacted_services: int
    mean_latency: float | None


def compute_kpis(sample: Sample) -> Kpis:
    """Calcula os KPIs operacionais a partir da amostra sintética de nós, enlaces e métricas."""
    unreachable, _ = unreachable_from_internet(sample.nodes, sample.links)
    monitored = [node for node in sample.nodes if node.type != NodeType.INTERNET]
    reachable_count = sum(node.id not in unreachable for node in monitored)
    alerts = generate_alerts(sample.nodes, sample.links, sample.cpu_series)
    incidents = correlate(alerts, sample)
    services = affected_services(sample.nodes, sample.links)
    return Kpis(
        availability=100.0 * reachable_count / len(monitored),
        active_alerts=len(alerts),
        critical_incidents=sum(incident.severity == Severity.CRITICAL for incident in incidents),
        impacted_services=sum(status != Status.UP for status in services.values()),
        mean_latency=sum(sample.latency_series) / len(sample.latency_series)
        if sample.latency_series
        else None,
    )
