from dataclasses import dataclass

import networkx as nx

from src.config import THRESHOLDS
from src.models import NodeType, Status
from src.network_topology import affected_services, build_topology
from src.synthetic_data import Sample


@dataclass(frozen=True)
class RootCauseAnalysis:
    root_cause: str | None
    component_id: str | None
    evidences: tuple[str, ...]
    impact: tuple[tuple[str, str], ...]
    actions: tuple[str, ...]


def _impact(sample: Sample) -> tuple[tuple[str, str], ...]:
    labels = {Status.DOWN: "Indisponível", Status.DEGRADED: "Degradado"}
    return tuple(
        (service, labels[status])
        for service, status in affected_services(sample.nodes, sample.links).items()
        if status != Status.UP
    )


def analyze(sample: Sample) -> RootCauseAnalysis:
    graph = build_topology(sample.nodes, sample.links)
    distances = nx.single_source_shortest_path_length(graph, "INTERNET")
    down_nodes = {node.id for node in sample.nodes if node.status == Status.DOWN}
    candidates: list[tuple[int, int, str, str]] = []

    for node in sample.nodes:
        if node.type in {NodeType.INTERNET, NodeType.SERVICE}:
            continue
        if node.status == Status.DOWN:
            candidates.append((distances[node.id], 0, node.id, "down"))
        elif node.cpu is not None and node.cpu >= THRESHOLDS["cpu"][0]:
            candidates.append((distances[node.id], 1, node.id, "cpu"))
    for link in sample.links:
        if {link.source, link.target} & down_nodes:
            continue
        if link.status == Status.DOWN:
            kind = "down"
        elif (
            link.status == Status.DEGRADED
            or link.latency >= THRESHOLDS["latency"][0]
            or link.packet_loss >= THRESHOLDS["packet_loss"][0]
        ):
            kind = "degraded"
        else:
            continue
        candidates.append(
            (
                min(distances[link.source], distances[link.target]),
                2,
                f"{link.source}--{link.target}",
                kind,
            )
        )

    if not candidates:
        return RootCauseAnalysis(None, None, (), (), ())
    _, _, component_id, kind = min(candidates)
    impact = _impact(sample)
    unavailable_count = sum(status == "Indisponível" for _, status in impact)
    degraded_count = sum(status == "Degradado" for _, status in impact)
    if kind == "cpu":
        cause = f"CPU elevada em {component_id}."
        actions = (
            "Validar a carga sintética do servidor.",
            "Confirmar o estado do serviço após estabilização.",
        )
    elif kind == "degraded":
        cause = f"Link {component_id} degradado."
        actions = (
            "Validar latência, perda e utilização do enlace no laboratório.",
            "Confirmar o caminho alternativo e acompanhar os serviços.",
        )
    else:
        cause = f"{component_id} indisponível."
        actions = (
            "Validar estado e conectividade do componente no laboratório.",
            "Confirmar o caminho alternativo antes de atuar nos serviços.",
        )
    evidences = tuple(
        evidence
        for count, evidence in (
            (unavailable_count, f"{unavailable_count} serviço(s) sem conectividade."),
            (degraded_count, f"{degraded_count} serviço(s) degradado(s)."),
        )
        if count
    ) + (f"Componente {component_id} identificado por estado, métricas e posição na topologia.",)
    return RootCauseAnalysis(cause, component_id, evidences, impact, actions)
