from datetime import UTC, datetime

from src.integrations.ripe_atlas import AtlasProbe, AtlasResult, RipeAtlasError
from src.services.real_data_service import RealDataState, get_real_data_status


def sample_batch(*, truncated: bool = False, invalid_count: int = 0) -> AtlasResult:
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
