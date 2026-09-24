import logging
import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from math import asin, cos, radians, sin, sqrt
from typing import Literal

from src.config import (
    PEERINGDB_SOURCE_URL,
    RIPE_ATLAS_BASE_URL,
    RIPESTAT_CACHE_TTL_SECONDS,
    RIPESTAT_PARTIAL_CACHE_TTL_SECONDS,
    RIPESTAT_SOURCE_URL,
    SAO_PAULO_LAT,
    SAO_PAULO_LON,
    SAO_PAULO_RADIUS_KM,
)
from src.integrations.peeringdb import (
    PeeringDbError,
    PeeringDbResult,
    fetch_peeringdb_data,
)
from src.integrations.ripe_atlas import (
    AtlasProbe,
    AtlasResult,
    RipeAtlasError,
    fetch_br_probes,
)
from src.integrations.ripestat import (
    RipeStatError,
    RipeStatRawRecord,
    RipeStatResult,
    fetch_ripestat_data,
    format_retry_after,
)


class RealDataState(str, Enum):
    OK = "ok"
    PARTIAL = "parcial"
    UNAVAILABLE = "indisponivel"


STATUS_LABELS = {
    0: "Nunca conectado",
    1: "Conectado",
    2: "Desconectado",
    3: "Abandonado",
    4: "Baixado",
}
ACTIVE_STATUSES = {"Conectado", "Desconectado"}
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Probe:
    probe_id: int
    status: str
    asn: int | None
    lat: float | None
    lon: float | None
    is_anchor: bool
    em_sp: bool


@dataclass(frozen=True)
class ProbeAggregates:
    total_br: int
    active: int
    connected: int
    connected_percent: float
    anchors: int
    active_sp: int
    distinct_asns: int


@dataclass(frozen=True)
class RealDataStatus:
    state: RealDataState
    message: str
    collected_at: datetime | None
    source: str
    probes: tuple[Probe, ...]
    aggregates: ProbeAggregates | None
    truncated: bool
    requests_made: int
    reported_count: int = 0
    invalid_count: int = 0
    truncated_reason: Literal["max_pages", "time_budget"] | None = None


def _within_sp_radius(lat: float | None, lon: float | None) -> bool:
    """Recorte local: até 100 km do centro de São Paulo, por Haversine."""
    if lat is None or lon is None:
        return False
    lat1, lat2 = radians(SAO_PAULO_LAT), radians(lat)
    delta_lat = lat2 - lat1
    delta_lon = radians(lon - SAO_PAULO_LON)
    hav = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(hav)) <= SAO_PAULO_RADIUS_KM


def _normalize(raw: AtlasProbe) -> Probe:
    return Probe(
        probe_id=raw.probe_id,
        status=STATUS_LABELS[raw.status_id],
        asn=raw.asn_v4 if raw.asn_v4 is not None else raw.asn_v6,
        lat=raw.lat,
        lon=raw.lon,
        is_anchor=raw.is_anchor,
        em_sp=_within_sp_radius(raw.lat, raw.lon),
    )


