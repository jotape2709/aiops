import logging
from datetime import UTC, datetime
from typing import Literal

import pytest

from src.integrations.peeringdb import PeeringDbError
from src.integrations.ripe_atlas import AtlasProbe, AtlasResult, RipeAtlasError
from src.services.real_data_service import (
    RealDataState,
    get_peeringdb_status,
    get_real_data_status,
)


def sample_batch(
    *,
    truncated: bool = False,
    invalid_count: int = 0,
    truncated_reason: Literal["max_pages", "time_budget"] | None = None,
) -> AtlasResult:
    return AtlasResult(
        probes=(
            AtlasProbe(1, 1, 64500, None, -23.55, -46.63, True),
            AtlasProbe(2, 2, None, 64501, -22.90, -43.20, False),
            AtlasProbe(3, 0, None, None, None, None, False),
            AtlasProbe(4, 3, 64599, None, -23.55, -46.63, False),
        ),
        reported_count=10 if truncated else 4,
        truncated=truncated,
        requests_made=1,
        invalid_count=invalid_count,
        truncated_reason=truncated_reason
        if truncated_reason
        else ("max_pages" if truncated else None),
    )


def test_normalization_aggregates_and_sp_cut(monkeypatch) -> None:
    def block_network(*args, **kwargs):
        raise AssertionError("Network access attempted")

    monkeypatch.setattr("socket.socket", block_network)
    now = datetime(2026, 9, 23, tzinfo=UTC)
    result = get_real_data_status(fetcher=sample_batch, clock=lambda: now)
    assert result.state == RealDataState.OK
    assert result.collected_at == now
    assert [probe.status for probe in result.probes] == [
        "Conectado",
        "Desconectado",
        "Nunca conectado",
        "Abandonado",
    ]
    assert [probe.em_sp for probe in result.probes] == [True, False, False, True]
    assert result.probes[1].asn == 64501
    assert result.aggregates.total_br == 4
    assert result.aggregates.active == 2
    assert result.aggregates.connected == 1
    assert result.aggregates.connected_percent == 50.0
    assert result.aggregates.anchors == 1
    assert result.aggregates.active_sp == 1
    assert result.aggregates.distinct_asns == 2  # ASN 64599 pertence só à probe abandonada
    assert result.reported_count == 4


def test_truncated_batch_reports_loaded_and_discarded() -> None:
    result = get_real_data_status(fetcher=lambda: sample_batch(truncated=True, invalid_count=1))
    assert result.truncated
    assert result.truncated_reason == "max_pages"
    assert result.reported_count == 10
    assert result.invalid_count == 1
    assert result.message == "Carregadas 4 de 10 probes."


def test_client_failure_returns_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        "socket.socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network"))
    )

    def fail():
        raise RipeAtlasError("timeout")

    result = get_real_data_status(fetcher=fail)
    assert result.state == RealDataState.UNAVAILABLE
    assert result.aggregates is None
    assert "indisponíveis" in result.message
    assert result.reported_count == 0
    assert result.invalid_count == 0


def test_unavailable_preserves_known_reported_and_invalid_count(monkeypatch) -> None:
    monkeypatch.setattr(
        "socket.socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network"))
    )

    def fail_with_metadata():
        raise RipeAtlasError(
            "timeout on page 2",
            reported_count=1200,
            invalid_count=3,
            requests_made=2,
        )

    result = get_real_data_status(fetcher=fail_with_metadata)
    assert result.state == RealDataState.UNAVAILABLE
    assert result.reported_count == 1200
    assert result.invalid_count == 3
    assert result.requests_made == 2
    assert result.aggregates is None
    assert result.probes == ()


