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


def test_ecmp_impact_is_derived_for_all_scenarios() -> None:
    from src.network_topology import affected_services

    expected = {
        Scenario.NORMAL: {},
        Scenario.LINK_DEGRADED: {
            "WEB": Status.DEGRADED,
            "DATABASE": Status.DEGRADED,
            "API": Status.DEGRADED,
        },
        Scenario.LINK_DOWN: {"WEB": Status.DEGRADED},
        Scenario.CPU_HIGH: {"API": Status.DEGRADED},
        Scenario.CORE_SWITCH_DOWN: {
            "WEB": Status.DOWN,
            "DATABASE": Status.DOWN,
            "API": Status.DOWN,
        },
    }
    for scenario, impact in expected.items():
        sample = generate_sample(42, scenario)
        result = affected_services(sample.nodes, sample.links)
        assert {
            service: status for service, status in result.items() if status != Status.UP
        } == impact


def test_end_to_end_latency_rises_for_reachable_failure_scenarios() -> None:
    from src.network_topology import mean_service_latency

    normal = generate_sample(42)
    baseline = mean_service_latency(normal.nodes, normal.links)
    assert baseline is not None
    for scenario in (Scenario.LINK_DEGRADED, Scenario.LINK_DOWN, Scenario.CPU_HIGH):
        sample = generate_sample(42, scenario)
        latency = mean_service_latency(sample.nodes, sample.links)
        assert latency is not None and latency > baseline
        assert sum(sample.latency_series) / len(sample.latency_series) > sum(
            normal.latency_series
        ) / len(normal.latency_series)
    core = generate_sample(42, Scenario.CORE_SWITCH_DOWN)
    assert mean_service_latency(core.nodes, core.links) is None
    assert core.latency_series == ()


def test_service_visual_state_matches_derived_ecmp_impact() -> None:
    from src.ui.topology import topology_figure

    sample = generate_sample(42, Scenario.LINK_DEGRADED)
    figure = topology_figure(sample.nodes, sample.links)
    degraded = next(trace for trace in figure.data if trace.name == "Degradado")
    assert {"WEB", "DATABASE", "API"} <= set(degraded.text)
