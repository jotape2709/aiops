import networkx as nx

from src.models import Link, Node, NodeType, Status

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


def unreachable_from_internet(
    nodes: tuple[Node, ...], links: tuple[Link, ...]
) -> tuple[set[str], set[str]]:
    active = nx.Graph()
    active.add_nodes_from(node.id for node in nodes if node.status != Status.DOWN)
    active.add_edges_from(
        (link.source, link.target)
        for link in links
        if link.status != Status.DOWN and link.source in active and link.target in active
    )
    reachable = nx.node_connected_component(active, "INTERNET") if "INTERNET" in active else set()
    unreachable = {node.id for node in nodes} - reachable
    services = {
        node.id for node in nodes if node.type == NodeType.SERVICE and node.id in unreachable
    }
    return unreachable, services
