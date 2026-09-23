from dataclasses import dataclass
from itertools import pairwise

import networkx as nx

from src.models import IMPACTED_LABEL, STATUS_LABELS_PT, Link, Node, NodeType, Status

POSITIONS: dict[str, tuple[float, float]] = {
    "INTERNET": (0.0, 6.0),
    "RTR-EDGE-01": (-1.1, 5.0),
    "RTR-EDGE-02": (1.1, 5.0),
    "FW-CORE-01": (0.0, 4.0),
    "SW-CORE-01": (0.0, 3.0),
    "SW-ACCESS-01": (-2.0, 2.0),
    "SW-ACCESS-02": (2.0, 2.0),
    "SRV-WEB-01": (-2.0, 1.0),
    "SRV-DB-01": (0.0, 1.0),
    "SRV-API-01": (2.0, 1.0),
    "WEB": (-2.0, 0.0),
    "DATABASE": (0.0, 0.0),
    "API": (2.0, 0.0),
}

NODE_TYPES: dict[str, NodeType] = {
    "INTERNET": NodeType.INTERNET,
    "RTR-EDGE-01": NodeType.ROUTER,
    "RTR-EDGE-02": NodeType.ROUTER,
    "FW-CORE-01": NodeType.FIREWALL,
    "SW-CORE-01": NodeType.CORE_SWITCH,
    "SW-ACCESS-01": NodeType.ACCESS_SWITCH,
    "SW-ACCESS-02": NodeType.ACCESS_SWITCH,
    "SRV-WEB-01": NodeType.SERVER,
    "SRV-DB-01": NodeType.SERVER,
    "SRV-API-01": NodeType.SERVER,
    "WEB": NodeType.SERVICE,
    "DATABASE": NodeType.SERVICE,
    "API": NodeType.SERVICE,
}

EDGES: tuple[tuple[str, str], ...] = (
    ("INTERNET", "RTR-EDGE-01"),
    ("INTERNET", "RTR-EDGE-02"),
    ("RTR-EDGE-01", "FW-CORE-01"),
    ("RTR-EDGE-02", "FW-CORE-01"),
    ("FW-CORE-01", "SW-CORE-01"),
    ("SW-CORE-01", "SW-ACCESS-01"),
    ("SW-CORE-01", "SW-ACCESS-02"),
    ("SW-CORE-01", "SRV-DB-01"),
    ("SW-ACCESS-01", "SW-ACCESS-02"),
    ("SW-ACCESS-01", "SRV-WEB-01"),
    ("SW-ACCESS-02", "SRV-API-01"),
    ("SRV-WEB-01", "WEB"),
    ("SRV-DB-01", "DATABASE"),
    ("SRV-API-01", "API"),
)


def build_topology(nodes: tuple[Node, ...], links: tuple[Link, ...]) -> nx.Graph:
    graph = nx.Graph()
    for node in nodes:
        graph.add_node(node.id, model=node, pos=POSITIONS[node.id])
    for link in links:
        graph.add_edge(link.source, link.target, model=link)
    return graph


def _active_graph(nodes: tuple[Node, ...], links: tuple[Link, ...]) -> nx.Graph:
    active = nx.Graph()
    active.add_nodes_from(
        (node.id, {"model": node}) for node in nodes if node.status != Status.DOWN
    )
    active.add_edges_from(
        (link.source, link.target, {"model": link})
        for link in links
        if link.status != Status.DOWN and link.source in active and link.target in active
    )
    return active


def affected_services(nodes: tuple[Node, ...], links: tuple[Link, ...]) -> dict[str, Status]:
    """Classifica serviços pelos caminhos ECMP ativos e pelo aumento de saltos."""
    active = _active_graph(nodes, links)
    baseline = build_topology(nodes, links)
    node_by_id = {node.id: node for node in nodes}
    result: dict[str, Status] = {}
    for node in nodes:
        if node.type != NodeType.SERVICE:
            continue
        if (
            "INTERNET" not in active
            or node.id not in active
            or not nx.has_path(active, "INTERNET", node.id)
        ):
            result[node.id] = Status.DOWN
            continue
        paths = tuple(nx.all_shortest_paths(active, "INTERNET", node.id))
        rerouted = len(paths[0]) > nx.shortest_path_length(baseline, "INTERNET", node.id) + 1
        degraded_path = any(
            any(node_by_id[part].status == Status.DEGRADED for part in path)
            or any(
                active.edges[first, second]["model"].status == Status.DEGRADED
                for first, second in pairwise(path)
            )
            for path in paths
        )
        result[node.id] = Status.DEGRADED if rerouted or degraded_path else Status.UP
    return result


def mean_service_latency(nodes: tuple[Node, ...], links: tuple[Link, ...]) -> float | None:
    """Média fim a fim por serviço; cada caminho ECMP recebe o mesmo peso."""
    active = _active_graph(nodes, links)
    latencies: list[float] = []
    for node in nodes:
        if node.type != NodeType.SERVICE or "INTERNET" not in active or node.id not in active:
            continue
        if not nx.has_path(active, "INTERNET", node.id):
            continue
        path_latencies = []
        for path in nx.all_shortest_paths(active, "INTERNET", node.id):
            server = next(
                part
                for part in reversed(path[:-1])
                if active.nodes[part]["model"].type == NodeType.SERVER
            )
            server_latency = active.nodes[server]["model"].latency or 0.0
            link_latency = sum(
                active.edges[first, second]["model"].latency
                + (20.0 if active.edges[first, second]["model"].utilization >= 80 else 0.0)
                for first, second in pairwise(path)
            )
            path_latencies.append(link_latency + server_latency)
        latencies.append(sum(path_latencies) / len(path_latencies))
    return sum(latencies) / len(latencies) if latencies else None


def unreachable_from_internet(
    nodes: tuple[Node, ...], links: tuple[Link, ...]
) -> tuple[set[str], set[str]]:
    active = _active_graph(nodes, links)
    reachable = nx.node_connected_component(active, "INTERNET") if "INTERNET" in active else set()
    unreachable = {node.id for node in nodes} - reachable
    services = {
        node.id for node in nodes if node.type == NodeType.SERVICE and node.id in unreachable
    }
    return unreachable, services


@dataclass(frozen=True)
class TopologyView:
    node_states: dict[str, str]
    link_states: dict[tuple[str, str], str]


def topology_view(nodes: tuple[Node, ...], links: tuple[Link, ...]) -> TopologyView:
    """Calcula os estados operacionais e visuais de nós e enlaces para apresentação na UI."""
    unreachable, _ = unreachable_from_internet(nodes, links)
    service_status = affected_services(nodes, links)

    node_states: dict[str, str] = {}
    for node in nodes:
        if node.type == NodeType.SERVICE:
            node_states[node.id] = STATUS_LABELS_PT[service_status[node.id]]
        elif node.id in unreachable and node.status != Status.DOWN:
            node_states[node.id] = IMPACTED_LABEL
        else:
            node_states[node.id] = STATUS_LABELS_PT[node.status]

    link_states: dict[tuple[str, str], str] = {}
    for link in links:
        if link.status != Status.DOWN and {link.source, link.target} <= unreachable:
            link_states[(link.source, link.target)] = IMPACTED_LABEL
        else:
            link_states[(link.source, link.target)] = STATUS_LABELS_PT[link.status]

    return TopologyView(node_states, link_states)
