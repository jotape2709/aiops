from src.models import Scenario
from src.root_cause import analyze
from src.synthetic_data import generate_sample


def test_normal_has_no_root_cause() -> None:
    analysis = analyze(generate_sample(42))
    assert analysis.root_cause is None
    assert analysis.component_id is None


def test_each_incident_identifies_component_and_safe_actions() -> None:
    expected = {
        Scenario.LINK_DEGRADED: "RTR-EDGE-01--FW-CORE-01",
        Scenario.LINK_DOWN: "SW-CORE-01--SW-ACCESS-01",
        Scenario.CORE_SWITCH_DOWN: "SW-CORE-01",
        Scenario.CPU_HIGH: "SRV-API-01",
    }
    forbidden = ("reload", "erase", "delete", "format", "shutdown")
    for scenario, component in expected.items():
        analysis = analyze(generate_sample(42, scenario))
        assert analysis.component_id == component
        assert analysis.root_cause
        assert analysis.evidences and analysis.actions
        assert not any(word in action.lower() for action in analysis.actions for word in forbidden)
    assert dict(analyze(generate_sample(42, Scenario.LINK_DOWN)).impact)["WEB"] == "Degradado"


def test_root_cause_impact_and_evidence_match_topology() -> None:
    expected = {
        Scenario.LINK_DEGRADED: {"WEB": "Degradado", "DATABASE": "Degradado", "API": "Degradado"},
        Scenario.LINK_DOWN: {"WEB": "Degradado"},
        Scenario.CPU_HIGH: {"API": "Degradado"},
        Scenario.CORE_SWITCH_DOWN: {
            "WEB": "Indisponível",
            "DATABASE": "Indisponível",
            "API": "Indisponível",
        },
    }
    for scenario, impact in expected.items():
        analysis = analyze(generate_sample(42, scenario))
        assert dict(analysis.impact) == impact
        assert all(not evidence.startswith("0 serviço") for evidence in analysis.evidences)


def test_cpu_root_cause_uses_warning_threshold() -> None:
    from dataclasses import replace

    from src.config import THRESHOLDS

    base = generate_sample(42)
    node_id = "SRV-API-01"
    nodes = tuple(
        replace(node, cpu=THRESHOLDS["cpu"][0]) if node.id == node_id else node
        for node in base.nodes
    )
    analysis = analyze(replace(base, nodes=nodes))
    assert analysis.component_id == node_id
