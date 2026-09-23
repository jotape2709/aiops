import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest
import streamlit
from streamlit.testing.v1 import AppTest

from src.config import PEERINGDB_CACHE_TTL_SECONDS
from src.services.real_data_service import (
    SP_RULE_LABEL,
    PdbAggregates,
    PdbExchange,
    PdbFacility,
    PeeringDbStatus,
    RealDataState,
    RealDataStatus,
    get_peeringdb_status,
)
from src.ui import peeringdb
from src.ui.peeringdb import (
    cooldown_remaining,
    cooldown_seconds,
    empty_message,
    exchange_bar_figure,
    excluded_none_count,
    excluded_note,
    facilities_with_coords,
    facility_map_figure,
    footer_caption,
    format_wait,
    partial_notice,
    peeringdb_kpis,
    peeringdb_unavailable_message,
    sp_facilities,
    top_exchange_label,
    top_exchanges,
)
from src.ui.real_data import REFRESH_COOLDOWN_SECONDS, DisplayableStatus, select_display_status

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _exchange(**overrides: object) -> PdbExchange:
    base: dict = {
        "ix_id": 1,
        "name": "IX Teste",
        "city": "São Paulo",
        "net_count": 100,
        "fac_count": 3,
        "in_sp": True,
    }
    base.update(overrides)
    return PdbExchange(**base)


def _facility(**overrides: object) -> PdbFacility:
    base: dict = {
        "fac_id": 1,
        "name": "Data Center Teste",
        "city": "São Paulo",
        "lat": -23.55,
        "lon": -46.63,
        "net_count": 50,
        "in_sp": True,
    }
    base.update(overrides)
    return PdbFacility(**base)


def _aggregates(**overrides: object) -> PdbAggregates:
    base: dict = {
        "ix_total": 10,
        "ix_sp": 3,
        "fac_total": 40,
        "fac_sp": 12,
        "top_exchange": _exchange(),
    }
    base.update(overrides)
    return PdbAggregates(**base)


def _status(**overrides: object) -> PeeringDbStatus:
    base: dict = {
        "state": RealDataState.OK,
        "message": "Carregados10 pontos de troca (IX) e40 data centers (facilities).",
        "collected_at": datetime(2026, 9, 23, 15, 0, tzinfo=UTC),
        "source": "https://www.peeringdb.com",
        "requests_made": 2,
        "exchanges": (),
        "facilities": (),
        "aggregates": None,
        "invalid_count": 0,
    }
    base.update(overrides)
    return PeeringDbStatus(**base)


def test_contract_constants_match_the_agreed_values() -> None:
    assert PEERINGDB_CACHE_TTL_SECONDS == 3600
    assert callable(get_peeringdb_status)


def test_peeringdb_kpis_format_values() -> None:
    kpis = dict(peeringdb_kpis(_aggregates()))
    assert kpis == {
        "IXPs no Brasil": "10",
        "IXPs em SP": "3",
        "Data centers no Brasil": "40",
        "Data centers em SP": "12",
        "Maior IXP por redes": "IX Teste (100)",
    }
    without_top = dict(peeringdb_kpis(_aggregates(top_exchange=None)))
    assert without_top["Maior IXP por redes"] == "N/D"


def test_top_exchange_label_uses_attributes() -> None:
    exchange = _exchange(name="IX Brasil", net_count=250)
    assert top_exchange_label(_aggregates(top_exchange=exchange)) == "IX Brasil (250)"


def test_top_exchange_label_handles_missing_value() -> None:
    assert top_exchange_label(_aggregates(top_exchange=None)) == "N/D"


def test_top_exchanges_caps_at_ten_and_drops_missing_counts() -> None:
    # Ordem garantida pelo service: net_count desc e None por último.
    counts = (900, 300, 200, 120, 80, 70, 60, 50, 40, 10, 5, None, None)
    exchanges = tuple(
        _exchange(ix_id=index, name=f"IX{index}", net_count=count)
        for index, count in enumerate(counts)
    )
    ranked = top_exchanges(exchanges)
    assert [item.net_count for item in ranked] == [900, 300, 200, 120, 80, 70, 60, 50, 40, 10]
    assert excluded_none_count(exchanges) == 2
    assert excluded_none_count(ranked) == 0
    note = excluded_note(2)
    assert note is not None and note.startswith("2 IXP(s)")
    assert excluded_note(0) is None


