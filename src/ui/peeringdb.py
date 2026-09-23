import time
from math import ceil

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import PEERINGDB_CACHE_TTL_SECONDS
from src.services.real_data_service import (
    SP_RULE_LABEL,
    PdbAggregates,
    PdbExchange,
    PdbFacility,
    PeeringDbStatus,
    RealDataState,
    get_peeringdb_status,
)
from src.ui.charts import FONT, GRID, TRANSPARENT
from src.ui.real_data import (
    REFRESH_COOLDOWN_SECONDS,
    collected_at_label,
    select_display_status,
    stale_banner,
)

_LAST_OK_KEY = "peeringdb_last_ok"
_LAST_REFRESH_KEY = "peeringdb_last_refresh"
_LAST_ERROR_KEY = "peeringdb_last_error"

EMPTY_MESSAGES = {
    "exchanges": "Nenhum IXP com contagem de redes disponível no momento.",
    "map": "Nenhum data center com coordenadas para exibir no mapa.",
    "sp_facilities": "Nenhum data center em São Paulo na amostra.",
}


class PeeringDbUnavailable(Exception):
    def __init__(self, status: PeeringDbStatus) -> None:
        self.status = status
        super().__init__(status.message)


def empty_message(kind: str) -> str:
    return EMPTY_MESSAGES.get(kind, "Sem dados disponíveis no momento.")


def top_exchange_label(aggregates: PdbAggregates) -> str:
    exchange = aggregates.top_exchange
    if exchange is None:
        return "N/D"
    return f"{exchange.name} ({exchange.net_count})"


def peeringdb_kpis(aggregates: PdbAggregates) -> tuple[tuple[str, str], ...]:
    return (
        ("IXPs no Brasil", str(aggregates.ix_total)),
        ("IXPs em SP", str(aggregates.ix_sp)),
        ("Data centers no Brasil", str(aggregates.fac_total)),
        ("Data centers em SP", str(aggregates.fac_sp)),
        ("Maior IXP por redes", top_exchange_label(aggregates)),
    )


def top_exchanges(exchanges: tuple[PdbExchange, ...], limit: int = 10) -> tuple[PdbExchange, ...]:
    """Ixs com contagem de redes; o service já ordena desc e deixa None por último."""
    ranked = [item for item in exchanges if item.net_count is not None]
    return tuple(ranked[:limit])


def excluded_none_count(exchanges: tuple[PdbExchange, ...]) -> int:
    return sum(1 for item in exchanges if item.net_count is None)


def excluded_note(count: int) -> str | None:
    if count <= 0:
        return None
    return f"{count} IXP(s) sem contagem de redes; fora do gráfico."


def sp_facilities(facilities: tuple[PdbFacility, ...]) -> tuple[PdbFacility, ...]:
    """Data centers em SP ordenados por redes (desc), sem contagem por último.

    O campo in_sp vem do service: cidade normalizada sem acento/caixa igual a
    "sao paulo" ou, para data centers com coordenadas, Haversine até
    SAO_PAULO_RADIUS_KM do centro de São Paulo.
    """
    sp = [item for item in facilities if item.in_sp]
    sp.sort(
        key=lambda item: item.net_count if item.net_count is not None else -1,
        reverse=True,
    )
    return tuple(sp)


def facilities_with_coords(facilities: tuple[PdbFacility, ...]) -> tuple[PdbFacility, ...]:
    return tuple(item for item in facilities if item.lat is not None and item.lon is not None)


def peeringdb_unavailable_message(status: PeeringDbStatus) -> str:
    return status.message


def partial_notice(status: PeeringDbStatus) -> str | None:
    """Aviso de coleta parcial quando o Core informa endpoints obtidos no erro."""
    if not status.fetched_endpoints:
        return None
    return (
        "Coleta parcial: parte dos dados chegou, mas a carga não terminou; "
        "as listas parciais não são exibidas."
    )


