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