def test_top_exchanges_does_not_reorder_service_order() -> None:
    exchanges = (
        _exchange(ix_id=1, name="Menor", net_count=5),
        _exchange(ix_id=2, name="Maior", net_count=10),
    )
    assert [item.net_count for item in top_exchanges(exchanges)] == [5, 10]


def test_sp_facilities_filters_and_orders_by_networks() -> None:
    facilities = (
        _facility(fac_id=1, name="SP Baixo", net_count=5, in_sp=True),
        _facility(fac_id=2, name="Fora", net_count=300, in_sp=False, city="Rio de Janeiro"),
        _facility(fac_id=3, name="SP Sem Contagem", net_count=None, in_sp=True),
        _facility(fac_id=4, name="SP Alto", net_count=40, in_sp=True),
    )
    sp = sp_facilities(facilities)
    assert [item.name for item in sp] == ["SP Alto", "SP Baixo", "SP Sem Contagem"]


def test_facilities_with_coords_excludes_incomplete_pairs() -> None:
    facilities = (
        _facility(fac_id=1, name="Completa"),
        _facility(fac_id=2, name="Sem Latitude", lat=None),
        _facility(fac_id=3, name="Sem Longitude", lon=None),
    )
    mappable = facilities_with_coords(facilities)
    assert [item.name for item in mappable] == ["Completa"]


def test_empty_messages_cover_each_list() -> None:
    assert "IXP" in empty_message("exchanges")
    assert "coordenadas" in empty_message("map")
    assert "São Paulo" in empty_message("sp_facilities")
    assert empty_message("desconhecido") == "Sem dados disponíveis no momento."


def test_peeringdb_unavailable_message_uses_the_service_message() -> None:
    status = _status(state=RealDataState.UNAVAILABLE, message="Falha na coleta.")
    assert peeringdb_unavailable_message(status) == "Falha na coleta."


def test_partial_notice_only_when_endpoints_were_fetched() -> None:
    partial = _status(
        state=RealDataState.UNAVAILABLE,
        message="IXPs carregados; data centers falharam: limite de requisições.",
        collected_at=None,
        aggregates=None,
        fetched_endpoints=("ix",),
    )
    notice = partial_notice(partial)
    assert notice is not None
    assert "parcial" in notice
    total_failure = _status(
        state=RealDataState.UNAVAILABLE,
        message="PeeringDB fora do ar.",
        collected_at=None,
        aggregates=None,
        fetched_endpoints=(),
    )
    assert partial_notice(total_failure) is None


def test_footer_caption_reports_collection_and_source() -> None:
    caption = footer_caption(_status(collected_at=None, requests_made=2))
    assert "Coleta: N/D" in caption
    assert "2 requisição(ões)" in caption
    assert "[Fonte: PeeringDB](https://www.peeringdb.com)" in caption
    dated = footer_caption(_status(collected_at=datetime(2026, 9, 23, 15, 5, tzinfo=UTC)))
    assert "23/09/2026 15:05 UTC" in dated


def test_format_wait_switches_from_seconds_to_minutes() -> None:
    assert format_wait(45) == "~45 s"
    assert format_wait(59) == "~59 s"
    assert format_wait(60) == "~1 min"
    assert format_wait(90) == "~2 min"
    assert format_wait(1560) == "~26 min"
    assert format_wait(0) == "~0 s"
    assert format_wait(-5) == "~0 s"


def test_cooldown_seconds_honors_retry_after_but_never_below_default() -> None:
    assert cooldown_seconds(_status(retry_after_seconds=None)) == REFRESH_COOLDOWN_SECONDS
    assert cooldown_seconds(_status(retry_after_seconds=0)) == REFRESH_COOLDOWN_SECONDS
    assert cooldown_seconds(_status(retry_after_seconds=30)) == REFRESH_COOLDOWN_SECONDS
    assert cooldown_seconds(_status(retry_after_seconds=1560)) == 1560
    # Status sem o campo (modelo do RIPE) mantém o padrão por duck typing.
    assert cooldown_seconds(object()) == REFRESH_COOLDOWN_SECONDS
    assert cooldown_seconds(None) == REFRESH_COOLDOWN_SECONDS


