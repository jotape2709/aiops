from datetime import UTC, datetime

import pytest
import streamlit
from streamlit.testing.v1 import AppTest

from src.services.real_data_service import (
    RealDataState,
    RipeStatAggregates,
    RipeStatRecord,
    RipeStatStatus,
)
from src.ui import ripestat
from src.ui.real_data import REFRESH_COOLDOWN_SECONDS
from src.ui.ripestat import (
    LEGEND_TEXT,
    NO_ANNOUNCEMENTS_TEXT,
    STATE_LABELS,
    cooldown_remaining,
    cooldown_seconds,
    footer_caption,
    format_wait,
    no_visibility_caption,
    optional_int,
    partial_notice,
    peers_ratio,
    records_table,
    ripestat_kpis,
    visibility_cell,
    visibility_pct,
)

RECORD_COLUMNS = [
    "ASN",
    "Organização",
    "Visibilidade v4",
    "Peers v4 (vendo/total)",
    "Visibilidade v6",
    "Peers v6 (vendo/total)",
    "Prefixos v4",
    "Prefixos v6",
    "Primeira observação (first_seen)",
    "Última observação (last_seen)",
]


def _record(**overrides: object) -> RipeStatRecord:
    base: dict = {
        "asn": "AS22548",
        "name": "NIC.br",
        "v4_seeing": 323,
        "v4_total": 325,
        "v4_visibility_pct": 99.38,
        "v6_seeing": 317,
        "v6_total": 317,
        "v6_visibility_pct": 100.0,
        "v4_prefixes": 1,
        "v6_prefixes": 1,
        "first_seen": "2002-03-01T16:00:00",
        "last_seen": "2026-09-24T08:00:00",
        "query_time": "2026-09-24T08:00:00",
    }
    base.update(overrides)
    return RipeStatRecord(**base)


def _aggregates(**overrides: object) -> RipeStatAggregates:
    base: dict = {
        "total_monitored": 3,
        "v4_full_visibility_count": 2,
        "v6_full_visibility_count": 2,
        "v4_partial_visibility_count": 1,
        "v6_partial_visibility_count": 1,
        "total_v4_prefixes": 8,
        "total_v6_prefixes": 7,
        "v4_no_visibility_count": 0,
        "v6_no_visibility_count": 0,
    }
    base.update(overrides)
    return RipeStatAggregates(**base)


def _status(**overrides: object) -> RipeStatStatus:
    base: dict = {
        "state": RealDataState.OK,
        "message": "Dados públicos de visibilidade de roteamento do RIPEstat carregados.",
        "collected_at": datetime(2026, 9, 24, 8, 0, tzinfo=UTC),
        "source": "https://stat.ripe.net",
        "requests_made": 3,
        "records": (_record(),),
        "aggregates": _aggregates(),
        "invalid_count": 0,
    }
    base.update(overrides)
    return RipeStatStatus(**base)


def test_contract_constants_match_the_agreed_values() -> None:
    assert REFRESH_COOLDOWN_SECONDS == 60
    assert callable(ripestat.get_ripestat_status)


def test_ripestat_kpis_format_values() -> None:
    kpis = dict(ripestat_kpis(_aggregates()))
    assert kpis == {
        "ASNs monitorados": "3",
        "Visibilidade plena v4": "2 de 3",
        "Visibilidade plena v6": "2 de 3",
        "Prefixos v4": "8",
        "Prefixos v6": "7",
    }


def test_optional_values_render_as_dash() -> None:
    assert optional_int(None) == "—"
    assert optional_int(4) == "4"
    assert visibility_pct(None) == "—"
    assert visibility_pct(99.38) == "99.38%"
    assert visibility_pct(100.0) == "100%"
    assert visibility_pct(0.0) == "0%"
    assert peers_ratio(None, None) == "—"
    assert peers_ratio(323, 325) == "323/325"
    assert peers_ratio(None, 325) == "—/325"


def test_visibility_cell_is_neutral_without_announcements() -> None:
    # 0% de visibilidade ou zero prefixos: texto neutro no lugar do percentual.
    assert visibility_cell(0.0, 0) == NO_ANNOUNCEMENTS_TEXT
    assert visibility_cell(0.0, 5) == NO_ANNOUNCEMENTS_TEXT
    assert visibility_cell(None, 0) == NO_ANNOUNCEMENTS_TEXT
    # Dados ausentes continuam como travessão; dados normais seguem numéricos.
    assert visibility_cell(None, None) == "—"
    assert visibility_cell(50.0, 5) == "50%"
    assert visibility_cell(99.38, 1) == "99.38%"


