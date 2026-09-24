import time
from math import ceil

import pandas as pd
import streamlit as st

from src.services.real_data_service import (
    RealDataState,
    RipeStatAggregates,
    RipeStatRecord,
    RipeStatStatus,
    get_ripestat_status,
)
from src.ui.real_data import REFRESH_COOLDOWN_SECONDS, collected_at_label

DASH = "—"
NO_ANNOUNCEMENTS_TEXT = "Sem anúncios observados"

_LAST_REFRESH_KEY = "ripestat_last_refresh"
_LAST_NON_OK_KEY = "ripestat_last_non_ok"
_FORCE_REFRESH_KEY = "ripestat_force_refresh"

STATE_LABELS: dict[RealDataState, str] = {
    RealDataState.OK: "Completa",
    RealDataState.PARTIAL: "Parcial",
    RealDataState.UNAVAILABLE: "Indisponível",
}

INTRO_TEXT = (
    "Visibilidade BGP pública observada pelos coletores RIS do RIPEstat. "
    "É apenas a perspectiva desses peers; valores abaixo de 100% são comuns "
    "e não indicam problema operacional. A simulação NOC permanece separada."
)

LEGEND_TEXT = (
    "Visibilidade = % de peers RIS que enxergam rotas do ASN; "
    "valores abaixo de 100% são comuns e não indicam problema operacional. "
    "ASNs sem anúncios observados (ex.: route servers ou redes sem prefixos próprios) "
    "não indicam problema operacional."
)


def optional_int(value: int | None) -> str:
    return DASH if value is None else str(value)


def visibility_pct(value: float | None) -> str:
    if value is None:
        return DASH
    return f"{value:g}%"


def visibility_cell(pct: float | None, prefixes: int | None) -> str:
    """Célula de visibilidade neutra para 0% ou zero prefixos anunciados."""
    if pct == 0.0 or prefixes == 0:
        return NO_ANNOUNCEMENTS_TEXT
    return visibility_pct(pct)


def peers_ratio(seen: int | None, total: int | None) -> str:
    if seen is None and total is None:
        return DASH
    return f"{optional_int(seen)}/{optional_int(total)}"


def record_text(value: str | None) -> str:
    if value is None or not value.strip():
        return DASH
    return value


def records_table(records: tuple[RipeStatRecord, ...]) -> pd.DataFrame:
    rows = [
        {
            "ASN": record.asn,
            "Organização": record_text(record.name),
            "Visibilidade v4": visibility_cell(record.v4_visibility_pct, record.v4_prefixes),
            "Peers v4 (vendo/total)": peers_ratio(record.v4_seeing, record.v4_total),
            "Visibilidade v6": visibility_cell(record.v6_visibility_pct, record.v6_prefixes),
            "Peers v6 (vendo/total)": peers_ratio(record.v6_seeing, record.v6_total),
            "Prefixos v4": optional_int(record.v4_prefixes),
            "Prefixos v6": optional_int(record.v6_prefixes),
            "Primeira observação (first_seen)": record_text(record.first_seen),
            "Última observação (last_seen)": record_text(record.last_seen),
        }
        for record in records
    ]
    return pd.DataFrame(rows)


def ripestat_kpis(aggregates: RipeStatAggregates) -> tuple[tuple[str, str], ...]:
    monitored = aggregates.total_monitored
    return (
        ("ASNs monitorados", str(monitored)),
        ("Visibilidade plena v4", f"{aggregates.v4_full_visibility_count} de {monitored}"),
        ("Visibilidade plena v6", f"{aggregates.v6_full_visibility_count} de {monitored}"),
        ("Prefixos v4", str(aggregates.total_v4_prefixes)),
        ("Prefixos v6", str(aggregates.total_v6_prefixes)),
    )


def no_visibility_caption(aggregates: RipeStatAggregates) -> str:
    return (
        "ASNs sem anúncios observados: "
        f"v4 {aggregates.v4_no_visibility_count} · v6 {aggregates.v6_no_visibility_count}."
    )


