import pytest

from src.services.real_data_service import RealDataState, get_real_data_status
from src.ui import real_data


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