def format_wait(seconds: float) -> str:
    """Espera curta em segundos e longa em minutos, com prefixo de aproximação."""
    total = ceil(seconds) if seconds > 0 else 0
    if total < 60:
        return f"~{total} s"
    return f"~{ceil(total / 60)} min"


def cooldown_seconds(status: object | None) -> int:
    """Cooldown do botão: honra o retry_after do status, sem descer do padrão."""
    value = getattr(status, "retry_after_seconds", None) if status is not None else None
    retry = value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0
    return max(REFRESH_COOLDOWN_SECONDS, retry)


def cooldown_remaining(
    anchor: float | None, status: object | None, *, now: float | None = None
) -> int:
    if anchor is None:
        return 0
    reference = time.monotonic() if now is None else now
    return max(0, ceil(cooldown_seconds(status) - (reference - anchor)))


def footer_caption(data: PeeringDbStatus) -> str:
    return (
        f"Coleta: {collected_at_label(data.collected_at)} · "
        f"{data.requests_made} requisição(ões) · [Fonte: PeeringDB]({data.source})"
    )


@st.cache_data(ttl=PEERINGDB_CACHE_TTL_SECONDS, show_spinner=False)
def _load_peeringdb() -> PeeringDbStatus:
    status = get_peeringdb_status()
    if status.state == RealDataState.UNAVAILABLE:
        raise PeeringDbUnavailable(status)
    return status


def _refresh_peeringdb() -> None:
    _load_peeringdb.clear()
    st.session_state.pop(_LAST_ERROR_KEY, None)
    st.session_state[_LAST_REFRESH_KEY] = time.monotonic()