def get_real_data_status(
    fetcher: Callable[[], AtlasResult] = fetch_br_probes,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> RealDataStatus:
    try:
        batch = fetcher()
        probes = tuple(_normalize(probe) for probe in batch.probes)
        connected = sum(probe.status == "Conectado" for probe in probes)
        active = sum(probe.status in ACTIVE_STATUSES for probe in probes)
        total = len(probes)
        aggregates = ProbeAggregates(
            total_br=total,
            active=active,
            connected=connected,
            connected_percent=100 * connected / active if active else 0.0,
            anchors=sum(probe.is_anchor for probe in probes),
            active_sp=sum(probe.em_sp and probe.status in ACTIVE_STATUSES for probe in probes),
            distinct_asns=len(
                {
                    probe.asn
                    for probe in probes
                    if probe.status in ACTIVE_STATUSES and probe.asn is not None
                }
            ),
        )
        message = (
            f"Carregadas {total} de {batch.reported_count} probes."
            if batch.truncated
            else "Dados públicos do RIPE Atlas carregados."
        )
        return RealDataStatus(
            state=RealDataState.OK,
            message=message,
            collected_at=clock(),
            source=RIPE_ATLAS_BASE_URL,
            probes=probes,
            aggregates=aggregates,
            truncated=batch.truncated,
            requests_made=batch.requests_made,
            reported_count=batch.reported_count,
            invalid_count=batch.invalid_count,
            truncated_reason=batch.truncated_reason,
        )
    except RipeAtlasError as exc:
        LOGGER.warning("Falha ao carregar dados públicos do RIPE Atlas: %s", exc)
        return RealDataStatus(
            state=RealDataState.UNAVAILABLE,
            message="Dados públicos do RIPE Atlas indisponíveis no momento. Tente atualizar mais tarde.",
            collected_at=None,
            source=RIPE_ATLAS_BASE_URL,
            probes=(),
            aggregates=None,
            truncated=False,
            requests_made=getattr(exc, "requests_made", 0),
            reported_count=getattr(exc, "reported_count", 0),
            invalid_count=getattr(exc, "invalid_count", 0),
            truncated_reason=None,
        )
    except Exception:
        LOGGER.exception("Falha inesperada ao carregar dados públicos do RIPE Atlas")
        return RealDataStatus(
            state=RealDataState.UNAVAILABLE,
            message="Dados públicos do RIPE Atlas indisponíveis no momento. Tente atualizar mais tarde.",
            collected_at=None,
            source=RIPE_ATLAS_BASE_URL,
            probes=(),
            aggregates=None,
            truncated=False,
            requests_made=0,
            reported_count=0,
            invalid_count=0,
            truncated_reason=None,
        )


@dataclass(frozen=True)
class PdbExchange:
    ix_id: int
    name: str
    city: str
    net_count: int | None
    fac_count: int | None
    in_sp: bool


@dataclass(frozen=True)
class PdbFacility:
    fac_id: int
    name: str
    city: str
    lat: float | None
    lon: float | None
    net_count: int | None
    in_sp: bool


@dataclass(frozen=True)
class PdbAggregates:
    ix_total: int
    ix_sp: int
    fac_total: int
    fac_sp: int
    top_exchange: PdbExchange | None


@dataclass(frozen=True)
class PeeringDbStatus:
    """Status consolidado da consulta à API pública do PeeringDB.

    Invariantes do contrato:
    - aggregates: presente (PdbAggregates) somente quando state == RealDataState.OK;
      estritamente None quando state == RealDataState.UNAVAILABLE.
    - exchanges: tupla de PdbExchange ordenada por net_count decrescente (valores
      None por último, desempate por nome alfabético ascendente). Vazia quando UNAVAILABLE.
    - facilities: tupla de PdbFacility com a mesma ordenação de exchanges: ordenada por
      net_count decrescente (valores None por último, desempate por nome alfabético ascendente).
      Vazia quando UNAVAILABLE.
    - city: em PdbExchange e PdbFacility, normalizada para 'N/D' quando vazia ou ausente.
    - fetched_endpoints: tupla com os endpoints consultados com sucesso (ex. ('ix', 'fac')
      no sucesso completo, ('ix',) em falha parcial, () em falha total).
    """

    state: RealDataState
    message: str
    collected_at: datetime | None
    source: str
    requests_made: int
    exchanges: tuple[PdbExchange, ...]
    facilities: tuple[PdbFacility, ...]
    aggregates: PdbAggregates | None
    invalid_count: int
    retry_after_seconds: int | None = None
    fetched_endpoints: tuple[str, ...] = ()


SP_RULE_LABEL: str = f"Cidade = São Paulo ou até {SAO_PAULO_RADIUS_KM} km do centro"


def _normalize_city(city: str | None) -> str:
    """Normaliza o nome da cidade para comparação geográfica.

    Remove sufixos de UF/país após '/', ',' ou ' - ' (ex.: 'São Paulo/SP',
    'Sao Paulo, SP', 'São Paulo - SP' -> 'sao paulo'), descarta acentos
    e converte para minúsculas.
    """
    if not city:
        return ""
    prefix = re.split(r"[/,]|\s+-\s+", city, maxsplit=1)[0]
    decomposed = unicodedata.normalize("NFKD", prefix)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return without_accents.strip().lower()


def _is_in_sp(city: str | None, lat: float | None = None, lon: float | None = None) -> bool:
    """Regra de classificação geográfica de São Paulo.

    Um IXP ou data center é considerado em São Paulo se:
    1. O nome da cidade (normalizado sem sufixos como '/SP', ', SP', ' - SP', acentos ou caixa)
       for igual a 'sao paulo'.
    2. OU, para data centers com coordenadas (lat, lon), a distância de Haversine em relação
       ao centro de referência de São Paulo for menor ou igual a SAO_PAULO_RADIUS_KM (100 km).
    """
    if _normalize_city(city) == "sao paulo":
        return True
    if lat is not None and lon is not None:
        return _within_sp_radius(lat, lon)
    return False


def get_peeringdb_status(
    fetcher: Callable[[], PeeringDbResult] = fetch_peeringdb_data,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> PeeringDbStatus:
    try:
        batch = fetcher()
        exchanges = tuple(
            PdbExchange(
                ix_id=raw.ix_id,
                name=raw.name,
                city=raw.city.strip() if raw.city and raw.city.strip() else "N/D",
                net_count=raw.net_count,
                fac_count=raw.fac_count,
                in_sp=_is_in_sp(raw.city),
            )
            for raw in batch.exchanges
        )
        # Ordenado por net_count desc (None por último), desempate pelo nome asc
        sorted_exchanges = tuple(
            sorted(
                exchanges,
                key=lambda item: (
                    1 if item.net_count is None else 0,
                    -(item.net_count or 0),
                    item.name,
                ),
            )
        )
        facilities = tuple(
            PdbFacility(
                fac_id=raw.fac_id,
                name=raw.name,
                city=raw.city.strip() if raw.city and raw.city.strip() else "N/D",
                lat=raw.lat,
                lon=raw.lon,
                net_count=raw.net_count,
                in_sp=_is_in_sp(raw.city, raw.lat, raw.lon),
            )
            for raw in batch.facilities
        )
        # Ordenado com a mesma regra de exchanges: net_count desc, None por último, desempate por nome
        sorted_facilities = tuple(
            sorted(
                facilities,
                key=lambda item: (
                    1 if item.net_count is None else 0,
                    -(item.net_count or 0),
                    item.name,
                ),
            )
        )
        top_exchange: PdbExchange | None = None
        if sorted_exchanges and sorted_exchanges[0].net_count is not None:
            top_exchange = sorted_exchanges[0]

        aggregates = PdbAggregates(
            ix_total=len(sorted_exchanges),
            ix_sp=sum(ix.in_sp for ix in sorted_exchanges),
            fac_total=len(sorted_facilities),
            fac_sp=sum(fac.in_sp for fac in sorted_facilities),
            top_exchange=top_exchange,
        )
        message = (
            f"Carregados {len(sorted_exchanges)} IXPs e "
            f"{len(sorted_facilities)} data centers do PeeringDB."
        )
        return PeeringDbStatus(
            state=RealDataState.OK,
            message=message,
            collected_at=clock(),
            source=PEERINGDB_SOURCE_URL,
            requests_made=batch.requests_made,
            exchanges=sorted_exchanges,
            facilities=sorted_facilities,
            aggregates=aggregates,
            invalid_count=batch.invalid_count,
            fetched_endpoints=getattr(batch, "fetched_endpoints", ("ix", "fac")),
        )
    except PeeringDbError as exc:
        LOGGER.warning("Falha ao carregar dados públicos do PeeringDB: %s", exc)
        motivo = (
            exc.args[0]
            if exc.args
            else "Dados públicos do PeeringDB indisponíveis no momento. Tente atualizar mais tarde."
        )
        fetched_endpoints = getattr(exc, "fetched_endpoints", ())
        if "ix" in fetched_endpoints and "fac" not in fetched_endpoints:
            msg = f"IXPs carregados; data centers falharam: {motivo}"
        else:
            msg = motivo
        return PeeringDbStatus(
            state=RealDataState.UNAVAILABLE,
            message=msg,
            collected_at=None,
            source=PEERINGDB_SOURCE_URL,
            requests_made=getattr(exc, "requests_made", 0),
            exchanges=(),
            facilities=(),
            aggregates=None,
            invalid_count=getattr(exc, "invalid_count", 0),
            retry_after_seconds=getattr(exc, "retry_after_seconds", None),
            fetched_endpoints=fetched_endpoints,
        )
    except Exception:
        LOGGER.exception("Falha inesperada ao carregar dados públicos do PeeringDB")
        return PeeringDbStatus(
            state=RealDataState.UNAVAILABLE,
            message="Dados públicos do PeeringDB indisponíveis no momento. Tente atualizar mais tarde.",
            collected_at=None,
            source=PEERINGDB_SOURCE_URL,
            requests_made=0,
            exchanges=(),
            facilities=(),
            aggregates=None,
            invalid_count=0,
            retry_after_seconds=None,
            fetched_endpoints=(),
        )


@dataclass(frozen=True)
class RipeStatRecord:
    asn: str
    name: str
    v4_seeing: int | None
    v4_total: int | None
    v4_visibility_pct: float | None
    v6_seeing: int | None
    v6_total: int | None
    v6_visibility_pct: float | None
    v4_prefixes: int | None
    v6_prefixes: int | None
    first_seen: str | None
    last_seen: str | None
    query_time: str | None


@dataclass(frozen=True)
class RipeStatAggregates:
    total_monitored: int
    v4_full_visibility_count: int
    v6_full_visibility_count: int
    v4_partial_visibility_count: int
    v6_partial_visibility_count: int
    total_v4_prefixes: int
    total_v6_prefixes: int
    v4_no_visibility_count: int = 0
    v6_no_visibility_count: int = 0


@dataclass(frozen=True)
class RipeStatStatus:
    """Status consolidado da consulta à API pública de visibilidade do RIPEstat.

    Invariantes do contrato:
    - state: RealDataState.OK quando todos os ASNs monitorados forem consultados com sucesso;
      RealDataState.PARTIAL quando houver dados válidos para ao menos um ASN mas consulta não concluída para outro;
      RealDataState.UNAVAILABLE quando não for possível obter dados de nenhum ASN.
    - records: tupla de RipeStatRecord normalizados por ASN. Vazia apenas se UNAVAILABLE.
    - aggregates: presente (RipeStatAggregates) quando state for OK ou PARTIAL com records;
      estritamente None quando state for UNAVAILABLE.
    - collected_at: datetime quando state for OK ou PARTIAL; None quando UNAVAILABLE.
    """

    state: RealDataState
    message: str
    collected_at: datetime | None
    source: str
    requests_made: int
    records: tuple[RipeStatRecord, ...]
    aggregates: RipeStatAggregates | None
    invalid_count: int
    retry_after_seconds: int | None = None
    fetched_asns: tuple[str, ...] = ()
    failed_asns: tuple[str, ...] = ()


def _normalize_ripestat_record(raw: RipeStatRawRecord) -> RipeStatRecord:
    v4_seeing = raw.visibility.v4_seeing
    v4_total = raw.visibility.v4_total
    v4_pct: float | None = None
    if v4_total is not None and v4_total > 0 and v4_seeing is not None:
        if v4_seeing <= v4_total:
            v4_pct = round(100.0 * v4_seeing / v4_total, 2)
        else:
            v4_pct = None

    v6_seeing = raw.visibility.v6_seeing
    v6_total = raw.visibility.v6_total
    v6_pct: float | None = None
    if v6_total is not None and v6_total > 0 and v6_seeing is not None:
        if v6_seeing <= v6_total:
            v6_pct = round(100.0 * v6_seeing / v6_total, 2)
        else:
            v6_pct = None

    return RipeStatRecord(
        asn=raw.asn,
        name=raw.name,
        v4_seeing=v4_seeing,
        v4_total=v4_total,
        v4_visibility_pct=v4_pct,
        v6_seeing=v6_seeing,
        v6_total=v6_total,
        v6_visibility_pct=v6_pct,
        v4_prefixes=raw.v4_prefixes,
        v6_prefixes=raw.v6_prefixes,
        first_seen=raw.first_seen,
        last_seen=raw.last_seen,
        query_time=raw.query_time,
    )


def _build_ripestat_aggregates(records: tuple[RipeStatRecord, ...]) -> RipeStatAggregates:
    v4_full = sum(r.v4_visibility_pct is not None and r.v4_visibility_pct >= 99.0 for r in records)
    v6_full = sum(r.v6_visibility_pct is not None and r.v6_visibility_pct >= 99.0 for r in records)
    v4_partial = sum(
        r.v4_visibility_pct is not None and 0.0 < r.v4_visibility_pct < 99.0 for r in records
    )
    v6_partial = sum(
        r.v6_visibility_pct is not None and 0.0 < r.v6_visibility_pct < 99.0 for r in records
    )
    v4_no = sum(r.v4_visibility_pct is not None and r.v4_visibility_pct == 0.0 for r in records)
    v6_no = sum(r.v6_visibility_pct is not None and r.v6_visibility_pct == 0.0 for r in records)
    total_v4_prefixes = sum(r.v4_prefixes for r in records if r.v4_prefixes is not None)
    total_v6_prefixes = sum(r.v6_prefixes for r in records if r.v6_prefixes is not None)

    return RipeStatAggregates(
        total_monitored=len(records),
        v4_full_visibility_count=v4_full,
        v6_full_visibility_count=v6_full,
        v4_partial_visibility_count=v4_partial,
        v6_partial_visibility_count=v6_partial,
        total_v4_prefixes=total_v4_prefixes,
        total_v6_prefixes=total_v6_prefixes,
        v4_no_visibility_count=v4_no,
        v6_no_visibility_count=v6_no,
    )


_ripestat_cache: tuple[RipeStatStatus, float, float] | None = None


def clear_ripestat_cache() -> None:
    """Limpa o cache em memória das consultas ao RIPEstat."""
    global _ripestat_cache
    _ripestat_cache = None


def _do_get_ripestat_status(
    fetcher: Callable[[], RipeStatResult],
    clock: Callable[[], datetime],
) -> RipeStatStatus:
    try:
        batch = fetcher()
        records = tuple(_normalize_ripestat_record(r) for r in batch.records)
        retry_after = getattr(batch, "retry_after_seconds", None)
        if batch.failed_asns and not records:
            state = RealDataState.UNAVAILABLE
            message = (
                f"Limite de requisições do RIPEstat atingido; tente novamente em {format_retry_after(retry_after)}."
                if retry_after
                else "Dados públicos do RIPEstat indisponíveis no momento. Tente atualizar mais tarde."
            )
            collected_at = None
            aggregates = None
        elif batch.failed_asns:
            state = RealDataState.PARTIAL
            message = (
                f"Visibilidade obtida para {len(records)} de "
                f"{len(records) + len(batch.failed_asns)} ASNs monitorados."
            )
            collected_at = clock()
            aggregates = _build_ripestat_aggregates(records)
        else:
            state = RealDataState.OK
            message = "Dados públicos de visibilidade de roteamento do RIPEstat carregados."
            collected_at = clock()
            aggregates = _build_ripestat_aggregates(records)

        return RipeStatStatus(
            state=state,
            message=message,
            collected_at=collected_at,
            source=RIPESTAT_SOURCE_URL,
            requests_made=batch.requests_made,
            records=records,
            aggregates=aggregates,
            invalid_count=batch.invalid_count,
            retry_after_seconds=retry_after,
            fetched_asns=batch.fetched_asns,
            failed_asns=batch.failed_asns,
        )
    except RipeStatError as exc:
        LOGGER.warning("Consulta ao RIPEstat não concluída: %s", exc)
        retry_after = getattr(exc, "retry_after_seconds", None)
        fetched = getattr(exc, "fetched_asns", ())
        failed = getattr(exc, "failed_asns", ())
        raw_records = getattr(exc, "records", ())
        if fetched and raw_records:
            records = tuple(_normalize_ripestat_record(r) for r in raw_records)
            aggregates = _build_ripestat_aggregates(records)
            total = len(fetched) + len(failed)
            return RipeStatStatus(
                state=RealDataState.PARTIAL,
                message=f"Visibilidade obtida para {len(records)} de {total} ASNs monitorados.",
                collected_at=clock(),
                source=RIPESTAT_SOURCE_URL,
                requests_made=getattr(exc, "requests_made", 0),
                records=records,
                aggregates=aggregates,
                invalid_count=getattr(exc, "invalid_count", 0),
                retry_after_seconds=retry_after,
                fetched_asns=fetched,
                failed_asns=failed,
            )
        message = (
            f"Limite de requisições do RIPEstat atingido; tente novamente em {format_retry_after(retry_after)}."
            if exc.status_code == 429 and retry_after
            else "Dados públicos do RIPEstat indisponíveis no momento. Tente atualizar mais tarde."
        )
        return RipeStatStatus(
            state=RealDataState.UNAVAILABLE,
            message=message,
            collected_at=None,
            source=RIPESTAT_SOURCE_URL,
            requests_made=getattr(exc, "requests_made", 0),
            records=(),
            aggregates=None,
            invalid_count=getattr(exc, "invalid_count", 0),
            retry_after_seconds=retry_after,
            fetched_asns=(),
            failed_asns=failed,
        )
    except Exception:
        LOGGER.exception("Falha inesperada ao carregar dados públicos do RIPEstat")
        return RipeStatStatus(
            state=RealDataState.UNAVAILABLE,
            message="Dados públicos do RIPEstat indisponíveis no momento. Tente atualizar mais tarde.",
            collected_at=None,
            source=RIPESTAT_SOURCE_URL,
            requests_made=0,
            records=(),
            aggregates=None,
            invalid_count=0,
            retry_after_seconds=None,
            fetched_asns=(),
            failed_asns=(),
        )


def get_ripestat_status(
    fetcher: Callable[[], RipeStatResult] = fetch_ripestat_data,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    *,
    ttl_seconds: float = RIPESTAT_CACHE_TTL_SECONDS,
    partial_ttl_seconds: float = RIPESTAT_PARTIAL_CACHE_TTL_SECONDS,
    monotonic_clock: Callable[[], float] = time.monotonic,
    ignore_cache: bool = False,
) -> RipeStatStatus:
    """Obtém status público de visibilidade BGP no RIPEstat com cache em memória (OK: 900 s, PARTIAL: 300 s)."""
    global _ripestat_cache
    now_mono = monotonic_clock()
    if not ignore_cache and _ripestat_cache is not None:
        cached_status, cached_time, ttl = _ripestat_cache
        if (now_mono - cached_time) < ttl:
            return cached_status

    status = _do_get_ripestat_status(fetcher, clock)
    if status.state == RealDataState.OK:
        _ripestat_cache = (status, now_mono, ttl_seconds)
    elif status.state == RealDataState.PARTIAL:
        _ripestat_cache = (status, now_mono, partial_ttl_seconds)
    return status
