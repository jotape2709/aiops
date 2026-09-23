import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from math import asin, cos, radians, sin, sqrt
from typing import Literal

from src.config import (
    RIPE_ATLAS_BASE_URL,
    SAO_PAULO_LAT,
    SAO_PAULO_LON,
    SAO_PAULO_RADIUS_KM,
)
from src.integrations.ripe_atlas import AtlasProbe, AtlasResult, fetch_br_probes


class RealDataState(str, Enum):
    OK = "ok"
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
    except Exception as exc:
        LOGGER.exception("Falha ao carregar dados públicos do RIPE Atlas")
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