def test_peeringdb_normalization_aggregates_and_sorting(monkeypatch) -> None:
    def block_network(*args, **kwargs):
        raise AssertionError("Network access attempted")

    monkeypatch.setattr("socket.socket", block_network)
    from src.integrations.peeringdb import (
        PeeringDbRawExchange,
        PeeringDbRawFacility,
        PeeringDbResult,
    )
    from src.services.real_data_service import get_peeringdb_status

    sample_pdb = PeeringDbResult(
        exchanges=(
            PeeringDbRawExchange(1, "IX.br Campinas", "Campinas", 150, 2),
            PeeringDbRawExchange(2, "IX.br São Paulo", "São Paulo", 2500, 12),
            PeeringDbRawExchange(3, "IX.br Rio de Janeiro", "Rio de Janeiro", 800, 5),
            PeeringDbRawExchange(4, "IX.br Sem Conexões", "", None, 0),
        ),
        facilities=(
            PeeringDbRawFacility(10, "Equinix SP4", "Barueri", -23.4975, -46.8145, 594),
            PeeringDbRawFacility(20, "Ascenty SP1", "sao paulo", None, None, 200),
            PeeringDbRawFacility(30, "Fortaleza DC", "Fortaleza", -3.73, -38.52, 50),
            PeeringDbRawFacility(40, "DC Sem Redes", "", -23.55, -46.63, None),
        ),
        requests_made=2,
        invalid_count=1,
    )
    now = datetime(2026, 9, 23, 15, 0, tzinfo=UTC)
    result = get_peeringdb_status(fetcher=lambda: sample_pdb, clock=lambda: now)

    assert result.state == RealDataState.OK
    assert result.collected_at == now
    assert result.source == "https://www.peeringdb.com"
    assert result.requests_made == 2
    assert result.invalid_count == 1
    assert result.fetched_endpoints == ("ix", "fac")

    # Ordenado por net_count desc, None por último; desempate pelo nome
    assert [ix.name for ix in result.exchanges] == [
        "IX.br São Paulo",
        "IX.br Rio de Janeiro",
        "IX.br Campinas",
        "IX.br Sem Conexões",
    ]
    assert [ix.net_count for ix in result.exchanges] == [2500, 800, 150, None]
    assert [ix.in_sp for ix in result.exchanges] == [True, False, False, False]
    # Cidade vazia normalizada para 'N/D'
    assert result.exchanges[3].city == "N/D"

    # Facilities ordenadas com a MESMA regra de exchanges (net_count desc, None por último)
    assert [fac.name for fac in result.facilities] == [
        "Equinix SP4",
        "Ascenty SP1",
        "Fortaleza DC",
        "DC Sem Redes",
    ]
    assert [fac.in_sp for fac in result.facilities] == [True, True, False, True]
    assert result.facilities[3].city == "N/D"

    # Agregados e top_exchange tipado como PdbExchange
    assert result.aggregates is not None
    assert result.aggregates.ix_total == 4
    assert result.aggregates.ix_sp == 1
    assert result.aggregates.fac_total == 4
    assert result.aggregates.fac_sp == 3
    assert result.aggregates.top_exchange == result.exchanges[0]
    assert result.aggregates.top_exchange.name == "IX.br São Paulo"
    assert result.aggregates.top_exchange.net_count == 2500
    assert result.aggregates.top_exchange.city == "São Paulo"
    assert result.aggregates.top_exchange.in_sp is True
    with pytest.raises(TypeError):
        _a, _b = result.aggregates.top_exchange


def test_sp_rule_label_exported() -> None:
    from src.services.real_data_service import SP_RULE_LABEL

    assert "100 km" in SP_RULE_LABEL
    assert "São Paulo" in SP_RULE_LABEL


def test_peeringdb_top_exchange_none_when_empty() -> None:
    from src.integrations.peeringdb import PeeringDbResult
    from src.services.real_data_service import get_peeringdb_status

    sample_empty = PeeringDbResult(exchanges=(), facilities=(), requests_made=2)
    result = get_peeringdb_status(fetcher=lambda: sample_empty)
    assert result.state == RealDataState.OK
    assert result.aggregates is not None
    assert result.aggregates.top_exchange is None
    assert result.aggregates.ix_total == 0


