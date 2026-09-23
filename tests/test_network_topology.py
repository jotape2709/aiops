from src.models import Scenario, Status
from src.network_topology import POSITIONS, build_topology, unreachable_from_internet
from src.synthetic_data import generate_sample


def test_normal_all_services_reachable() -> None:
    sample = generate_sample(42)
    unreachable, services = unreachable_from_internet(sample.nodes, sample.links)
    assert not unreachable
    assert not services
    assert len(build_topology(sample.nodes, sample.links)) == len(POSITIONS)


def test_core_down_impacts_multiple_services() -> None:
    sample = generate_sample(42, Scenario.CORE_SWITCH_DOWN)
    unreachable, services = unreachable_from_internet(sample.nodes, sample.links)
    assert len(services) >= 2
    assert "SW-CORE-01" in unreachable
    assert all(
        link.status == Status.DOWN
        for link in sample.links
        if "SW-CORE-01" in (link.source, link.target)
    )
