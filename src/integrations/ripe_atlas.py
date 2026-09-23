import json
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPException
from math import isfinite
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.config import (
    RIPE_ATLAS_BASE_URL,
    RIPE_ATLAS_MAX_PAGES,
    RIPE_ATLAS_PAGE_SIZE,
    RIPE_ATLAS_TIMEOUT_SECONDS,
)

USER_AGENT = "aiops-network-dashboard/0.1 (portfolio lab)"
FIELDS = "id,status,asn_v4,asn_v6,geometry,is_anchor"


class RipeAtlasError(Exception):
    """Falha de transporte ou resposta inválida da API pública."""


@dataclass(frozen=True)
class AtlasProbe:
    probe_id: int
    status_id: int
    asn_v4: int | None
    asn_v6: int | None
    lat: float | None
    lon: float | None
    is_anchor: bool


@dataclass(frozen=True)
class AtlasResult:
    probes: tuple[AtlasProbe, ...]
    reported_count: int
    truncated: bool
    requests_made: int
    invalid_count: int = 0


Opener = Callable[..., Any]


def _optional_asn(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise RipeAtlasError("ASN inválido na resposta do RIPE Atlas.")


def _parse_probe(raw: object) -> AtlasProbe:
    if not isinstance(raw, dict):
        raise RipeAtlasError("Probe inválida na resposta do RIPE Atlas.")
    if not {"id", "status", "asn_v4", "asn_v6", "geometry", "is_anchor"} <= raw.keys():
        raise RipeAtlasError("Campos obrigatórios ausentes na probe.")
    probe_id = raw.get("id")
    status = raw.get("status")
    anchor = raw.get("is_anchor")
    if not isinstance(probe_id, int) or isinstance(probe_id, bool):
        raise RipeAtlasError("ID de probe inválido.")
    if (
        not isinstance(status, dict)
        or not isinstance(status.get("id"), int)
        or isinstance(status.get("id"), bool)
        or status["id"] not in range(5)
    ):
        raise RipeAtlasError("Status de probe inválido.")
    if not isinstance(anchor, bool):
        raise RipeAtlasError("Indicador de anchor inválido.")

    geometry = raw.get("geometry")
    lat = lon = None
    if geometry is not None:
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if (
            not isinstance(coordinates, list)
            or len(coordinates) != 2
            or any(
                not isinstance(value, (int, float)) or isinstance(value, bool)
                for value in coordinates
            )
        ):
            raise RipeAtlasError("Coordenadas de probe inválidas.")
        lon, lat = (float(value) for value in coordinates)
        if not (isfinite(lon) and isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
            raise RipeAtlasError("Coordenadas fora do intervalo válido.")
    return AtlasProbe(
        probe_id=probe_id,
        status_id=status["id"],
        asn_v4=_optional_asn(raw.get("asn_v4")),
        asn_v6=_optional_asn(raw.get("asn_v6")),
        lat=lat,
        lon=lon,
        is_anchor=anchor,
    )


def fetch_br_probes(
    opener: Opener = urlopen,
    *,
    page_size: int = RIPE_ATLAS_PAGE_SIZE,
    max_pages: int = RIPE_ATLAS_MAX_PAGES,
    timeout: int = RIPE_ATLAS_TIMEOUT_SECONDS,
) -> AtlasResult:
    if not 1 <= page_size <= 500 or max_pages < 1 or timeout <= 0:
        raise ValueError("Configuração de coleta inválida.")
    probes: list[AtlasProbe] = []
    reported_count = 0
    next_page: str | None = None
    requests_made = 0
    invalid_count = 0
    for page in range(1, max_pages + 1):
        params = {
            "country_code": "BR",
            "fields": FIELDS,
            "page_size": page_size,
            "page": page,
        }
        request = Request(
            f"{RIPE_ATLAS_BASE_URL}?{urlencode(params)}",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            method="GET",
        )
        try:
            requests_made += 1
            with opener(request, timeout=timeout) as response:
                payload = json.load(response)
        except (HTTPError, URLError, HTTPException, TimeoutError, OSError, ValueError) as exc:
            raise RipeAtlasError("Não foi possível consultar o RIPE Atlas.") from exc
        if not isinstance(payload, dict):
            raise RipeAtlasError("Resposta inesperada do RIPE Atlas.")
        results = payload.get("results")
        count = payload.get("count")
        next_page = payload.get("next")
        if (
            not isinstance(results, list)
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
            or (next_page is not None and not isinstance(next_page, str))
        ):
            raise RipeAtlasError("Esquema inesperado do RIPE Atlas.")
        reported_count = count
        for raw in results:
            try:
                probes.append(_parse_probe(raw))
            except RipeAtlasError:
                invalid_count += 1
        if not next_page:
            break
    return AtlasResult(tuple(probes), reported_count, bool(next_page), requests_made, invalid_count)
