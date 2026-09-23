import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from math import isfinite
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.config import (
    PEERINGDB_BASE_URL,
    PEERINGDB_REQUEST_INTERVAL_SECONDS,
    PEERINGDB_TIMEOUT_SECONDS,
    PEERINGDB_TOTAL_BUDGET_SECONDS,
)

USER_AGENT = "aiops-network-dashboard/0.1 (portfolio lab)"
Opener = Callable[..., Any]


class PeeringDbError(Exception):
    """Falha de transporte, rate limit ou resposta inválida da API do PeeringDB."""

    def __init__(
        self,
        message: str = "Falha ao consultar o PeeringDB.",
        *,
        status_code: int | None = None,
        requests_made: int = 0,
        invalid_count: int = 0,
        retry_after_seconds: int | None = None,
        fetched_endpoints: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.requests_made = requests_made
        self.invalid_count = invalid_count
        self.retry_after_seconds = retry_after_seconds
        self.fetched_endpoints = fetched_endpoints


@dataclass(frozen=True)
class PeeringDbRawExchange:
    ix_id: int
    name: str
    city: str
    net_count: int | None
    fac_count: int | None


@dataclass(frozen=True)
class PeeringDbRawFacility:
    fac_id: int
    name: str
    city: str
    lat: float | None
    lon: float | None
    net_count: int | None


@dataclass(frozen=True)
class PeeringDbResult:
    exchanges: tuple[PeeringDbRawExchange, ...]
    facilities: tuple[PeeringDbRawFacility, ...]
    requests_made: int
    invalid_count: int = 0
    fetched_endpoints: tuple[str, ...] = ("ix", "fac")


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise PeeringDbError(f"Valor numérico inteiro inválido: {value!r}")


def _parse_exchange(raw: object) -> PeeringDbRawExchange:
    if not isinstance(raw, dict):
        raise PeeringDbError("Registro de IXP inválido.")
    ix_id = raw.get("id")
    name = raw.get("name")
    city = raw.get("city")
    if not isinstance(ix_id, int) or isinstance(ix_id, bool) or ix_id <= 0:
        raise PeeringDbError("ID de IXP inválido.")
    if not isinstance(name, str) or not name.strip():
        raise PeeringDbError("Nome de IXP inválido.")
    if city is not None and not isinstance(city, str):
        raise PeeringDbError("Cidade de IXP inválida.")
    net_count = _optional_int(raw.get("net_count"))
    fac_count = _optional_int(raw.get("fac_count"))
    # Campos de contato (tech_email, tech_phone, policy_email, policy_phone,
    # sales_email, sales_phone, notes) são estritamente omitidos e descartados.
    return PeeringDbRawExchange(
        ix_id=ix_id,
        name=name.strip(),
        city=(city or "").strip(),
        net_count=net_count,
        fac_count=fac_count,
    )


def _parse_facility(raw: object) -> PeeringDbRawFacility:
    if not isinstance(raw, dict):
        raise PeeringDbError("Registro de data center inválido.")
    fac_id = raw.get("id")
    name = raw.get("name")
    city = raw.get("city")
    if not isinstance(fac_id, int) or isinstance(fac_id, bool) or fac_id <= 0:
        raise PeeringDbError("ID de data center inválido.")
    if not isinstance(name, str) or not name.strip():
        raise PeeringDbError("Nome de data center inválido.")
    if city is not None and not isinstance(city, str):
        raise PeeringDbError("Cidade de data center inválida.")
    latitude = raw.get("latitude")
    longitude = raw.get("longitude")
    lat: float | None = None
    lon: float | None = None
    if latitude is not None:
        if (
            not isinstance(latitude, (int, float))
            or isinstance(latitude, bool)
            or not isfinite(latitude)
            or not -90 <= latitude <= 90
        ):
            raise PeeringDbError("Latitude inválida.")
        lat = float(latitude)
    if longitude is not None:
        if (
            not isinstance(longitude, (int, float))
            or isinstance(longitude, bool)
            or not isfinite(longitude)
            or not -180 <= longitude <= 180
        ):
            raise PeeringDbError("Longitude inválida.")
        lon = float(longitude)
    net_count = _optional_int(raw.get("net_count"))
    # Campos de contato (tech_email, tech_phone, policy_email, policy_phone,
    # sales_email, sales_phone, notes) são estritamente omitidos e descartados.
    return PeeringDbRawFacility(
        fac_id=fac_id,
        name=name.strip(),
        city=(city or "").strip(),
        lat=lat,
        lon=lon,
        net_count=net_count,
    )


def _parse_retry_after(
    header_value: str | None,
    now_fn: Callable[[], datetime] | None = None,
) -> int | None:
    """Extrai o tempo de espera do cabeçalho Retry-After em segundos ou formato HTTP-date."""
    if not header_value:
        return None
    val = header_value.strip()
    if not val:
        return None
    if val.isdigit():
        seconds = int(val)
        return seconds if seconds >= 1 else None
    try:
        dt = parsedate_to_datetime(val)
        now = now_fn() if now_fn else datetime.now(UTC)
        delta = (dt - now).total_seconds()
        seconds = int(delta)
        return seconds if seconds >= 1 else None
    except (TypeError, ValueError, OverflowError):
        return None


def fetch_peeringdb_data(
    opener: Opener = urlopen,
    *,
    timeout: int = PEERINGDB_TIMEOUT_SECONDS,
    total_budget: float = PEERINGDB_TOTAL_BUDGET_SECONDS,
    request_interval: float = PEERINGDB_REQUEST_INTERVAL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> PeeringDbResult:
    if timeout <= 0 or total_budget <= 0 or request_interval < 0:
        raise ValueError("Configuração de coleta inválida.")
    start_time = clock()
    requests_made = 0
    invalid_count = 0

    def _fetch_endpoint(
        endpoint_path: str,
        resource_name: str,
        fetched_so_far: tuple[str, ...] = (),
    ) -> list[Any]:
        nonlocal requests_made, invalid_count
        if (clock() - start_time) >= total_budget:
            raise PeeringDbError(
                "Orçamento de tempo excedido ao consultar o PeeringDB.",
                requests_made=requests_made,
                invalid_count=invalid_count,
                fetched_endpoints=fetched_so_far,
            )
        url = f"{PEERINGDB_BASE_URL}/{endpoint_path}?country=BR"
        request = Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            method="GET",
        )
        try:
            requests_made += 1
            with opener(request, timeout=timeout) as response:
                payload = json.load(response)
        except HTTPError as exc:
            retry_after = (
                _parse_retry_after(exc.headers.get("Retry-After")) if exc.headers else None
            )
            if exc.code == 429:
                msg = (
                    f"Limite de requisições do PeeringDB atingido; tente novamente em ~{retry_after} s."
                    if retry_after is not None
                    else "Limite de requisições do PeeringDB atingido. Tente novamente mais tarde."
                )
            else:
                msg = f"Falha ao consultar {resource_name} no PeeringDB (HTTP {exc.code})."
            raise PeeringDbError(
                msg,
                status_code=exc.code,
                requests_made=requests_made,
                invalid_count=invalid_count,
                retry_after_seconds=retry_after,
                fetched_endpoints=fetched_so_far,
            ) from exc
        except (URLError, HTTPException, TimeoutError, OSError, ValueError) as exc:
            raise PeeringDbError(
                f"Não foi possível consultar {resource_name} no PeeringDB.",
                requests_made=requests_made,
                invalid_count=invalid_count,
                fetched_endpoints=fetched_so_far,
            ) from exc

        if not isinstance(payload, dict):
            raise PeeringDbError(
                f"Resposta inesperada do PeeringDB para {resource_name}.",
                requests_made=requests_made,
                invalid_count=invalid_count,
                fetched_endpoints=fetched_so_far,
            )
        data = payload.get("data")
        if not isinstance(data, list):
            raise PeeringDbError(
                f"Esquema inesperado do PeeringDB para {resource_name}.",
                requests_made=requests_made,
                invalid_count=invalid_count,
                fetched_endpoints=fetched_so_far,
            )
        return data

    # 1. Consulta a pontos de troca de tráfego (IXPs)
    raw_ixs = _fetch_endpoint("ix", "IXPs", fetched_so_far=())
    exchanges: list[PeeringDbRawExchange] = []
    for raw in raw_ixs:
        try:
            exchanges.append(_parse_exchange(raw))
        except PeeringDbError:
            invalid_count += 1

    # Espaçamento controlado entre requisições para evitar rate limit
    if request_interval > 0:
        if (clock() - start_time) + request_interval >= total_budget:
            raise PeeringDbError(
                "Orçamento de tempo excedido ao consultar o PeeringDB.",
                requests_made=requests_made,
                invalid_count=invalid_count,
                fetched_endpoints=("ix",),
            )
        sleep(request_interval)

    # 2. Consulta a data centers (facilities)
    raw_facs = _fetch_endpoint("fac", "data centers", fetched_so_far=("ix",))
    facilities: list[PeeringDbRawFacility] = []
    for raw in raw_facs:
        try:
            facilities.append(_parse_facility(raw))
        except PeeringDbError:
            invalid_count += 1

    return PeeringDbResult(
        exchanges=tuple(exchanges),
        facilities=tuple(facilities),
        requests_made=requests_made,
        invalid_count=invalid_count,
        fetched_endpoints=("ix", "fac"),
    )
