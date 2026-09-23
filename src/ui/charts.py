import plotly.graph_objects as go

from src.chart_data import LatencyData, LinkUtilization, UtilizationBand
from src.config import CONGESTION_THRESHOLD_PCT
from src.models import SEVERITY_LABELS_PT, Severity

FONT = "#eaf4ff"
GRID = "#34425c"
TRANSPARENT = "rgba(0,0,0,0)"

SEVERITY_COLORS = {
    SEVERITY_LABELS_PT[Severity.CRITICAL]: "#ef5f70",
    SEVERITY_LABELS_PT[Severity.WARNING]: "#f3ad4e",
}
BAND_COLORS: dict[UtilizationBand, str] = {
    UtilizationBand.NORMAL: "#33d6a6",
    UtilizationBand.CONGESTED: "#f3ad4e",
    UtilizationBand.DEGRADED: "#f3ad4e",
    UtilizationBand.DOWN: "#ef5f70",
}


def _style(figure: go.Figure, *, left: int = 42) -> go.Figure:
    figure.update_layout(
        height=280,
        margin={"l": left, "r": 12, "t": 18, "b": 36},
        paper_bgcolor=TRANSPARENT,
        plot_bgcolor=TRANSPARENT,
        font={"color": FONT, "size": 11},
        showlegend=False,
        hoverlabel={"bgcolor": "#172239", "font_color": FONT},
    )
    figure.update_xaxes(gridcolor=GRID, zeroline=False)
    figure.update_yaxes(gridcolor=GRID, zeroline=False)
    return figure


def latency_figure(data: LatencyData) -> go.Figure:
    figure = go.Figure()
    if data.points:
        figure.add_trace(
            go.Scatter(
                x=[point for point, _ in data.points],
                y=[value for _, value in data.points],
                mode="lines",
                line={"color": "#63d9f4", "width": 2.5},
                fill="tozeroy",
                fillcolor="rgba(99,217,244,0.08)",
                hovertemplate="Ponto %{x}<br>%{y:.1f} ms<extra></extra>",
            )
        )
        for value, label, color in (
            (data.warning, "SLO aviso", "#f3ad4e"),
            (data.critical, "SLO crítico", "#ef5f70"),
        ):
            figure.add_hline(
                y=value,
                line={"color": color, "width": 1.5, "dash": "dot"},
                annotation_text=f"{label} {value:.0f}",
                annotation_position="top right",
                annotation_font={"color": color, "size": 10},
            )
        figure.update_yaxes(
            title_text="ms",
            range=[
                0,
                max(data.critical + 18, 1.1 * max((value for _, value in data.points), default=0)),
            ],
        )
    else:
        figure.add_annotation(
            text="Sem serviços alcançáveis",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"color": "#dbe6f8", "size": 13},
            bgcolor="rgba(23,34,57,0.92)",
            bordercolor="#2b3852",
            borderpad=8,
        )
        figure.update_xaxes(showgrid=False, showticklabels=False, zeroline=False)
        figure.update_yaxes(
            title_text="ms", range=[0, 1], showgrid=False, showticklabels=False, zeroline=False
        )
    figure.update_xaxes(title_text="Amostras", range=[1, max(60, len(data.points))])
    return _style(figure)


def utilization_figure(data: tuple[LinkUtilization, ...]) -> go.Figure:
    down_label = UtilizationBand.DOWN.value
    unavailable = tuple(item for item in data if item.band is UtilizationBand.DOWN)
    available = tuple(item for item in data if item.band is not UtilizationBand.DOWN)
    figure = go.Figure()
    if not data:
        figure.add_annotation(
            text="Nenhum link monitorado",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"color": "#dbe6f8", "size": 13},
            bgcolor="rgba(23,34,57,0.92)",
            bordercolor="#2b3852",
            borderpad=8,
        )
        figure.update_xaxes(showgrid=False, showticklabels=False, zeroline=False, range=[0, 1])
        figure.update_yaxes(showgrid=False, showticklabels=False, zeroline=False, range=[0, 1])
        return _style(figure, left=102)
    if unavailable:
        figure.add_trace(
            go.Bar(
                x=[100] * len(unavailable),
                y=[item.label for item in unavailable],
                orientation="h",
                marker={
                    "color": "rgba(239,95,112,0.06)",
                    "line": {"color": "#ef5f70", "width": 1},
                },
                text=[down_label] * len(unavailable),
                textposition="inside",
                textfont={"color": "#ef5f70", "size": 10},
                customdata=[[item.host] for item in unavailable],
                hovertemplate=f"%{{customdata[0]}}<br>{down_label}<extra></extra>",
                showlegend=False,
            )
        )
    if available:
        figure.add_trace(
            go.Bar(
                x=[item.utilization for item in available],
                y=[item.label for item in available],
                orientation="h",
                marker_color=[BAND_COLORS[item.band] for item in available],
                customdata=[[item.host, item.band.value, item.utilization] for item in available],
                hovertemplate="%{customdata[0]}<br>%{customdata[2]:.1f}% · %{customdata[1]}<extra></extra>",
                showlegend=False,
            )
        )
    figure.add_vline(
        x=CONGESTION_THRESHOLD_PCT,
        line={"color": "#f3ad4e", "width": 1.5, "dash": "dot"},
        annotation_text=f"Congestionamento {CONGESTION_THRESHOLD_PCT:.0f}%",
        annotation_position="top right",
        annotation_font={"color": "#f3ad4e", "size": 10},
    )
    figure.update_xaxes(title_text="Utilização (%)", range=[0, 105])
    figure.update_yaxes(autorange="reversed", tickfont={"size": 10}, showgrid=False)
    return _style(figure, left=102)


def severity_figure(data: tuple[tuple[str, int], ...]) -> go.Figure:
    labels = tuple(label for label, _ in data)
    counts = tuple(count for _, count in data)
    figure = go.Figure(
        go.Bar(
            x=list(labels),
            y=list(counts),
            marker_color=[SEVERITY_COLORS.get(label, "#8292aa") for label in labels],
            text=list(counts),
            textposition="outside",
            hovertemplate="%{x}: %{y}<extra></extra>",
        )
    )
    if not any(counts):
        figure.add_annotation(
            text="Nenhum incidente ativo",
            x=0.5,
            y=0.55,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"color": "#b6c5dd"},
        )
    figure.update_yaxes(title_text="Incidentes", range=[0, max((2, *counts)) + 0.5], dtick=1)
    figure.update_xaxes(showgrid=False)
    return _style(figure)
