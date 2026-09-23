from datetime import UTC, datetime

import pytest

from src.services.real_data_service import RealDataState, RealDataStatus, get_real_data_status
from src.ui import real_data
from src.ui.real_data import (
    collected_at_label,
    probes_summary,
    select_display_status,
    stale_banner,
    truncation_message,
    unavailable_message,
)


def _status(**overrides: object) -> RealDataStatus:
    base: dict = {
        "state": RealDataState.OK,
        "message": "Dados públicos do RIPE Atlas carregados.",
        "collected_at": datetime(2026, 9, 23, 14, 30, tzinfo=UTC),
        "source": "https://atlas.ripe.net/api/v2/probes/",
        "probes": (),
        "aggregates": None,
        "truncated": False,
        "requests_made": 1,
        "reported_count": 0,
        "invalid_count": 0,
    }
    base.update(overrides)
    return RealDataStatus(**base)


def test_probes_summary_distinguishes_loaded_from_reported() -> None:
    assert probes_summary(4500, 5200, True) == ("Probes carregadas", "4500 de 5200")
    assert probes_summary(5200, 5200, False) == ("Probes registradas", "5200")


def test_unavailable_message_adds_last_known_total() -> None:
    with_total = unavailable_message(
        _status(state=RealDataState.UNAVAILABLE, message="Falha.", reported_count=5200)
    )
    assert "Último total conhecido: 5200 probes." in with_total
    assert unavailable_message(_status(state=RealDataState.UNAVAILABLE, message="Falha.")) == (
        "Falha."
    )


def test_collected_at_label_handles_missing_timestamp() -> None:
    assert collected_at_label(None) == "N/D"
    moment = datetime(2026, 9, 23, 14, 30, tzinfo=UTC)
    assert collected_at_label(moment) == "23/09/2026 14:30 UTC"


def test_stale_banner_names_last_collection() -> None:
    banner = stale_banner(_status(collected_at=datetime(2026, 9, 23, 14, 30, tzinfo=UTC)))
    expected = "Exibindo última coleta bem-sucedida de 23/09 14:30 UTC — fonte indisponível agora"
    assert banner == expected
    assert "de N/D — fonte indisponível agora" in stale_banner(_status(collected_at=None))


def test_select_display_status_prefers_current_then_last_ok() -> None:
    current = _status(requests_made=2)
    last_ok = _status(requests_made=1)
    assert select_display_status(current, last_ok) is current
    assert select_display_status(None, last_ok) is last_ok
    down = _status(state=RealDataState.UNAVAILABLE)
    assert select_display_status(down, last_ok) is last_ok
    assert select_display_status(None, None) is None


def test_truncation_message_names_the_reason() -> None:
    pages = truncation_message(
        _status(
            truncated=True,
            truncated_reason="max_pages",
            message="Carregadas 4500 de 5200 probes.",
        )
    )
    assert pages.endswith("Motivo: limite de páginas.")
    budget = truncation_message(
        _status(truncated=True, truncated_reason="time_budget", message="Coleta parcial.")
    )
    assert budget.endswith("Motivo: limite de tempo.")
    fallback = truncation_message(_status(truncated=True, message="Coleta parcial."))
    assert fallback.endswith("Motivo: limite de coleta.")


def test_unavailable_result_is_not_cached(monkeypatch) -> None:
    calls = 0

    def fetcher():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")
        from src.integrations.ripe_atlas import AtlasResult

        return AtlasResult((), 0, False, 1)

    monkeypatch.setattr(
        real_data, "get_real_data_status", lambda: get_real_data_status(fetcher=fetcher)
    )
    real_data._load_real_data.clear()
    with pytest.raises(real_data.RealDataUnavailable):
        real_data._load_real_data()
    assert real_data._load_real_data().state == RealDataState.OK
    assert calls == 2
    real_data._load_real_data.clear()
