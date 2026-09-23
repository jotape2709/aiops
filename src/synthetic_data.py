from dataclasses import dataclass, replace

import numpy as np

from src.config import DEFAULT_SEED
from src.models import Link, Node, NodeType, Scenario, Status
from src.network_topology import EDGES, NODE_TYPES, unreachable_from_internet


@dataclass(frozen=True)
class Sample:
    scenario: Scenario
    seed: int
    variant: int
    nodes: tuple[Node, ...]
    links: tuple[Link, ...]
    latency_series: tuple[float, ...]


def generate_sample(
    seed: int = DEFAULT_SEED, scenario: Scenario = Scenario.NORMAL, variant: int = 0
) -> Sample:
    rng = np.random.default_rng([seed, variant])
    nodes = tuple(
        Node(
            id=node_id,
            hostname=node_id,
            type=node_type,
            status=Status.UP,
            site="LAB-SP",
            ip=None if node_type == NodeType.INTERNET else f"192.0.2.{index + 10}",
            cpu=None if node_type == NodeType.INTERNET else round(float(rng.uniform(18, 48)), 1),
            memory=None if node_type == NodeType.INTERNET else round(float(rng.uniform(28, 58)), 1),
            latency=None if node_type == NodeType.INTERNET else round(float(rng.uniform(8, 28)), 1),
            packet_loss=None
            if node_type == NodeType.INTERNET
            else round(float(rng.uniform(0, 0.8)), 2),
            availability=None if node_type == NodeType.INTERNET else 100.0,
        )
        for index, (node_id, node_type) in enumerate(NODE_TYPES.items())
    )
    links = tuple(
        Link(
            source=source,
            target=target,
            status=Status.UP,
            utilization=round(float(rng.uniform(12, 55)), 1),
            latency=round(float(rng.uniform(2, 16)), 1),
            capacity_mbps=1000,
        )
        for source, target in EDGES
    )

    if scenario == Scenario.CORE_SWITCH_DOWN:
        nodes = tuple(
            replace(node, status=Status.DOWN, availability=0.0) if node.id == "SW-CORE-01" else node
            for node in nodes
        )
        links = tuple(
            replace(link, status=Status.DOWN, utilization=0.0)
            if "SW-CORE-01" in (link.source, link.target)
            else link
            for link in links
        )
        unreachable, _ = unreachable_from_internet(nodes, links)
        nodes = tuple(
            replace(
                node,
                latency=round(node.latency + 45, 1) if node.latency is not None else None,
                availability=0.0 if node.id in unreachable else node.availability,
            )
            if node.id in unreachable or node.id == "FW-CORE-01"
            else node
            for node in nodes
        )

    unreachable, _ = unreachable_from_internet(nodes, links)
    reachable_latencies = [
        node.latency
        for node in nodes
        if node.type != NodeType.INTERNET
        and node.id not in unreachable
        and node.latency is not None
    ]
    base_latency = float(np.mean(reachable_latencies))
    latency_series = tuple(
        round(max(0.0, base_latency + float(noise)), 1) for noise in rng.normal(0, 1.2, 60)
    )
    return Sample(scenario, seed, variant, nodes, links, latency_series)