def test_peeringdb_failure_returns_unavailable_and_never_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        "socket.socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network"))
    )
    from src.integrations.peeringdb import PeeringDbError
    from src.services.real_data_service import get_peeringdb_status

    def fail_with_msg():
        raise PeeringDbError(
            "Falha ao consultar data centers no PeeringDB (HTTP 503).",
            status_code=503,
            requests_made=2,
            invalid_count=0,
            fetched_endpoints=("ix",),
        )

    result = get_peeringdb_status(fetcher=fail_with_msg)
    assert result.state == RealDataState.UNAVAILABLE
    assert "IXPs carregados; data centers falharam:" in result.message
    assert "data centers no PeeringDB (HTTP 503)" in result.message
    assert result.requests_made == 2
    assert result.aggregates is None
    assert result.exchanges == ()
    assert result.facilities == ()
    assert result.fetched_endpoints == ("ix",)

    # Garante que até mesmo exceções inesperadas genéricas não quebram o serviço
    result_generic = get_peeringdb_status(
        fetcher=lambda: (_ for _ in ()).throw(RuntimeError("crash"))
    )
    assert result_generic.state == RealDataState.UNAVAILABLE
    assert "indisponíveis" in result_generic.message


def test_peeringdb_logging_distinguishes_expected_vs_unexpected(caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        get_peeringdb_status(
            fetcher=lambda: (_ for _ in ()).throw(
                PeeringDbError("rate limited", retry_after_seconds=30)
            )
        )
        assert any(
            r.levelno == logging.WARNING
            and "Falha ao carregar dados públicos do PeeringDB" in r.message
            for r in caplog.records
        )
        assert not any(r.levelno == logging.ERROR for r in caplog.records)

    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        get_peeringdb_status(
            fetcher=lambda: (_ for _ in ()).throw(RuntimeError("unexpected crash"))
        )
        assert any(
            r.levelno == logging.ERROR
            and "Falha inesperada ao carregar dados públicos do PeeringDB" in r.message
            for r in caplog.records
        )


def test_ripe_atlas_logging_distinguishes_expected_vs_unexpected(caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        get_real_data_status(fetcher=lambda: (_ for _ in ()).throw(RipeAtlasError("timeout")))
        assert any(
            r.levelno == logging.WARNING
            and "Falha ao carregar dados públicos do RIPE Atlas" in r.message
            for r in caplog.records
        )
        assert not any(r.levelno == logging.ERROR for r in caplog.records)

    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        get_real_data_status(
            fetcher=lambda: (_ for _ in ()).throw(RuntimeError("unexpected crash"))
        )
        assert any(
            r.levelno == logging.ERROR
            and "Falha inesperada ao carregar dados públicos do RIPE Atlas" in r.message
            for r in caplog.records
        )


def test_sp_city_normalization_and_geographic_classification() -> None:
    from src.integrations.peeringdb import PeeringDbRawExchange, PeeringDbResult
    from src.services.real_data_service import (
        _is_in_sp,
        _normalize_city,
        get_peeringdb_status,
    )

    # 1. Normalização de cidade com sufixos
    assert _normalize_city("São Paulo/SP") == "sao paulo"
    assert _normalize_city("Sao Paulo, SP") == "sao paulo"
    assert _normalize_city("São Paulo - SP") == "sao paulo"
    assert _normalize_city("São Paulo - Brasil") == "sao paulo"
    assert _normalize_city("São Paulo") == "sao paulo"
    assert _normalize_city("São Paulo de Olivença/AM") == "sao paulo de olivenca"
    assert _normalize_city("Santo André/SP") == "santo andre"
    assert _normalize_city("") == ""
    assert _normalize_city(None) == ""

    # 2. _is_in_sp para variantes de São Paulo
    assert _is_in_sp("São Paulo/SP") is True
    assert _is_in_sp("Sao Paulo, SP") is True
    assert _is_in_sp("São Paulo - SP") is True
    assert _is_in_sp("são paulo") is True

    # 3. Não-SP: São Paulo de Olivença/AM NÃO casa com SP
    assert _is_in_sp("São Paulo de Olivença/AM") is False

    # 4. Santo André/SP: sem coordenadas não casa por nome; com coordenadas próximas a SP casa via Haversine
    assert _is_in_sp("Santo André/SP") is False
    assert _is_in_sp("Santo André/SP", lat=-23.66, lon=-46.53) is True  # ~15 km do centro
    assert _is_in_sp("Santo André/SP", lat=-20.0, lon=-40.0) is False  # Fora do raio de 100 km

    # 5. Validação ponta a ponta no get_peeringdb_status: a cidade exibida permanece original
    sample = PeeringDbResult(
        exchanges=(
            PeeringDbRawExchange(1, "IX.br (PTT.br) São Paulo", "São Paulo/SP", 2500, 12),
            PeeringDbRawExchange(2, "IX.br Manaus Interior", "São Paulo de Olivença/AM", 10, 1),
        ),
        facilities=(),
        requests_made=2,
    )
    status = get_peeringdb_status(fetcher=lambda: sample)
    assert status.exchanges[0].in_sp is True
    assert status.exchanges[0].city == "São Paulo/SP"  # Mantém a original exibida
    assert status.exchanges[1].in_sp is False
    assert status.exchanges[1].city == "São Paulo de Olivença/AM"
    assert status.aggregates is not None
    assert status.aggregates.ix_sp == 1


# ---------------------------------------------------------------------------
# Testes do serviço RIPEstat
# ---------------------------------------------------------------------------

from src.config import RIPESTAT_SOURCE_URL
from src.integrations.ripestat import (
    RipeStatError,
    RipeStatRawRecord,
    RipeStatRawVisibility,
    RipeStatResult,
)
from src.services.real_data_service import (
    clear_ripestat_cache,
    get_ripestat_status,
)


@pytest.fixture(autouse=True)
def _reset_ripestat_cache():
    clear_ripestat_cache()
    yield
    clear_ripestat_cache()


def sample_ripestat_raw_records() -> tuple[RipeStatRawRecord, ...]:
    return (
        RipeStatRawRecord(
            asn="AS22548",
            name="NIC.br",
            visibility=RipeStatRawVisibility(
                v4_seeing=323, v4_total=325, v6_seeing=317, v6_total=317
            ),
            v4_prefixes=1,
            v6_prefixes=1,
            first_seen="2002-03-01T16:00:00",
            last_seen="2026-09-24T08:00:00",
            query_time="2026-09-24T08:00:00",
        ),
        RipeStatRawRecord(
            asn="AS1251",
            name="FAPESP / ANSP",
            visibility=RipeStatRawVisibility(
                v4_seeing=320, v4_total=325, v6_seeing=310, v6_total=317
            ),
            v4_prefixes=2,
            v6_prefixes=2,
            first_seen="2005-01-01T00:00:00",
            last_seen="2026-09-24T08:00:00",
            query_time="2026-09-24T08:00:00",
        ),
        RipeStatRawRecord(
            asn="AS1916",
            name="RNP",
            visibility=RipeStatRawVisibility(
                v4_seeing=325, v4_total=325, v6_seeing=317, v6_total=317
            ),
            v4_prefixes=5,
            v6_prefixes=4,
            first_seen="2000-01-01T00:00:00",
            last_seen="2026-09-24T08:00:00",
            query_time="2026-09-24T08:00:00",
        ),
    )


def test_ripestat_success_status() -> None:
    raw_records = sample_ripestat_raw_records()
    sample = RipeStatResult(
        records=raw_records,
        requests_made=3,
        invalid_count=0,
        fetched_asns=("AS22548", "AS1251", "AS1916"),
        failed_asns=(),
    )
    status = get_ripestat_status(fetcher=lambda: sample)
    assert status.state == RealDataState.OK
    assert "carregados" in status.message.lower()
    assert status.collected_at is not None
    assert status.source == RIPESTAT_SOURCE_URL
    assert status.requests_made == 3
    assert len(status.records) == 3
    assert status.fetched_asns == ("AS22548", "AS1251", "AS1916")
    assert status.failed_asns == ()

    # Normalização e cálculo de percentuais
    rec0 = status.records[0]
    assert rec0.asn == "AS22548"
    assert rec0.name == "NIC.br"
    assert rec0.v4_visibility_pct == 99.38
    assert rec0.v6_visibility_pct == 100.0

    # Agregados com contagem de no_visibility
    assert status.aggregates is not None
    assert status.aggregates.total_monitored == 3
    assert status.aggregates.v4_full_visibility_count == 2  # 99.38% e 100.0% >= 99%
    assert status.aggregates.v6_full_visibility_count == 2  # 100.0% e 100.0% >= 99%
    assert status.aggregates.v4_partial_visibility_count == 1  # 98.46%
    assert status.aggregates.v6_partial_visibility_count == 1  # 97.79%
    assert status.aggregates.v4_no_visibility_count == 0
    assert status.aggregates.v6_no_visibility_count == 0
    assert status.aggregates.total_v4_prefixes == 8
    assert status.aggregates.total_v6_prefixes == 7


def test_ripestat_aggregates_no_visibility_and_none_handling() -> None:
    records = (
        RipeStatRawRecord(
            asn="AS1",
            name="Zero ASN",
            visibility=RipeStatRawVisibility(v4_seeing=0, v4_total=100, v6_seeing=0, v6_total=100),
            v4_prefixes=0,
            v6_prefixes=0,
            first_seen=None,
            last_seen=None,
            query_time=None,
        ),
        RipeStatRawRecord(
            asn="AS2",
            name="None ASN",
            visibility=RipeStatRawVisibility(v4_seeing=None, v4_total=100, v6_seeing=100, v6_total=None),
            v4_prefixes=1,
            v6_prefixes=1,
            first_seen=None,
            last_seen=None,
            query_time=None,
        ),
    )
    sample = RipeStatResult(records=records, requests_made=2, fetched_asns=("AS1", "AS2"))
    status = get_ripestat_status(fetcher=lambda: sample)
    assert status.aggregates is not None
    # AS1 tem pct == 0.0 -> entra em no_visibility
    assert status.aggregates.v4_no_visibility_count == 1
    assert status.aggregates.v6_no_visibility_count == 1
    # AS2 tem pct None -> NÃO entra em nenhum balde
    assert status.aggregates.v4_full_visibility_count == 0
    assert status.aggregates.v4_partial_visibility_count == 0
    assert status.aggregates.v6_full_visibility_count == 0


def test_ripestat_partial_status_via_result_and_exception() -> None:
    raw_records = sample_ripestat_raw_records()[:1]

    # Caso 1: RipeStatResult com falha parcial
    sample_partial = RipeStatResult(
        records=raw_records,
        requests_made=3,
        invalid_count=0,
        fetched_asns=("AS22548",),
        failed_asns=("AS1251", "AS1916"),
    )
    status1 = get_ripestat_status(fetcher=lambda: sample_partial)
    assert status1.state == RealDataState.PARTIAL
    assert status1.collected_at is not None
    assert len(status1.records) == 1
    assert status1.aggregates is not None
    assert status1.fetched_asns == ("AS22548",)
    assert status1.failed_asns == ("AS1251", "AS1916")
    assert "Visibilidade obtida para 1 de 3" in status1.message

    clear_ripestat_cache()

    # Caso 2: RipeStatError com registros prévios preservados
    def fail_with_partial():
        raise RipeStatError(
            "Não foi possível consultar o RIPEstat para AS1251 (HTTP 503).",
            status_code=503,
            requests_made=2,
            fetched_asns=("AS22548",),
            failed_asns=("AS1251", "AS1916"),
            records=raw_records,
        )

    status2 = get_ripestat_status(fetcher=fail_with_partial)
    assert status2.state == RealDataState.PARTIAL
    assert status2.collected_at is not None
    assert len(status2.records) == 1
    assert status2.aggregates is not None
    assert "Visibilidade obtida para 1 de 3" in status2.message


def test_ripestat_429_in_middle_propagates_retry_after() -> None:
    raw_records = sample_ripestat_raw_records()[:1]
    sample = RipeStatResult(
        records=raw_records,
        requests_made=2,
        fetched_asns=("AS22548",),
        failed_asns=("AS1251", "AS1916"),
        retry_after_seconds=60,
    )
    status = get_ripestat_status(fetcher=lambda: sample)
    assert status.state == RealDataState.PARTIAL
    assert status.retry_after_seconds == 60


def test_ripestat_unavailable_status() -> None:
    def fail_total():
        raise RipeStatError(
            "Não foi possível consultar o RIPEstat.",
            status_code=None,
            requests_made=1,
            fetched_asns=(),
            failed_asns=("AS22548", "AS1251", "AS1916"),
            records=(),
        )

    status = get_ripestat_status(fetcher=fail_total)
    assert status.state == RealDataState.UNAVAILABLE
    assert status.collected_at is None
    assert status.aggregates is None
    assert status.records == ()
    assert status.fetched_asns == ()
    assert "indisponíveis" in status.message


def test_ripestat_429_propagates_retry_after() -> None:
    def fail_429():
        raise RipeStatError(
            "Limite de requisições do RIPEstat atingido.",
            status_code=429,
            requests_made=1,
            retry_after_seconds=60,
            fetched_asns=(),
            failed_asns=("AS22548", "AS1251", "AS1916"),
            records=(),
        )

    status = get_ripestat_status(fetcher=fail_429)
    assert status.state == RealDataState.UNAVAILABLE
    assert status.retry_after_seconds == 60
    assert "tente novamente em ~1 min" in status.message


def test_ripestat_unexpected_exception_handled() -> None:
    def crash():
        raise RuntimeError("unexpected fatal crash")

    status = get_ripestat_status(fetcher=crash)
    assert status.state == RealDataState.UNAVAILABLE
    assert status.collected_at is None
    assert status.aggregates is None
    assert "indisponíveis" in status.message


def test_ripestat_logging_distinguishes_expected_vs_unexpected(caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        get_ripestat_status(
            fetcher=lambda: (_ for _ in ()).throw(
                RipeStatError("erro esperado", retry_after_seconds=30)
            )
        )
        assert any(
            r.levelno == logging.WARNING
            and "Consulta ao RIPEstat não concluída" in r.message
            for r in caplog.records
        )
        assert not any(r.levelno == logging.ERROR for r in caplog.records)

    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        get_ripestat_status(
            fetcher=lambda: (_ for _ in ()).throw(RuntimeError("crash inesperado"))
        )
        assert any(
            r.levelno == logging.ERROR
            and "Falha inesperada ao carregar dados públicos do RIPEstat" in r.message
            for r in caplog.records
        )


def test_ripestat_cache_ttl_and_partial_and_unavailable() -> None:
    calls = 0
    now_monotonic = 1000.0
    mode = "ok"

    def mock_fetcher():
        nonlocal calls
        calls += 1
        if mode == "ok":
            return RipeStatResult(
                records=sample_ripestat_raw_records(),
                requests_made=3,
                fetched_asns=("AS22548", "AS1251", "AS1916"),
                failed_asns=(),
            )
        if mode == "partial":
            return RipeStatResult(
                records=sample_ripestat_raw_records()[:1],
                requests_made=3,
                fetched_asns=("AS22548",),
                failed_asns=("AS1251", "AS1916"),
            )
        raise RipeStatError(
            "Indisponível",
            requests_made=1,
            fetched_asns=(),
            failed_asns=("AS22548",),
        )

    # 1. OK cacheado por 900 s
    s1 = get_ripestat_status(fetcher=mock_fetcher, monotonic_clock=lambda: now_monotonic)
    assert s1.state == RealDataState.OK
    assert calls == 1

    # Dentro de 900 s -> usa cache
    s2 = get_ripestat_status(fetcher=mock_fetcher, monotonic_clock=lambda: now_monotonic + 500.0)
    assert s2.state == RealDataState.OK
    assert calls == 1

    # ignore_cache força consulta mesmo dentro do TTL
    s_forced = get_ripestat_status(
        fetcher=mock_fetcher,
        monotonic_clock=lambda: now_monotonic + 500.0,
        ignore_cache=True,
    )
    assert s_forced.state == RealDataState.OK
    assert calls == 2

    # Após 900 s (ex: 901 s após s_forced a 1401 s) -> expira
    s3 = get_ripestat_status(fetcher=mock_fetcher, monotonic_clock=lambda: now_monotonic + 1402.0)
    assert s3.state == RealDataState.OK
    assert calls == 3

    # 2. PARTIAL cacheado por 300 s
    mode = "partial"
    clear_ripestat_cache()
    p1 = get_ripestat_status(fetcher=mock_fetcher, monotonic_clock=lambda: now_monotonic + 2000.0)
    assert p1.state == RealDataState.PARTIAL
    assert calls == 4

    # Dentro de 300 s (ex: +200 s) -> usa cache
    p2 = get_ripestat_status(fetcher=mock_fetcher, monotonic_clock=lambda: now_monotonic + 2200.0)
    assert p2.state == RealDataState.PARTIAL
    assert calls == 4

    # Após 300 s (ex: +301 s) -> expira PARTIAL
    p3 = get_ripestat_status(fetcher=mock_fetcher, monotonic_clock=lambda: now_monotonic + 2301.0)
    assert p3.state == RealDataState.PARTIAL
    assert calls == 5

    # 3. UNAVAILABLE nunca é cacheado
    mode = "unavailable"
    clear_ripestat_cache()
    u1 = get_ripestat_status(fetcher=mock_fetcher, monotonic_clock=lambda: now_monotonic + 3000.0)
    assert u1.state == RealDataState.UNAVAILABLE
    assert calls == 6

    u2 = get_ripestat_status(fetcher=mock_fetcher, monotonic_clock=lambda: now_monotonic + 3001.0)
    assert u2.state == RealDataState.UNAVAILABLE
    assert calls == 7


def test_ripestat_seeing_greater_than_total_normalizes_to_none() -> None:
    records = (
        RipeStatRawRecord(
            asn="AS22548",
            name="NIC.br",
            visibility=RipeStatRawVisibility(v4_seeing=350, v4_total=325, v6_seeing=100, v6_total=100),
            v4_prefixes=1,
            v6_prefixes=1,
            first_seen=None,
            last_seen=None,
            query_time=None,
        ),
    )
    sample = RipeStatResult(records=records, requests_made=1, fetched_asns=("AS22548",))
    status = get_ripestat_status(fetcher=lambda: sample)
    assert status.records[0].v4_visibility_pct is None
    assert status.records[0].v6_visibility_pct == 100.0


def test_ripestat_prohibited_words_across_all_states() -> None:
    prohibited = ("incidente", "queda", "falha", "fora do ar")

    # 1. OK
    sample_ok = RipeStatResult(
        records=sample_ripestat_raw_records(),
        requests_made=3,
        fetched_asns=("AS22548", "AS1251", "AS1916"),
        failed_asns=(),
    )
    status_ok = get_ripestat_status(fetcher=lambda: sample_ok)
    for w in prohibited:
        assert w not in status_ok.message.lower()

    # 2. PARTIAL
    sample_partial = RipeStatResult(
        records=sample_ripestat_raw_records()[:1],
        requests_made=3,
        fetched_asns=("AS22548",),
        failed_asns=("AS1251", "AS1916"),
    )
    clear_ripestat_cache()
    status_partial = get_ripestat_status(fetcher=lambda: sample_partial)
    for w in prohibited:
        assert w not in status_partial.message.lower()

    # 3. UNAVAILABLE
    clear_ripestat_cache()
    status_unavailable = get_ripestat_status(
        fetcher=lambda: (_ for _ in ()).throw(RipeStatError())
    )
    for w in prohibited:
        assert w not in status_unavailable.message.lower()
