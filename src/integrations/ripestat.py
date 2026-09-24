import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from math import ceil
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.config import (
    RIPESTAT_ASNS,
    RIPESTAT_BASE_URL,
    RIPESTAT_REQUEST_INTERVAL_SECONDS,
    RIPESTAT_SOURCEAPP,
    RIPESTAT_TIMEOUT_SECONDS,
    RIPESTAT_TOTAL_BUDGET_SECONDS,
)

USER_AGENT = "aiops-network-dashboard/0.1 (portfolio lab)"
Opener = Callable[..., Any]


class RipeStatError(Exception):
    """Falha de transporte, limite de requisições ou resposta inválida do RIPEstat."""

    def __init__(
        self,
        message: str = "Não foi possível consultar o RIPEstat.",
        *,
        status_code: int | None = None,
        requests_made: int = 0,
        invalid_count: int = 0,
        retry_after_seconds: int | None = None,
        fetched_asns: tuple[str, ...] = (),
        failed_asns: tuple[str, ...] = (),
        records: tuple["RipeStatRawRecord", ...] = (),
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.requests_made = requests_made
        self.invalid_count = invalid_count
        self.retry_after_seconds = retry_after_seconds
        self.fetched_asns = fetched_asns
        self.failed_asns = failed_asns
        self.records = records


@dataclass(frozen=True)
class RipeStatRawVisibility:
    v4_seeing: int | None
    v4_total: int | None
    v6_seeing: int | None
    v6_total: int | None


@dataclass(frozen=True)
class RipeStatRawRecord:
    asn: str
    name: str
    visibility: RipeStatRawVisibility
    v4_prefixes: int | None
    v6_prefixes: int | None
    first_seen: str | None
    last_seen: str | None
    query_time: str | None


@dataclass(frozen=True)
class RipeStatResult:
    records: tuple[RipeStatRawRecord, ...]
    requests_made: int
    invalid_count: int = 0
    fetched_asns: tuple[str, ...] = ()
    failed_asns: tuple[str, ...] = ()
    retry_after_seconds: int | None = None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _parse_seen_time(value: object) -> tuple[str | None, int]:
    """Extrai timestamp textual de first_seen/last_seen ou contabiliza como inválido."""
    if value is None:
        return None, 0
    if isinstance(value, dict):
        t = value.get("time")
        if isinstance(t, str) and t.strip():
            return t.strip(), 0
        return None, 1
    if isinstance(value, str):
        if value.strip():
            return value.strip(), 0
        return None, 1
    return None, 1


def format_retry_after(seconds: int | None) -> str:
    """Formata o tempo de espera de Retry-After de forma legível (ex.: '~45 s', '~26 min')."""
    if seconds is None:
        return ""
    total = ceil(seconds) if seconds > 0 else 0
    if total < 60:
        return f"~{total} s"
    return f"~{ceil(total / 60)} min"


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


def _parse_asn_record(
    payload: object,
    asn_code: str,
    friendly_name: str,
) -> tuple[RipeStatRawRecord, int]:
    """Parse mínimo e defensivo dos dados de visibilidade de roteamento do RIPEstat."""
    if not isinstance(payload, dict):
        raise RipeStatError(f"Não foi possível consultar o RIPEstat para {asn_code}.")

    status = payload.get("status")
    if status != "ok":
        raise RipeStatError(f"Não foi possível consultar o RIPEstat para {asn_code}: status {status!r}.")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise RipeStatError(f"Não foi possível consultar o RIPEstat para {asn_code}: esquema inesperado.")

    invalid_fields = 0

    # 1. Visibilidade v4 e v6 observada por peers do RIS
    raw_visibility = data.get("visibility")
    v4_seeing: int | None = None
    v4_total: int | None = None
    v6_seeing: int | None = None
    v6_total: int | None = None

    if isinstance(raw_visibility, dict):
        v4_data = raw_visibility.get("v4")
        if isinstance(v4_data, dict):
            v4_seeing = _optional_int(v4_data.get("ris_peers_seeing"))
            if v4_data.get("ris_peers_seeing") is not None and v4_seeing is None:
                invalid_fields += 1
            v4_total = _optional_int(v4_data.get("total_ris_peers"))
            if v4_data.get("total_ris_peers") is not None and v4_total is None:
                invalid_fields += 1
            # Normalização: se seeing > total, trata como inválido
            if v4_seeing is not None and v4_total is not None and v4_seeing > v4_total:
                v4_seeing = None
                v4_total = None
                invalid_fields += 1
        elif v4_data is not None:
            invalid_fields += 1

        v6_data = raw_visibility.get("v6")
        if isinstance(v6_data, dict):
            v6_seeing = _optional_int(v6_data.get("ris_peers_seeing"))
            if v6_data.get("ris_peers_seeing") is not None and v6_seeing is None:
                invalid_fields += 1
            v6_total = _optional_int(v6_data.get("total_ris_peers"))
            if v6_data.get("total_ris_peers") is not None and v6_total is None:
                invalid_fields += 1
            # Normalização: se seeing > total, trata como inválido
            if v6_seeing is not None and v6_total is not None and v6_seeing > v6_total:
                v6_seeing = None
                v6_total = None
                invalid_fields += 1
        elif v6_data is not None:
            invalid_fields += 1
    elif raw_visibility is not None:
        invalid_fields += 1

    # 2. Contagem de prefixos anunciados v4 e v6
    raw_space = data.get("announced_space")
    v4_prefixes: int | None = None
    v6_prefixes: int | None = None

    if isinstance(raw_space, dict):
        v4_space = raw_space.get("v4")
        if isinstance(v4_space, dict):
            v4_prefixes = _optional_int(v4_space.get("prefixes"))
            if v4_space.get("prefixes") is not None and v4_prefixes is None:
                invalid_fields += 1
        elif v4_space is not None:
            invalid_fields += 1

        v6_space = raw_space.get("v6")
        if isinstance(v6_space, dict):
            v6_prefixes = _optional_int(v6_space.get("prefixes"))
            if v6_space.get("prefixes") is not None and v6_prefixes is None:
                invalid_fields += 1
        elif v6_space is not None:
            invalid_fields += 1
    elif raw_space is not None:
        invalid_fields += 1

    # 3. first_seen, last_seen e query_time
    first_seen, first_invalid = _parse_seen_time(data.get("first_seen"))
    last_seen, last_invalid = _parse_seen_time(data.get("last_seen"))
    invalid_fields += first_invalid + last_invalid

    raw_query_time = data.get("query_time")
    query_time: str | None = None
    if isinstance(raw_query_time, str) and raw_query_time.strip():
        query_time = raw_query_time.strip()
    elif raw_query_time is not None:
        invalid_fields += 1

    record = RipeStatRawRecord(
        asn=asn_code,
        name=friendly_name,
        visibility=RipeStatRawVisibility(
            v4_seeing=v4_seeing,
            v4_total=v4_total,
            v6_seeing=v6_seeing,
            v6_total=v6_total,
        ),
        v4_prefixes=v4_prefixes,
        v6_prefixes=v6_prefixes,
        first_seen=first_seen,
        last_seen=last_seen,
        query_time=query_time,
    )
    return record, invalid_fields


def fetch_ripestat_data(
    asns: Sequence[tuple[str, str] | str] = RIPESTAT_ASNS,
    opener: Opener = urlopen,
    *,
    timeout: int = RIPESTAT_TIMEOUT_SECONDS,
    total_budget: float = RIPESTAT_TOTAL_BUDGET_SECONDS,
    request_interval: float = RIPESTAT_REQUEST_INTERVAL_SECONDS,
    sourceapp: str = RIPESTAT_SOURCEAPP,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> RipeStatResult:
    """Coleta dados de visibilidade no RIPEstat com isolamento por ASN, deduplicação e orçamento de tempo."""
    if timeout <= 0 or total_budget <= 0 or request_interval < 0:
        raise ValueError("Configuração de coleta do RIPEstat inválida.")

    normalized_targets: list[tuple[str, str]] = []
    seen_asns: set[str] = set()
    for item in asns:
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            code, name = str(item[0]).strip(), str(item[1]).strip()
        elif isinstance(item, str):
            code, name = item.strip(), item.strip()
        else:
            code, name = str(item).strip(), str(item).strip()

        key = code.upper()
        if key not in seen_asns:
            seen_asns.add(key)
            normalized_targets.append((code, name))

    all_asns = tuple(t[0] for t in normalized_targets)
    start_time = clock()
    requests_made = 0
    invalid_count = 0
    records: list[RipeStatRawRecord] = []
    fetched_asns: list[str] = []
    failed_asns: list[str] = []

    for i, (asn_code, friendly_name) in enumerate(normalized_targets):
        # Intervalo entre requisições para evitar rate limit
        if i > 0 and request_interval > 0:
            if (clock() - start_time) + request_interval >= total_budget:
                failed_asns.extend(all_asns[i:])
                if records:
                    return RipeStatResult(
                        records=tuple(records),
                        requests_made=requests_made,
                        invalid_count=invalid_count,
                        fetched_asns=tuple(fetched_asns),
                        failed_asns=tuple(failed_asns),
                    )
                raise RipeStatError(
                    "Orçamento de tempo excedido ao consultar o RIPEstat.",
                    requests_made=requests_made,
                    invalid_count=invalid_count,
                    fetched_asns=(),
                    failed_asns=tuple(failed_asns),
                    records=(),
                )
            sleep(request_interval)

        if (clock() - start_time) >= total_budget:
            failed_asns.extend(all_asns[i:])
            if records:
                return RipeStatResult(
                    records=tuple(records),
                    requests_made=requests_made,
                    invalid_count=invalid_count,
                    fetched_asns=tuple(fetched_asns),
                    failed_asns=tuple(failed_asns),
                )
            raise RipeStatError(
                "Orçamento de tempo excedido ao consultar o RIPEstat.",
                requests_made=requests_made,
                invalid_count=invalid_count,
                fetched_asns=(),
                failed_asns=tuple(failed_asns),
                records=(),
            )

        norm_resource = asn_code if asn_code.upper().startswith("AS") else f"AS{asn_code}"
        url = (
            f"{RIPESTAT_BASE_URL}/routing-status/data.json?"
            f"resource={norm_resource}&sourceapp={sourceapp}"
        )
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
                failed_asns.extend(all_asns[i:])
                wait_text = format_retry_after(retry_after)
                msg = (
                    f"Limite de requisições do RIPEstat atingido; tente novamente em {wait_text}."
                    if wait_text
                    else "Limite de requisições do RIPEstat atingido. Tente novamente mais tarde."
                )
                if records:
                    return RipeStatResult(
                        records=tuple(records),
                        requests_made=requests_made,
                        invalid_count=invalid_count,
                        fetched_asns=tuple(fetched_asns),
                        failed_asns=tuple(failed_asns),
                        retry_after_seconds=retry_after,
                    )
                raise RipeStatError(
                    msg,
                    status_code=exc.code,
                    requests_made=requests_made,
                    invalid_count=invalid_count,
                    retry_after_seconds=retry_after,
                    fetched_asns=(),
                    failed_asns=tuple(failed_asns),
                    records=(),
                ) from exc

            # Erro HTTP diferente de 429: isolamento por ASN (continua)
            failed_asns.append(asn_code)
            continue
        except (URLError, HTTPException, TimeoutError, OSError, ValueError):
            # Erro de transporte / timeout / JSON inválido: isolamento por ASN (continua)
            failed_asns.append(asn_code)
            continue

        try:
            record, invalid_fields = _parse_asn_record(payload, asn_code, friendly_name)
            invalid_count += invalid_fields
            records.append(record)
            fetched_asns.append(asn_code)
        except RipeStatError:
            # Envelope ou status não-ok específico deste ASN: isolamento por ASN (continua)
            failed_asns.append(asn_code)
            invalid_count += 1
            continue

    if not records:
        raise RipeStatError(
            "Não foi possível consultar o RIPEstat no momento. Tente atualizar mais tarde.",
            requests_made=requests_made,
            invalid_count=invalid_count,
            fetched_asns=(),
            failed_asns=tuple(failed_asns),
            records=(),
        )

    return RipeStatResult(
        records=tuple(records),
        requests_made=requests_made,
        invalid_count=invalid_count,
        fetched_asns=tuple(fetched_asns),
        failed_asns=tuple(failed_asns),
        retry_after_seconds=None,
    )
