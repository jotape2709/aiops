from dataclasses import dataclass, field, replace

import numpy as np

from src.config import DEFAULT_SEED
from src.models import Link, Node, NodeType, Scenario, Status
from src.network_topology import EDGES, NODE_TYPES, mean_service_latency


@dataclass(frozen=True)
class Sample:
    scenario: Scenario
    seed: int
    variant: int
    nodes: tuple[Node, ...]
    links: tuple[Link, ...]
    latency_series: tuple[float, ...]
    cpu_series: dict[str, tuple[float, ...]] = field(default_factory=dict)


def _same_link(link: Link, first: str, second: str) -> bool:
    return {link.source, link.target} == {first, second}


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
    elif scenario == Scenario.LINK_DEGRADED:
        links = tuple(
            replace(link, status=Status.DEGRADED, latency=90.0, packet_loss=5.0)
            if _same_link(link, "RTR-EDGE-01", "FW-CORE-01")
            else replace(link, utilization=82.0)
            if _same_link(link, "RTR-EDGE-02", "FW-CORE-01")
            else link
            for link in links
        )
    elif scenario == Scenario.LINK_DOWN:
        links = tuple(
            replace(link, status=Status.DOWN, utilization=0.0)
            if _same_link(link, "SW-CORE-01", "SW-ACCESS-01")
            else replace(link, utilization=91.0)
            if _same_link(link, "SW-ACCESS-01", "SW-ACCESS-02")
            else link
            for link in links
        )
    elif scenario == Scenario.CPU_HIGH:
        cpu_penalty = float(np.random.default_rng([seed, variant, 1]).uniform(30, 60))
        nodes = tuple(
            replace(
                node,
                cpu=92.0,
                status=Status.DEGRADED,
                latency=round((node.latency or 0.0) + cpu_penalty, 1),
            )
            if node.id == "SRV-API-01"
            else node
            for node in nodes
        )

    # Sem serviços alcançáveis, não há observação de latência fim a fim.
    base_latency = mean_service_latency(nodes, links)
    latency_rng = np.random.default_rng([seed, variant, 2])
    latency_series = (
        tuple(
            round(max(0.0, base_latency + float(noise)), 1)
            for noise in latency_rng.normal(0, 1.2, 60)
        )
        if base_latency is not None
        else ()
    )
    cpu_rng = np.random.default_rng([seed, variant, 3])
    cpu_series = {
        node.id: tuple(
            round(float(value), 1)
            for value in (
                cpu_rng.uniform(91, 94, 12)
                if scenario == Scenario.CPU_HIGH and node.id == "SRV-API-01"
                else cpu_rng.uniform(max(0.0, (node.cpu or 0.0) - 2), (node.cpu or 0.0) + 2, 12)
            )
        )
        for node in nodes
        if node.type not in {NodeType.INTERNET, NodeType.SERVICE}
    }
    return Sample(scenario, seed, variant, nodes, links, latency_series, cpu_series)
