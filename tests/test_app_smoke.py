from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.config import DOWN_LINKS_SHOWN, RIPESTAT_SOURCE_URL
from src.models import Scenario
from src.services.real_data_service import (
    RealDataState,
    RipeStatAggregates,
    RipeStatRecord,
    RipeStatStatus,
)
from src.ui import ripestat

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
TAB_LABELS = [
    "Laboratório NOC (sintético)",
    "Internet pública — RIPE Atlas (dados reais)",
    "Internet pública — PeeringDB (dados reais)",
    "Internet pública — RIPEstat (dados reais)",
]
FAILURE_SCENARIOS = (
    Scenario.LINK_DEGRADED,
    Scenario.LINK_DOWN,
    Scenario.CORE_SWITCH_DOWN,
    Scenario.CPU_HIGH,
)


def _app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=60)


def _ripestat_status() -> RipeStatStatus:
    return RipeStatStatus(
        state=RealDataState.OK,
        message="Dados públicos de visibilidade de roteamento do RIPEstat carregados.",
        collected_at=datetime(2026, 9, 24, 8, 0, tzinfo=UTC),
        source=RIPESTAT_SOURCE_URL,
        requests_made=3,
        records=(
            RipeStatRecord(
                asn="AS22548",
                name="NIC.br",
                v4_seeing=323,
                v4_total=325,
                v4_visibility_pct=99.38,
                v6_seeing=317,
                v6_total=317,
                v6_visibility_pct=100.0,
                v4_prefixes=1,
                v6_prefixes=1,
                first_seen="2002-03-01T16:00:00",
                last_seen="2026-09-24T08:00:00",
                query_time="2026-09-24T08:00:00",
            ),
        ),
        aggregates=RipeStatAggregates(
            total_monitored=1,
            v4_full_visibility_count=1,
            v6_full_visibility_count=1,
            v4_partial_visibility_count=0,
            v6_partial_visibility_count=0,
            total_v4_prefixes=1,
            total_v6_prefixes=1,
        ),
        invalid_count=0,
    )


@pytest.mark.parametrize("scenario", FAILURE_SCENARIOS, ids=lambda item: item.value)
def test_smoke_failure_scenario_then_restore(scenario: Scenario) -> None:
    app = _app()
    app.run()
    assert not app.exception

    app.sidebar.selectbox[0].select(scenario)
    app.run()
    assert not app.exception

    app.sidebar.button[0].click()
    app.run()
    assert not app.exception

    if scenario is Scenario.CORE_SWITCH_DOWN:
        captions = [item.value for item in app.caption]
        assert any(f"mostrando os {DOWN_LINKS_SHOWN} principais." in text for text in captions)

    app.sidebar.button[1].click()
    app.run()
    assert not app.exception


def test_smoke_fourth_tab_ripestat_renders_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def fake_status(*, ignore_cache: bool = False) -> RipeStatStatus:
        calls.append(ignore_cache)
        return _ripestat_status()

    # Serviço injetado: a quarta aba renderiza sem nenhuma chamada HTTP.
    monkeypatch.setattr(ripestat, "get_ripestat_status", fake_status)
    app = _app()
    app.run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == TAB_LABELS

    app.session_state["main_tabs"] = TAB_LABELS[3]
    app.run()
    assert not app.exception
    assert len(app.metric) == 5
    assert len(app.dataframe) == 1
    assert calls == [False]
