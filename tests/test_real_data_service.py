from src.services.real_data_service import RealDataState, get_real_data_status


def test_stub_is_local_and_not_configured(monkeypatch) -> None:
    def block_network(*args, **kwargs):
        raise AssertionError("Network access attempted")

    monkeypatch.setattr("socket.socket", block_network)
    status = get_real_data_status()
    assert status.state == RealDataState.NOT_CONFIGURED
    assert "não configurados" in status.message