def test_records_table_maps_contract_columns_and_dashes() -> None:
    sparse = _record(
        asn="AS65000",
        name="",
        v4_seeing=None,
        v4_total=None,
        v4_visibility_pct=None,
        v6_seeing=None,
        v6_total=None,
        v6_visibility_pct=None,
        v4_prefixes=None,
        v6_prefixes=None,
        last_seen=None,
    )
    table = records_table((_record(), sparse))
    assert list(table.columns) == RECORD_COLUMNS
    assert table.loc[0, "Visibilidade v4"] == "99.38%"
    assert table.loc[0, "Peers v4 (vendo/total)"] == "323/325"
    assert table.loc[0, "Visibilidade v6"] == "100%"
    assert table.loc[0, "Primeira observação (first_seen)"] == "2002-03-01T16:00:00"
    assert table.loc[0, "Última observação (last_seen)"] == "2026-09-24T08:00:00"
    assert table.loc[1, "Organização"] == "—"
    assert table.loc[1, "Visibilidade v4"] == "—"
    assert table.loc[1, "Peers v4 (vendo/total)"] == "—"
    assert table.loc[1, "Visibilidade v6"] == "—"
    assert table.loc[1, "Peers v6 (vendo/total)"] == "—"
    assert table.loc[1, "Prefixos v4"] == "—"
    assert table.loc[1, "Prefixos v6"] == "—"
    assert table.loc[1, "Primeira observação (first_seen)"] == "2002-03-01T16:00:00"
    assert table.loc[1, "Última observação (last_seen)"] == "—"


def test_records_table_marks_zero_visibility_as_no_announcements() -> None:
    # Caso real da carga: route server sem prefixos próprios e 0% de visibilidade.
    route_server = _record(
        asn="AS65000",
        name="Route Server",
        v4_seeing=0,
        v4_total=325,
        v4_visibility_pct=0.0,
        v4_prefixes=0,
        v6_seeing=0,
        v6_total=317,
        v6_visibility_pct=0.0,
        v6_prefixes=0,
    )
    table = records_table((route_server, _record()))
    assert table.loc[0, "Visibilidade v4"] == "Sem anúncios observados"
    assert table.loc[0, "Visibilidade v6"] == "Sem anúncios observados"
    assert table.loc[0, "Prefixos v4"] == "0"
    assert table.loc[0, "Peers v4 (vendo/total)"] == "0/325"
    # O resto da linha e os demais ASNs continuam numéricos.
    assert table.loc[1, "Visibilidade v4"] == "99.38%"
    assert table.loc[1, "Prefixos v4"] == "1"


def test_no_visibility_caption_reports_new_counters() -> None:
    assert no_visibility_caption(_aggregates()) == "ASNs sem anúncios observados: v4 0 · v6 0."
    counters = _aggregates(v4_no_visibility_count=1, v6_no_visibility_count=2)
    assert no_visibility_caption(counters) == "ASNs sem anúncios observados: v4 1 · v6 2."


def test_state_labels_cover_every_state_without_key_error() -> None:
    for state in RealDataState:
        assert STATE_LABELS[state]
    assert STATE_LABELS[RealDataState.PARTIAL] == "Parcial"
    assert STATE_LABELS[RealDataState.OK] == "Completa"
    assert STATE_LABELS[RealDataState.UNAVAILABLE] == "Indisponível"


def test_partial_notice_lists_failed_asns_and_keeps_message() -> None:
    ok = _status()
    assert partial_notice(ok) is None
    partial = _status(
        state=RealDataState.PARTIAL,
        message="Visibilidade obtida para 1 de 3 ASNs monitorados.",
        fetched_asns=("AS22548",),
        failed_asns=("AS26162", "AS1916"),
    )
    notice = partial_notice(partial)
    assert notice is not None
    assert "Visibilidade obtida para 1 de 3 ASNs monitorados." in notice
    assert "ASNs sem dados nesta coleta: AS26162, AS1916." in notice
    without_failures = _status(
        state=RealDataState.PARTIAL,
        message="Visibilidade obtida para 1 de 1 ASNs monitorados.",
    )
    assert partial_notice(without_failures) == without_failures.message