def test_cooldown_remaining_counts_from_anchor_with_status_base() -> None:
    status = _status(retry_after_seconds=1560)
    assert cooldown_remaining(None, status, now=1000.0) == 0
    assert cooldown_remaining(1000.0, status, now=1010.0) == 1550
    assert cooldown_remaining(1000.0, _status(), now=1010.0) == REFRESH_COOLDOWN_SECONDS - 10
    assert cooldown_remaining(1000.0, _status(), now=1100.0) == 0


def test_select_display_status_accepts_peeringdb_status() -> None:
    current = _status(requests_made=2)
    last_ok = _status(requests_made=1)
    assert select_display_status(current, last_ok) is current
    down = _status(state=RealDataState.UNAVAILABLE)
    assert select_display_status(down, last_ok) is last_ok
    assert select_display_status(None, None) is None


def test_displayable_status_protocol_serves_both_services() -> None:
    peering = _status()
    ripe = RealDataStatus(
        state=RealDataState.OK,
        message="ok",
        collected_at=datetime(2026, 9, 23, 15, 0, tzinfo=UTC),
        source="https://atlas.ripe.net",
        probes=(),
        aggregates=None,
        truncated=False,
        requests_made=1,
    )
    assert isinstance(peering, DisplayableStatus)
    assert isinstance(ripe, DisplayableStatus)
    assert select_display_status(peering, None) is peering
    assert select_display_status(ripe, None) is ripe


def test_exchange_bar_figure_empty_shows_message() -> None:
    figure = exchange_bar_figure(())
    assert len(figure.data) == 0
    annotations = figure.layout.annotations
    assert annotations
    first = annotations[0] if isinstance(annotations, tuple) else annotations
    assert empty_message("exchanges") in first.text


def test_exchange_bar_figure_renders_top_ten_horizontal() -> None:
    # Ordem do service: net_count desc com None por último.
    counts = (900, 300, 200, 120, 80, 70, 60, 50, 40, 10, 5, None, None)
    exchanges = tuple(
        _exchange(ix_id=index, name=f"IX{index}", net_count=count)
        for index, count in enumerate(counts)
    )
    figure = exchange_bar_figure(exchanges)
    assert len(figure.data) == 1
    trace = figure.data[0]
    assert trace.type == "bar"
    assert trace.orientation == "h"
    assert len(trace.x) == 10
    assert None not in trace.x
    assert list(trace.x) == sorted(trace.x, reverse=True)
    assert len(trace.y) == 10


def test_facility_map_figure_empty_keeps_geo_layout() -> None:
    figure = facility_map_figure(())
    assert len(figure.data) == 0
    assert figure.layout.geo is not None


def test_facility_map_figure_highlights_sp_and_skips_missing_coords() -> None:
    facilities = (
        _facility(fac_id=1, name="SP Center", in_sp=True, lat=-23.55, lon=-46.63),
        _facility(fac_id=2, name="Rio Center", in_sp=False, lat=-22.9, lon=-43.2),
        _facility(fac_id=3, name="Sem Coordenadas", in_sp=True, lat=None, lon=None),
    )
    figure = facility_map_figure(facilities)
    assert [trace.name for trace in figure.data] == ["Demais localidades", "São Paulo"]
    assert sum(len(trace.lat) for trace in figure.data) == 2
    sp_trace = next(trace for trace in figure.data if trace.name == "São Paulo")
    assert sp_trace.marker.size == 11
    assert sp_trace.marker.color == "#33d6a6"


def test_unavailable_result_is_not_cached(monkeypatch) -> None:
    calls = 0

    def fetcher() -> PeeringDbStatus:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _status(state=RealDataState.UNAVAILABLE, message="Falha temporária.")
        return _status(requests_made=2)

    monkeypatch.setattr(peeringdb, "get_peeringdb_status", fetcher)
    peeringdb._load_peeringdb.clear()
    with pytest.raises(peeringdb.PeeringDbUnavailable):
        peeringdb._load_peeringdb()
    ok = peeringdb._load_peeringdb()
    assert ok.state == RealDataState.OK
    assert calls == 2
    peeringdb._load_peeringdb.clear()


