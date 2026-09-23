from src.models import NodeType, Scenario, Status
from src.synthetic_data import generate_sample


def test_same_seed_variant_and_scenario_reproduce_sample() -> None:
    assert generate_sample(42, Scenario.NORMAL, 0) == generate_sample(42, Scenario.NORMAL, 0)
    assert generate_sample(42, Scenario.CORE_SWITCH_DOWN, 1) == generate_sample(
        42, Scenario.CORE_SWITCH_DOWN, 1
    )
    assert generate_sample(42, variant=0) != generate_sample(42, variant=1)
    assert generate_sample(42) != generate_sample(43)


def test_normal_has_no_down_elements() -> None:
    sample = generate_sample(42)
    assert all(node.status == Status.UP for node in sample.nodes)
    assert all(link.status == Status.UP for link in sample.links)
    assert len(sample.latency_series) == 60
    internet = next(node for node in sample.nodes if node.type == NodeType.INTERNET)
    assert internet.ip is None and internet.cpu is None and internet.memory is None