def test_footer_caption_reports_collection_source_and_query_time() -> None:
    caption = footer_caption(_status(collected_at=None, requests_made=1))
    assert "Coleta: N/D" in caption
    assert "1 requisição(ões)" in caption
    assert "Consulta RIPEstat: 2026-09-24T08:00:00" in caption
    assert "[Fonte: RIPEstat](https://stat.ripe.net)" in caption
    dated = footer_caption(_status(collected_at=datetime(2026, 9, 24, 8, 5, tzinfo=UTC)))
    assert "24/09/2026 08:05 UTC" in dated
    without_records = footer_caption(_status(records=(), collected_at=None, requests_made=1))
    assert "Consulta RIPEstat" not in without_records


def test_format_wait_switches_from_seconds_to_minutes() -> None:
    assert format_wait(45) == "~45 s"
    assert format_wait(59) == "~59 s"
    assert format_wait(60) == "~1 min"
    assert format_wait(1560) == "~26 min"
    assert format_wait(0) == "~0 s"
    assert format_wait(-5) == "~0 s"


def test_cooldown_seconds_honors_retry_after_but_never_below_default() -> None:
    assert cooldown_seconds(_status(retry_after_seconds=None)) == REFRESH_COOLDOWN_SECONDS
    assert cooldown_seconds(_status(retry_after_seconds=0)) == REFRESH_COOLDOWN_SECONDS
    assert cooldown_seconds(_status(retry_after_seconds=30)) == REFRESH_COOLDOWN_SECONDS
    assert cooldown_seconds(_status(retry_after_seconds=1560)) == 1560
    # Status sem o campo continuam com o padrão por duck typing.
    assert cooldown_seconds(object()) == REFRESH_COOLDOWN_SECONDS
    assert cooldown_seconds(None) == REFRESH_COOLDOWN_SECONDS


def test_cooldown_remaining_counts_from_anchor_with_status_base() -> None:
    status = _status(retry_after_seconds=1560)
    assert cooldown_remaining(None, status, now=1000.0) == 0
    assert cooldown_remaining(1000.0, status, now=1010.0) == 1550
    assert cooldown_remaining(1000.0, _status(), now=1010.0) == REFRESH_COOLDOWN_SECONDS - 10
    assert cooldown_remaining(1000.0, _status(), now=1100.0) == 0


def test_legend_explains_ris_visibility() -> None:
    assert "Visibilidade = % de peers RIS" in LEGEND_TEXT
    assert "não indicam problema operacional" in LEGEND_TEXT


def test_ui_copy_avoids_operational_words() -> None:
    copy = " ".join(
        (
            ripestat.INTRO_TEXT,
            LEGEND_TEXT,
            NO_ANNOUNCEMENTS_TEXT,
            " ".join(STATE_LABELS.values()),
            "Nenhum ASN com dados de visibilidade nesta coleta.",
        )
    ).lower()
    for word in ("incidente", "falha", "queda", "fora do ar"):
        assert word not in copy


def _run_ripestat_app(
    monkeypatch: pytest.MonkeyPatch, status_factory: object
) -> tuple[AppTest, dict[str, list[str]], list[bool]]:
    """Roda a aba com o serviço injetado, capturando textos e chamadas (sem rede)."""
    captured: dict[str, list[str]] = {"caption": [], "warning": [], "info": []}
    for name in list(captured):
        real = getattr(streamlit, name)

        def _spy(
            body: object, *args: object, _name: str = name, _real: object = real, **kwargs: object
        ) -> object:
            captured[_name].append(str(body))
            return _real(body, *args, **kwargs)  # type: ignore[operator]

        monkeypatch.setattr(streamlit, name, _spy)
    calls: list[bool] = []

    def fake_status(*, ignore_cache: bool = False) -> RipeStatStatus:
        calls.append(ignore_cache)
        return status_factory()  # type: ignore[operator]

    monkeypatch.setattr(ripestat, "get_ripestat_status", fake_status)
    app = AppTest.from_string(
        "from src.ui.ripestat import render_ripestat\nrender_ripestat()",
        default_timeout=30,
    )
    app.run()
    return app, captured, calls