def test_app_smoke_renders_noc_tab_without_network(monkeypatch) -> None:
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo
    connect_attempts: list[object] = []
    dns_attempts: list[str] = []

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) and address else None
        if isinstance(host, str) and host not in ("127.0.0.1", "::1", "localhost"):
            connect_attempts.append(address)
            raise OSError("conexão externa bloqueada no teste")
        return real_connect(self, address, *args, **kwargs)

    def _guarded_getaddrinfo(host, *args, **kwargs):
        if isinstance(host, str) and host and host not in ("127.0.0.1", "::1", "localhost"):
            dns_attempts.append(host)
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", _guarded_getaddrinfo)
    app = AppTest.from_file(str(APP_PATH), default_timeout=60)
    app.run()
    assert not app.exception
    assert connect_attempts == [], f"conexões inesperadas: {connect_attempts}"
    assert dns_attempts == [], f"resoluções de domínio inesperadas: {dns_attempts}"


def _run_peeringdb_app(
    monkeypatch: pytest.MonkeyPatch, status_factory: object
) -> tuple[AppTest, dict[str, list[str]]]:
    """Roda a aba com o service injetado, capturando textos de aviso/legenda."""
    captured: dict[str, list[str]] = {"caption": [], "warning": [], "info": []}
    for name in list(captured):
        real = getattr(streamlit, name)

        def _spy(
            body: object, *args: object, _name: str = name, _real: object = real, **kwargs: object
        ) -> object:
            captured[_name].append(str(body))
            return _real(body, *args, **kwargs)  # type: ignore[operator]

        monkeypatch.setattr(streamlit, name, _spy)
    monkeypatch.setattr(peeringdb, "get_peeringdb_status", status_factory)
    peeringdb._load_peeringdb.clear()
    app = AppTest.from_string(
        "from src.ui.peeringdb import render_peeringdb\nrender_peeringdb()",
        default_timeout=30,
    )
    app.run()
    peeringdb._load_peeringdb.clear()
    return app, captured


def test_app_smoke_peeringdb_ok_renders_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    ok = _status(
        exchanges=(_exchange(ix_id=1, name="IX A", city="São Paulo", net_count=10),),
        facilities=(_facility(),),
        aggregates=_aggregates(),
        fetched_endpoints=("ix", "fac"),
    )
    app, captured = _run_peeringdb_app(monkeypatch, lambda: ok)
    assert not app.exception
    assert len(app.metric) == 5
    assert len(app.button) == 1
    assert not app.button[0].disabled
    assert SP_RULE_LABEL in captured["caption"]
    assert not any("Coleta parcial" in text for text in captured["info"])


def test_app_smoke_peeringdb_partial_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    partial = _status(
        state=RealDataState.UNAVAILABLE,
        message="IXPs carregados; data centers falharam: limite de requisições atingido.",
        collected_at=None,
        aggregates=None,
        # Listas parciais vindas do Core: não podem aparecer na tela.
        exchanges=(_exchange(),),
        facilities=(_facility(),),
        fetched_endpoints=("ix",),
        retry_after_seconds=120,
    )
    app, captured = _run_peeringdb_app(monkeypatch, lambda: partial)
    assert not app.exception
    assert len(app.metric) == 0
    assert any("IXPs carregados" in text for text in captured["warning"])
    assert any("Coleta parcial" in text for text in captured["info"])
    assert any("Fonte:" in str(element.value) for element in app.markdown)


def test_app_smoke_peeringdb_unavailable_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    down = _status(
        state=RealDataState.UNAVAILABLE,
        message="PeeringDB atingiu o limite de requisições.",
        collected_at=None,
        aggregates=None,
        fetched_endpoints=(),
        retry_after_seconds=1560,
    )
    calls = 0

    def factory() -> PeeringDbStatus:
        nonlocal calls
        calls += 1
        return down

    app, captured = _run_peeringdb_app(monkeypatch, factory)
    assert not app.exception
    assert app.button[0].disabled
    assert any("em ~26 min" in text for text in captured["caption"])
    assert app.session_state["peeringdb_last_error"].retry_after_seconds == 1560
    # Segunda execução: o cooldown pula a recarga e não reconsulta o service.
    app.run()
    peeringdb._load_peeringdb.clear()
    assert not app.exception
    assert app.button[0].disabled
    assert calls == 1