def _style(figure: go.Figure, *, left: int = 42, height: int = 340) -> go.Figure:
    figure.update_layout(
        height=height,
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


def exchange_bar_figure(exchanges: tuple[PdbExchange, ...]) -> go.Figure:
    ranked = top_exchanges(exchanges)
    figure = go.Figure()
    if not ranked:
        figure.add_annotation(
            text=empty_message("exchanges"),
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
        return _style(figure)
    counts = [item.net_count if item.net_count is not None else 0 for item in ranked]
    figure.add_trace(
        go.Bar(
            x=counts,
            y=[f"{item.name} ({item.city})" for item in ranked],
            orientation="h",
            marker_color="#63d9f4",
            text=counts,
            textposition="outside",
            hovertemplate="%{y}: %{x} redes<extra></extra>",
            showlegend=False,
        )
    )
    figure.update_xaxes(
        title_text="Redes conectadas",
        range=[0, max(counts) * 1.15 + 1],
    )
    figure.update_yaxes(autorange="reversed", tickfont={"size": 10}, showgrid=False)
    return _style(figure)


def facility_map_figure(facilities: tuple[PdbFacility, ...]) -> go.Figure:
    figure = go.Figure()
    mappable = facilities_with_coords(facilities)
    for wanted_sp, label, color, size in (
        (False, "Demais localidades", "#63d9f4", 6),
        (True, "São Paulo", "#33d6a6", 11),
    ):
        selected = [item for item in mappable if item.in_sp == wanted_sp]
        if not selected:
            continue
        figure.add_trace(
            go.Scattergeo(
                lat=[item.lat for item in selected],
                lon=[item.lon for item in selected],
                mode="markers",
                marker={
                    "size": size,
                    "color": color,
                    "line": {"color": "#0b1020", "width": 1},
                },
                text=[
                    f"Data center {item.fac_id}<br>{item.name}<br>{item.city}<br>"
                    f"Redes: {item.net_count if item.net_count is not None else 'N/D'}<br>"
                    f"São Paulo: {'Sim' if item.in_sp else 'Não'}"
                    for item in selected
                ],
                hoverinfo="text",
                name=label,
            )
        )
    figure.update_geos(
        scope="south america",
        projection_type="equirectangular",
        showland=True,
        landcolor="#23344e",
        showocean=True,
        oceancolor="#101a2c",
        showcountries=True,
        countrycolor="#596983",
        bgcolor="#111a2d",
    )
    figure.update_layout(
        height=470,
        margin={"l": 0, "r": 0, "t": 8, "b": 0},
        paper_bgcolor="#111a2d",
        font={"color": FONT},
        legend={"orientation": "h", "y": -0.02},
    )
    return figure


def render_peeringdb() -> None:
    st.subheader("Internet pública — PeeringDB")
    st.info(
        "Dados públicos de infraestrutura de interconexão (IXPs e data centers). "
        "Eles não indicam incidentes nem desempenho de operadoras. "
        "A simulação NOC permanece separada."
    )
    anchor = st.session_state.get(_LAST_REFRESH_KEY)
    last_error: PeeringDbStatus | None = st.session_state.get(_LAST_ERROR_KEY)
    current: PeeringDbStatus | None = None
    load_error: PeeringDbStatus | None = None
    if last_error is not None and cooldown_remaining(anchor, last_error) > 0:
        load_error = last_error
    else:
        try:
            with st.spinner("Consultando PeeringDB..."):
                current = _load_peeringdb()
        except PeeringDbUnavailable as exc:
            load_error = exc.status
            st.session_state[_LAST_ERROR_KEY] = exc.status
            st.session_state[_LAST_REFRESH_KEY] = time.monotonic()
        else:
            st.session_state.pop(_LAST_ERROR_KEY, None)
    cooldown_status = load_error if load_error is not None else current
    remaining = cooldown_remaining(st.session_state.get(_LAST_REFRESH_KEY), cooldown_status)
    st.button(
        "Atualizar dados reais",
        disabled=remaining > 0,
        on_click=_refresh_peeringdb,
    )
    if remaining > 0:
        st.caption(f"Nova atualização disponível em {format_wait(remaining)}.")
    data = select_display_status(current, st.session_state.get(_LAST_OK_KEY))
    notice = partial_notice(load_error) if load_error is not None else None
    if data is None:
        if load_error is not None:
            st.warning(peeringdb_unavailable_message(load_error))
            if notice is not None:
                st.info(notice)
            st.markdown(f"Fonte: [PeeringDB]({load_error.source})")
        return
    if current is None:
        st.warning(stale_banner(data))
        if notice is not None:
            st.info(notice)
    else:
        st.session_state[_LAST_OK_KEY] = data
    st.caption(data.message)
    aggregates = data.aggregates
    if aggregates is None:
        st.warning("Agregados indisponíveis no momento.")
        return
    columns = st.columns(5)
    for column, (label, value) in zip(columns, peeringdb_kpis(aggregates), strict=True):
        column.metric(label, value)
    st.caption(SP_RULE_LABEL)

    st.subheader("Top 10 IXPs por redes conectadas")
    if top_exchanges(data.exchanges):
        st.plotly_chart(exchange_bar_figure(data.exchanges), width="stretch")
        note = excluded_note(excluded_none_count(data.exchanges))
        if note is not None:
            st.caption(note)
    else:
        st.info(empty_message("exchanges"))

    if facilities_with_coords(data.facilities):
        st.plotly_chart(facility_map_figure(data.facilities), width="stretch")
    else:
        st.info(empty_message("map"))

    sp = sp_facilities(data.facilities)
    st.subheader("Data centers em São Paulo")
    if not sp:
        st.info(empty_message("sp_facilities"))
    else:
        rows = pd.DataFrame(
            {
                "Data center": item.name,
                "Cidade": item.city,
                "Redes": item.net_count if item.net_count is not None else "N/D",
            }
            for item in sp
        )
        st.dataframe(rows, hide_index=True, width="stretch")

    if data.invalid_count:
        st.warning(f"{data.invalid_count} registros descartados por dados inválidos.")
    st.caption(footer_caption(data))
