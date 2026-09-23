from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.config import DOWN_LINKS_SHOWN
from src.models import Scenario

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
FAILURE_SCENARIOS = (
    Scenario.LINK_DEGRADED,
    Scenario.LINK_DOWN,
    Scenario.CORE_SWITCH_DOWN,
    Scenario.CPU_HIGH,
)


def _app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=60)


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