def test_app_smoke_ripestat_ok_renders_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    ok = _status(
        records=(
            _record(),
            _record(asn="AS26162", name="IX.br"),
            _record(asn="AS1916", name="RNP"),
        ),
        aggregates=_aggregates(),
    )
    app, captured, calls = _run_ripestat_app(monkeypatch, lambda: ok)
    assert not app.exception
    assert len(app.metric) == 5
    assert len(app.button) == 1
    assert not app.button[0].disabled
    assert len(app.dataframe) == 1
    table = app.dataframe[0].value
    assert list(table["ASN"]) == ["AS22548", "AS26162", "AS1916"]
    assert LEGEND_TEXT in captured["caption"]
    assert any("Coleta: 24/09/2026 08:00 UTC" in text for text in captured["caption"])
    assert any("Consulta RIPEstat: 2026-09-24T08:00:00" in text for text in captured["caption"])
    assert any("[Fonte: RIPEstat](https://stat.ripe.net)" in text for text in captured["caption"])
    assert any("Situação da coleta: Completa" in text for text in captured["caption"])
    assert any("ASNs sem anúncios observados: v4 0 · v6 0." in text for text in captured["caption"])
    assert not captured["warning"]
    assert calls == [False]


def test_app_smoke_ripestat_aggregates_none_still_renders_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Contrato defensivo (M6.1): aggregates None pula só os cards de KPI.
    no_aggregates = _status(aggregates=None)
    app, captured, calls = _run_ripestat_app(monkeypatch, lambda: no_aggregates)
    assert not app.exception
    assert len(app.metric) == 0
    assert len(app.dataframe) == 1
    assert LEGEND_TEXT in captured["caption"]
    assert any("Coleta: 24/09/2026 08:00 UTC" in text for text in captured["caption"])
    assert any("Consulta RIPEstat: 2026-09-24T08:00:00" in text for text in captured["caption"])
    assert not captured["warning"]
    assert calls == [False]


def test_app_smoke_ripestat_partial_keeps_obtained_data(monkeypatch: pytest.MonkeyPatch) -> None:
    partial = _status(
        state=RealDataState.PARTIAL,
        message="Visibilidade obtida para 1 de 3 ASNs monitorados.",
        records=(_record(),),
        aggregates=_aggregates(total_monitored=1),
        fetched_asns=("AS22548",),
        failed_asns=("AS26162", "AS1916"),
    )
    app, captured, calls = _run_ripestat_app(monkeypatch, lambda: partial)
    assert not app.exception
    assert len(app.metric) == 5
    assert len(app.dataframe) == 1
    assert any("Visibilidade obtida para 1 de 3 ASNs monitorados." in text for text in captured["warning"])
    assert any(
        "ASNs sem dados nesta coleta: AS26162, AS1916." in text for text in captured["warning"]
    )
    assert any("Situação da coleta: Parcial" in text for text in captured["caption"])
    # PARTIAL entra no cooldown de 60 s (sem retry_after no status).
    assert app.button[0].disabled
    # Segunda execução: o cooldown reaproveita os dados obtidos sem nova consulta.
    app.run()
    assert not app.exception
    assert len(app.metric) == 5
    assert len(app.dataframe) == 1
    assert calls == [False]


def test_app_smoke_ripestat_unavailable_shows_friendly_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    down = _status(
        state=RealDataState.UNAVAILABLE,
        message="Limite de requisições do RIPEstat atingido; tente novamente em ~26 min.",
        collected_at=None,
        records=(),
        aggregates=None,
        fetched_asns=(),
        failed_asns=("AS22548", "AS26162", "AS1916"),
        retry_after_seconds=1560,
    )
    app, captured, calls = _run_ripestat_app(monkeypatch, lambda: down)
    assert not app.exception
    assert len(app.metric) == 0
    assert len(app.dataframe) == 0
    assert any("tente novamente em ~26 min" in text for text in captured["info"])
    assert any(
        "Fonte: [RIPEstat](https://stat.ripe.net)" in str(element.value)
        for element in app.markdown
    )
    assert app.button[0].disabled
    assert any("em ~26 min" in text for text in captured["caption"])
    assert app.session_state["ripestat_last_non_ok"].state == RealDataState.UNAVAILABLE
    # Segunda execução: o cooldown pula a recarga e não reconsulta o serviço.
    app.run()
    assert not app.exception
    assert app.button[0].disabled
    assert calls == [False]


def test_refresh_button_forces_ignore_cache_and_starts_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ok = _status()
    app, captured, calls = _run_ripestat_app(monkeypatch, lambda: ok)
    assert not app.exception
    assert calls == [False]
    assert not app.button[0].disabled
    app.button[0].click()
    app.run()
    assert not app.exception
    assert calls == [False, True]
    assert app.button[0].disabled
    assert any("Nova atualização disponível em" in text for text in captured["caption"])
    assert "ripestat_force_refresh" not in app.session_state
