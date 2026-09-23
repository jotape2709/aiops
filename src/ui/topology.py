from typing import Literal

import plotly.graph_objects as go

from src.models import IMPACTED_LABEL, STATUS_LABELS_PT, Link, Node, NodeType, Status
from src.network_topology import POSITIONS, topology_view

COLORS = {
    STATUS_LABELS_PT[Status.UP]: "#33d6a6",
    STATUS_LABELS_PT[Status.DEGRADED]: "#f3ad4e",
    IMPACTED_LABEL: "#ff9b50",
    STATUS_LABELS_PT[Status.DOWN]: "#ef5f70",
}
_NO_LATENCY_LABELS = {IMPACTED_LABEL, STATUS_LABELS_PT[Status.DOWN]}
TYPE_LABELS = {
    NodeType.INTERNET: "Internet",
    NodeType.ROUTER: "Roteador",
    NodeType.FIREWALL: "Firewall",
    NodeType.CORE_SWITCH: "Core switch",
    NodeType.ACCESS_SWITCH: "Switch de acesso",
    NodeType.SERVER: "Servidor",
    NodeType.SERVICE: "Serviço",
}
MARKER_SYMBOLS = {
    NodeType.INTERNET: "circle-open",
    NodeType.ROUTER: "diamond",
    NodeType.FIREWALL: "hexagon",
    NodeType.CORE_SWITCH: "square",
    NodeType.ACCESS_SWITCH: "square-open",
    NodeType.SERVER: "triangle-up",
    NodeType.SERVICE: "circle",
}


def format_metric(value: float | None, spec: str, unit: str = "") -> str:
    """Formata uma métrica opcional; valores ausentes viram N/D."""
    return "N/D" if value is None else f"{value:{spec}}{unit}"


def _node_tooltip(node: Node, visual_status: str) -> str:
    lines = [node.id, f"Tipo: {TYPE_LABELS[node.type]}", f"Estado: {visual_status}"]
    if node.type != NodeType.INTERNET:
        latency = None if visual_status in _NO_LATENCY_LABELS else node.latency
        lines.extend(
            (
                f"IP: {node.ip if node.ip else 'N/D'}",
                f"CPU: {format_metric(node.cpu, '.1f', '%')}",
                f"Memória: {format_metric(node.memory, '.1f', '%')}",
                f"Latência: {format_metric(latency, '.1f', ' ms')}",
                f"Perda: {format_metric(node.packet_loss, '.2f', '%')}",
                f"Disponibilidade: {format_metric(node.availability, '.1f', '%')}",
            )
        )
    return "<br>".join(lines)


def topology_figure(
    nodes: tuple[Node, ...],
    links: tuple[Link, ...],
    component_kind: Literal["node", "link"] | None = None,
    component_nodes: tuple[str, ...] = (),
) -> go.Figure:
    view = topology_view(nodes, links)
    figure = go.Figure()
    root_seen = False
    for link in links:
        x0, y0 = POSITIONS[link.source]
        x1, y1 = POSITIONS[link.target]
        label = view.link_states[(link.source, link.target)]
        is_root = component_kind == "link" and {link.source, link.target} == set(component_nodes)
        if is_root:
            root_seen = True
            figure.add_trace(
                go.Scatter(
                    x=[x0, x1],
                    y=[y0, y1],
                    mode="lines",
                    line={"color": "#c38bff", "width": 9},
                    opacity=0.7,
                    hoverinfo="skip",
                    name="Causa raiz",
                    showlegend=False,
                )
            )
        figure.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line={
                    "color": COLORS[label],
                    "width": 3 if is_root else 2.5,
                    "dash": "dash" if link.status == Status.DOWN else "solid",
                },
                text=(
                    f"{link.source} ↔ {link.target}<br>Estado: {label}<br>"
                    f"Utilização: {link.utilization:.1f}%<br>Latência: {link.latency:.1f} ms"
                    f"<br>Perda: {link.packet_loss:.1f}%"
                ),
                hoverinfo="text",
                showlegend=False,
            )
        )
    root_node = (
        next((node for node in nodes if node.id == component_nodes[0]), None)
        if component_kind == "node" and component_nodes
        else None
    )
    if root_node is not None:
        root_seen = True
        x, y = POSITIONS[root_node.id]
        figure.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers",
                marker={
                    "size": 30,
                    "color": "rgba(0,0,0,0)",
                    "line": {"color": "#c38bff", "width": 3},
                },
                hoverinfo="skip",
                name="Causa raiz",
                showlegend=False,
            )
        )
    for label, color in COLORS.items():
        selected = [node for node in nodes if view.node_states[node.id] == label]
        if not selected:
            continue
        figure.add_trace(
            go.Scatter(
                x=[POSITIONS[node.id][0] for node in selected],
                y=[POSITIONS[node.id][1] for node in selected],
                mode="markers",
                marker={
                    "size": 18,
                    "symbol": [MARKER_SYMBOLS[node.type] for node in selected],
                    "color": color,
                    "line": {"color": "#0b1020", "width": 2},
                },
                hovertext=[_node_tooltip(node, label) for node in selected],
                hovertemplate="%{hovertext}<extra></extra>",
                name=label,
                showlegend=False,
            )
        )
    if root_seen:
        figure.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={
                    "symbol": "circle-open",
                    "size": 12,
                    "color": "#c38bff",
                    "line": {"width": 2},
                },
                name="Causa raiz",
                hoverinfo="skip",
            )
        )
    for label, color in COLORS.items():
        figure.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={"symbol": "circle", "size": 10, "color": color},
                name=label,
                hoverinfo="skip",
            )
        )
    for node in nodes:
        x, y = POSITIONS[node.id]
        figure.add_annotation(
            x=x,
            y=y,
            yshift=20,
            text=node.id,
            showarrow=False,
            font={"color": "#eaf4ff", "size": 10},
            bgcolor="rgba(17,26,45,0.93)",
            bordercolor="#2b3852",
            borderpad=2,
        )
    figure.update_layout(
        height=460,
        margin={"l": 15, "r": 15, "t": 30, "b": 15},
        paper_bgcolor="#111a2d",
        plot_bgcolor="#111a2d",
        font={"color": "#eaf4ff"},
        xaxis={"visible": False, "range": [-3.0, 3.0]},
        yaxis={"visible": False, "range": [-0.5, 6.7]},
        legend={"orientation": "h", "y": -0.02, "font": {"color": "#eaf4ff", "size": 10}},
    )
    return figure
