import time
from datetime import datetime
from math import ceil

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import RIPE_ATLAS_CACHE_TTL_SECONDS, SAO_PAULO_RADIUS_KM
from src.services.real_data_service import (
    ACTIVE_STATUSES,
    RealDataState,
    RealDataStatus,
    get_real_data_status,
)

STATUS_COLORS = {
    "Conectado": "#33d6a6",
    "Desconectado": "#ef5f70",
    "Abandonado": "#9b7bff",
    "Nunca conectado": "#f3ad4e",
    "Baixado": "#8292aa",
}
REFRESH_COOLDOWN_SECONDS = 60
_LAST_OK_KEY = "real_data_last_ok"


class RealDataUnavailable(Exception):
    def __init__(self, status: RealDataStatus) -> None:
        self.status = status
        super().__init__(status.message)


def probes_summary(total_loaded: int, reported_count: int, truncated: bool) -> tuple[str, str]:
    """Rótulo e valor do card de probes, distinguindo carregadas de registradas."""
    if truncated:
        return "Probes carregadas", f"{total_loaded} de {reported_count}"
    return "Probes registradas", str(reported_count)


def unavailable_message(status: RealDataStatus) -> str:
    if status.reported_count > 0:
        return f"{status.message} Último total conhecido: {status.reported_count} probes."
    return status.message


def collected_at_label(collected_at: datetime | None) -> str:
    if collected_at is None:
        return "N/D"
    return f"{collected_at:%d/%m/%Y %H:%M} UTC"


def stale_banner(status: RealDataStatus) -> str:
    stamp = "N/D" if status.collected_at is None else f"{status.collected_at:%d/%m %H:%M} UTC"
    return f"Exibindo última coleta bem-sucedida de {stamp} — fonte indisponível agora"


def select_display_status(
    current: RealDataStatus | None, last_ok: RealDataStatus | None
) -> RealDataStatus | None:
    """Status a exibir: a carga atual quando OK, senão o último OK guardado."""
    if current is not None and current.state == RealDataState.OK:
        return current
    return last_ok


TRUNCATION_REASONS = {
    "max_pages": "limite de páginas",
    "time_budget": "limite de tempo",
}


def truncation_message(status: RealDataStatus) -> str:
    reason = TRUNCATION_REASONS.get(status.truncated_reason or "", "limite de coleta")
    return f"{status.message} Motivo: {reason}."


@st.cache_data(ttl=RIPE_ATLAS_CACHE_TTL_SECONDS, show_spinner=False)
def _load_real_data() -> RealDataStatus:
    status = get_real_data_status()
    if status.state == RealDataState.UNAVAILABLE:
        raise RealDataUnavailable(status)
    return status


def _refresh_real_data() -> None:
    _load_real_data.clear()
    st.session_state.real_data_last_refresh = time.monotonic()


def _map_figure(data: RealDataStatus) -> go.Figure:
    figure = go.Figure()
    for status, color in STATUS_COLORS.items():
        selected = [
            probe
            for probe in data.probes
            if probe.status == status and probe.lat is not None and probe.lon is not None
        ]
        if not selected:
            continue
        figure.add_trace(
            go.Scattergeo(
                lat=[probe.lat for probe in selected],
                lon=[probe.lon for probe in selected],
                mode="markers",
                marker={
                    "size": [11 if probe.em_sp else 6 for probe in selected],
                    "color": color,
                    "line": {"color": "#0b1020", "width": 1},
                },
                text=[
                    f"Probe {probe.probe_id}<br>{status}<br>"
                    f"ASN: {probe.asn if probe.asn is not None else 'não informado'}<br>"
                    f"São Paulo (100 km): {'Sim' if probe.em_sp else 'Não'}"
                    for probe in selected
                ],
                hoverinfo="text",
                name=status,
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
        font={"color": "#eaf4ff"},
        legend={"orientation": "h", "y": -0.02},
    )
    return figure


def render_real_data() -> None:
    st.subheader("Internet pública — RIPE Atlas")
    st.info(
        "Dados públicos reais de probes e anchors do Brasil. Eles não indicam incidentes "
        "de operadoras. A simulação NOC permanece separada."
    )
    last_refresh = st.session_state.get("real_data_last_refresh")
    remaining = (
        max(0, ceil(REFRESH_COOLDOWN_SECONDS - (time.monotonic() - last_refresh)))
        if last_refresh is not None
        else 0
    )
    st.button(
        "Atualizar dados reais",
        disabled=remaining > 0,
        on_click=_refresh_real_data,
    )
    if remaining > 0:
        st.caption(f"Nova atualização disponível em {remaining} s.")
    current: RealDataStatus | None = None
    load_error: RealDataStatus | None = None
    try:
        with st.spinner("Consultando RIPE Atlas..."):
            current = _load_real_data()
    except RealDataUnavailable as exc:
        load_error = exc.status
    data = select_display_status(current, st.session_state.get(_LAST_OK_KEY))
    if data is None:
        if load_error is not None:
            st.warning(unavailable_message(load_error))
            st.markdown(f"Fonte: [RIPE Atlas]({load_error.source})")
        return
    if current is None:
        st.warning(stale_banner(data))
    else:
        st.session_state[_LAST_OK_KEY] = data
    if data.truncated:
        st.warning(truncation_message(data))
    else:
        st.caption(data.message)
    if data.invalid_count:
        st.warning(f"{data.invalid_count} registros descartados por dados inválidos.")

    totals = data.aggregates
    if totals is None:
        st.warning("Agregados indisponíveis no momento.")
        return
    columns = st.columns(6)
    probe_label, probe_value = probes_summary(totals.total_br, data.reported_count, data.truncated)
    for column, label, value in zip(
        columns,
        (
            probe_label,
            "Probes ativas",
            "% conectadas",
            "Anchors",
            "Ativas em SP",
            "ASNs distintos (ativas)",
        ),
        (
            probe_value,
            str(totals.active),
            f"{totals.connected_percent:.1f}%",
            str(totals.anchors),
            str(totals.active_sp),
            str(totals.distinct_asns),
        ),
        strict=True,
    ):
        column.metric(label, value)
    st.caption(
        "% conectadas = Conectado entre as ativas (Conectado + Desconectado). "
        "Abandonado, Nunca conectado e Baixado ficam fora do percentual. "
        f"SP = raio local de {SAO_PAULO_RADIUS_KM} km do centro da cidade; "
        "pontos maiores no mapa."
    )
    st.plotly_chart(_map_figure(data), width="stretch")

    rows = pd.DataFrame(
        {"ASN": probe.asn, "Probe": probe.probe_id}
        for probe in data.probes
        if probe.status in ACTIVE_STATUSES and probe.asn is not None
    )
    st.subheader("ASNs com mais probes ativas")
    if rows.empty:
        st.info("Nenhum ASN informado na amostra.")
    else:
        top_asns = (
            rows.groupby("ASN", as_index=False)["Probe"]
            .nunique()
            .rename(columns={"Probe": "Probes"})
            .sort_values(["Probes", "ASN"], ascending=[False, True])
            .head(10)
        )
        st.dataframe(top_asns, hide_index=True, width="stretch")
    st.caption(
        f"Coleta: {collected_at_label(data.collected_at)} · "
        f"{data.requests_made} requisição(ões) · [Fonte: RIPE Atlas]({data.source})"
    )
