import plotly.graph_objects as go

from src.models import Link, Node, NodeType, Status
from src.network_topology import POSITIONS, unreachable_from_internet

COLORS = {
    "Operacional": "#33d6a6",
    "Degradado": "#f3ad4e",
    "Impactado": "#ff9b50",
    "Indisponível": "#ef5f70",
}
STATUS_LABELS = {
    Status.UP: "Operacional",
    Status.DEGRADED: "Degradado",
    Status.DOWN: "Indisponível",
}
TYPE_LABELS = {
    NodeType.INTERNET: "Internet",
    NodeType.ROUTER: "Roteador",
    NodeType.FIREWALL: "Firewall",
    NodeType.CORE_SWITCH: "Core switch",
    NodeType.ACCESS_SWITCH: "Switch de acesso",
    NodeType.SERVER: "Servidor",
    NodeType.SERVICE: "Serviço",
}


def _node_tooltip(node: Node, visual_status: str) -> str:
    lines = [node.id, f"Tipo: {TYPE_LABELS[node.type]}", f"Estado: {visual_status}"]
    if node.type != NodeType.INTERNET:
        lines.extend(
            (
                f"IP: {node.ip}",
                f"CPU: {node.cpu:.1f}%",
                f"Memória: {node.memory:.1f}%",
                f"Latência: {node.latency:.1f} ms",
                f"Perda: {node.packet_loss:.2f}%",
                f"Disponibilidade: {node.availability:.1f}%",
            )
        )
    return "<br>".join(lines)


def topology_figure(nodes: tuple[Node, ...], links: tuple[Link, ...]) -> go.Figure:
    unreachable, _ = unreachable_from_internet(nodes, links)
    figure = go.Figure()
    for link in links:
        x0, y0 = POSITIONS[link.source]
        x1, y1 = POSITIONS[link.target]
        label = STATUS_LABELS[link.status]
        figure.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line={
                    "color": COLORS[label],
                    "width": 2.5,
                    "dash": "dash" if link.status == Status.DOWN else "solid",
                },
                text=(
                    f"{link.source} ↔ {link.target}<br>Estado: {label}<br>"
                    f"Utilização: {link.utilization:.1f}%<br>Latência: {link.latency:.1f} ms"
                ),
                hoverinfo="text",
                showlegend=False,
            )
        )
    for label, color in COLORS.items():
        selected = [
            node
            for node in nodes
            if (
                "Impactado"
                if node.id in unreachable and node.status != Status.DOWN
                else STATUS_LABELS[node.status]
            )
            == label
        ]
        if not selected:
            continue
        figure.add_trace(
            go.Scatter(
                x=[POSITIONS[node.id][0] for node in selected],
                y=[POSITIONS[node.id][1] for node in selected],
                mode="markers+text",
                text=[node.id for node in selected],
                textposition="top center",
                textfont={"color": "#eaf4ff", "size": 10},
                marker={
                    "size": 17,
                    "color": color,
                    "line": {"color": "#0b1020", "width": 2},
                },
                hovertext=[_node_tooltip(node, label) for node in selected],
                hovertemplate="%{hovertext}<extra></extra>",
                name=label,
            )
        )
    figure.update_layout(
        height=530,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        paper_bgcolor="#111a2d",
        plot_bgcolor="#111a2d",
        font={"color": "#eaf4ff"},
        xaxis={"visible": False, "range": [-2.7, 2.7]},
        yaxis={"visible": False, "range": [-0.5, 6.5], "scaleanchor": "x", "scaleratio": 1},
        legend={"orientation": "h", "y": -0.02, "font": {"color": "#eaf4ff"}},
    )
    return figure