def partial_notice(status: RipeStatStatus) -> str | None:
    """Aviso de coleta parcial: mensagem do serviço + ASNs sem dados nesta coleta."""
    if status.state != RealDataState.PARTIAL:
        return None
    if status.failed_asns:
        return f"{status.message} ASNs sem dados nesta coleta: {', '.join(status.failed_asns)}."
    return status.message


def footer_caption(status: RipeStatStatus) -> str:
    parts = [
        f"Coleta: {collected_at_label(status.collected_at)}",
        f"{status.requests_made} requisição(ões)",
    ]
    query_time = next((r.query_time for r in status.records if r.query_time), None)
    if query_time is not None:
        parts.append(f"Consulta RIPEstat: {query_time}")
    parts.append(f"[Fonte: RIPEstat]({status.source})")
    return " · ".join(parts)


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


def _refresh_ripestat() -> None:
    st.session_state.pop(_LAST_NON_OK_KEY, None)
    st.session_state[_LAST_REFRESH_KEY] = time.monotonic()
    st.session_state[_FORCE_REFRESH_KEY] = True


def _load_ripestat() -> RipeStatStatus:
    """Consulta o serviço; o cache em memória de 900 s do Core evita cache duplo."""
    force = bool(st.session_state.pop(_FORCE_REFRESH_KEY, False))
    return get_ripestat_status(ignore_cache=force)


def render_ripestat() -> None:
    st.subheader("Internet pública — RIPEstat (dados reais)")
    st.info(INTRO_TEXT)
    anchor = st.session_state.get(_LAST_REFRESH_KEY)
    stored_non_ok: RipeStatStatus | None = st.session_state.get(_LAST_NON_OK_KEY)
    current: RipeStatStatus | None = None
    load_non_ok: RipeStatStatus | None = None
    if stored_non_ok is not None and cooldown_remaining(anchor, stored_non_ok) > 0:
        load_non_ok = stored_non_ok
    else:
        with st.spinner("Consultando RIPEstat..."):
            current = _load_ripestat()
        if current.state == RealDataState.OK:
            st.session_state.pop(_LAST_NON_OK_KEY, None)
        else:
            st.session_state[_LAST_NON_OK_KEY] = current
            st.session_state[_LAST_REFRESH_KEY] = time.monotonic()
            load_non_ok = current
    cooldown_status = load_non_ok if load_non_ok is not None else current
    remaining = cooldown_remaining(st.session_state.get(_LAST_REFRESH_KEY), cooldown_status)
    st.button("Atualizar dados reais", disabled=remaining > 0, on_click=_refresh_ripestat)
    if remaining > 0:
        st.caption(f"Nova atualização disponível em {format_wait(remaining)}.")
    status = current if current is not None else load_non_ok
    if status is None:
        return
    st.caption(f"Situação da coleta: {STATE_LABELS[status.state]}")
    if status.state == RealDataState.UNAVAILABLE:
        st.info(status.message)
        st.markdown(f"Fonte: [RIPEstat]({status.source})")
        return
    notice = partial_notice(status)
    if notice is not None:
        st.warning(notice)
    else:
        st.caption(status.message)
    aggregates = status.aggregates
    if aggregates is not None:
        columns = st.columns(5)
        for column, (label, value) in zip(columns, ripestat_kpis(aggregates), strict=True):
            column.metric(label, value)
        st.caption(no_visibility_caption(aggregates))
    st.caption(LEGEND_TEXT)

    st.subheader("Visibilidade por ASN")
    if status.records:
        st.dataframe(records_table(status.records), hide_index=True, width="stretch")
    else:
        st.info("Nenhum ASN com dados de visibilidade nesta coleta.")
    if status.invalid_count:
        st.warning(f"{status.invalid_count} registros descartados por dados inválidos.")
    st.caption(footer_caption(status))
