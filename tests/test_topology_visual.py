from src.models import IMPACTED_LABEL, STATUS_LABELS_PT, Node, NodeType, Scenario, Status
from src.synthetic_data import generate_sample
from src.ui.topology import COLORS, MARKER_SYMBOLS, _node_tooltip, topology_figure


def _node(**overrides: object) -> Node:
    base: dict = {
        "id": "SRV-TEST-01",
        "hostname": "SRV-TEST-01",
        "type": NodeType.SERVER,
        "status": Status.UP,
        "site": "LAB-SP",
        "ip": None,
        "cpu": None,
        "memory": None,
        "latency": None,
        "packet_loss": None,
        "availability": None,
    }
    base.update(overrides)
    return Node(**base)


def test_node_tooltip_formats_missing_metrics_as_nd() -> None:
    tooltip = _node_tooltip(_node(), STATUS_LABELS_PT[Status.UP])
    assert "None" not in tooltip
    for fragment in (
        "IP: N/D",
        "CPU: N/D",
        "Memória: N/D",
        "Latência: N/D",
        "Perda: N/D",
        "Disponibilidade: N/D",
    ):
        assert fragment in tooltip


def test_node_tooltip_formats_present_metrics() -> None:
    tooltip = _node_tooltip(
        _node(
            ip="192.0.2.10",
            cpu=42.37,
            memory=55.04,
            latency=12.34,
            packet_loss=0.126,
            availability=99.96,
        ),
        STATUS_LABELS_PT[Status.UP],
    )
    assert "IP: 192.0.2.10" in tooltip
    assert "CPU: 42.4%" in tooltip
    assert "Memória: 55.0%" in tooltip
    assert "Latência: 12.3 ms" in tooltip
    assert "Perda: 0.13%" in tooltip
    assert "Disponibilidade: 100.0%" in tooltip


def test_node_tooltip_unreachable_latency_is_nd() -> None:
    assert "Latência: N/D" in _node_tooltip(_node(latency=12.34), IMPACTED_LABEL)
    down_label = STATUS_LABELS_PT[Status.DOWN]
    assert "Latência: N/D" in _node_tooltip(_node(latency=12.34), down_label)
    shown = _node_tooltip(_node(latency=12.34), STATUS_LABELS_PT[Status.DEGRADED])
    assert "Latência: 12.3 ms" in shown


def test_node_types_use_distinct_symbols_and_labels_have_background() -> None:
    sample = generate_sample(42)
    figure = topology_figure(sample.nodes, sample.links)
    symbols = {
        symbol
        for trace in figure.data
        if trace.mode == "markers"
        for symbol in (
            trace.marker.symbol
            if isinstance(trace.marker.symbol, (list, tuple))
            else [trace.marker.symbol]
        )
    }
    assert symbols == set(MARKER_SYMBOLS.values())
    assert len(figure.layout.annotations) == len(sample.nodes)
    assert all(annotation.bgcolor for annotation in figure.layout.annotations)
    assert len(MARKER_SYMBOLS) == len(NodeType)


def test_root_halo_keeps_state_color_and_unreachable_tooltips() -> None:
    sample = generate_sample(42, Scenario.CORE_SWITCH_DOWN)
    figure = topology_figure(sample.nodes, sample.links, "node", ("SW-CORE-01",))
    assert any(trace.name == "Causa raiz" for trace in figure.data)
    down = next(trace for trace in figure.data if trace.name == "Indisponível")
    assert down.marker.color == COLORS["Indisponível"]
    impacted = next(trace for trace in figure.data if trace.name == "Impactado")
    assert any("Latência: N/D" in tooltip for tooltip in impacted.hovertext)
    cross_link = next(
        trace
        for trace in figure.data
        if isinstance(trace.text, str) and "SW-ACCESS-01 ↔ SW-ACCESS-02" in trace.text
    )
    assert "Estado: Impactado" in cross_link.text
    assert next(node.status for node in sample.nodes if node.id == "SW-CORE-01") == Status.DOWN


def test_link_component_halo_without_string_parsing() -> None:
    sample = generate_sample(42, Scenario.LINK_DOWN)
    figure = topology_figure(sample.nodes, sample.links, "link", ("SW-CORE-01", "SW-ACCESS-01"))
    assert any(trace.name == "Causa raiz" for trace in figure.data)
    without_kind = topology_figure(sample.nodes, sample.links, None, ("SW-CORE-01",))
    assert not any(trace.name == "Causa raiz" for trace in without_kind.data)
