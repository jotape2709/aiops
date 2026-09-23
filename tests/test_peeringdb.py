import io
import json
import socket
from datetime import UTC
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import pytest

from src.integrations.peeringdb import (
    PeeringDbError,
    PeeringDbRawExchange,
    PeeringDbRawFacility,
    fetch_peeringdb_data,
)


def raw_ix(ix_id: int = 1, name: str = "IX.br São Paulo", city: str = "São Paulo") -> dict:
    return {
        "id": ix_id,
        "name": name,
        "city": city,
        "country": "BR",
        "net_count": 2500,
        "fac_count": 12,
        # Campos de contato que devem ser descartados
        "tech_email": "tech@example.org",
        "tech_phone": "+55 11 9999-9999",
        "policy_email": "policy@example.org",
        "policy_phone": "+55 11 8888-8888",
        "sales_email": "sales@example.org",
        "sales_phone": "+55 11 7777-7777",
        "notes": "Internal note",
    }


def raw_fac(
    fac_id: int = 1,
    name: str = "Equinix SP4",
    city: str = "Barueri",
    lat: float = -23.4975,
    lon: float = -46.8145,
) -> dict:
    return {
        "id": fac_id,
        "name": name,
        "city": city,
        "country": "BR",
        "latitude": lat,
        "longitude": lon,
        "net_count": 594,
        # Campos de contato que devem ser descartados
        "tech_email": "tech@datacenter.org",
        "tech_phone": "+55 11 1111-1111",
        "sales_email": "sales@datacenter.org",
        "sales_phone": "+55 11 2222-2222",
        "notes": "Datacenter confidential notes",
    }


def response(data: list[dict]) -> io.BytesIO:
    return io.BytesIO(json.dumps({"data": data, "meta": {}}).encode())


def test_success_and_request_contract(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        if "ix" in request.full_url:
            return response([raw_ix(1), raw_ix(2, name="IX.br Rio", city="Rio de Janeiro")])
        return response([raw_fac(10)])

    result = fetch_peeringdb_data(opener=opener, timeout=8)
    assert len(result.exchanges) == 2
    assert len(result.facilities) == 1
    assert result.requests_made == 2
    assert result.invalid_count == 0

    assert len(calls) == 2
    for request, timeout in calls:
        assert timeout == 8
        assert request.get_method() == "GET"
        assert "aiops-network-dashboard" in request.get_header("User-agent")
        url = urlparse(request.full_url)
        assert parse_qs(url.query) == {"country": ["BR"]}


def test_privacy_contact_fields_never_stored(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))

    def opener(request, timeout):
        if "ix" in request.full_url:
            return response([raw_ix()])
        return response([raw_fac()])

    result = fetch_peeringdb_data(opener=opener)
    ix = result.exchanges[0]
    fac = result.facilities[0]

    sensitive_fields = [
        "tech_email",
        "tech_phone",
        "policy_email",
        "policy_phone",
        "sales_email",
        "sales_phone",
        "notes",
    ]
    for field in sensitive_fields:
        assert not hasattr(ix, field)
        assert not hasattr(fac, field)
        assert field not in PeeringDbRawExchange.__dataclass_fields__
        assert field not in PeeringDbRawFacility.__dataclass_fields__


def test_invalid_records_discarded_and_counted(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))

    def opener(request, timeout):
        if "ix" in request.full_url:
            # 1 válido, 1 sem id, 1 com net_count negativo
            return response([raw_ix(1), {"name": "No ID"}, {**raw_ix(2), "net_count": -5}])
        # 1 válido, 1 com latitude fora de intervalo, 1 não-dict
        return response([raw_fac(1), {**raw_fac(2), "latitude": 999.0}, "invalid_item"])

    result = fetch_peeringdb_data(opener=opener)
    assert len(result.exchanges) == 1
    assert len(result.facilities) == 1
    assert result.invalid_count == 4


def test_rate_limit_429_friendly_message_with_and_without_retry_after(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    from email.message import Message

    # 1. 429 com Retry-After numérico
    def opener_with_retry_after(request, timeout):
        headers = Message()
        headers["Retry-After"] = "42"
        raise HTTPError(request.full_url, 429, "Too Many Requests", headers, None)

    with pytest.raises(PeeringDbError) as exc_info:
        fetch_peeringdb_data(opener=opener_with_retry_after)
    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after_seconds == 42
    assert "tente novamente em ~42 s" in str(exc_info.value)

    # 2. 429 sem Retry-After
    def opener_without_retry_after(request, timeout):
        raise HTTPError(request.full_url, 429, "Too Many Requests", {}, None)

    with pytest.raises(PeeringDbError) as exc_info2:
        fetch_peeringdb_data(opener=opener_without_retry_after)
    assert exc_info2.value.status_code == 429
    assert exc_info2.value.retry_after_seconds is None
    assert "Limite de requisições do PeeringDB atingido. Tente novamente mais tarde." in str(
        exc_info2.value
    )


def test_parse_retry_after_formats() -> None:
    from datetime import datetime

    from src.integrations.peeringdb import _parse_retry_after

    assert _parse_retry_after("120") == 120
    assert _parse_retry_after("  5  ") == 5
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("") is None
    assert _parse_retry_after("not-a-number") is None

    # HTTP-date
    now = datetime(2026, 9, 23, 17, 30, 0, tzinfo=UTC)
    future_date = "Wed, 23 Sep 2026 17:31:30 GMT"
    assert _parse_retry_after(future_date, now_fn=lambda: now) == 90

    # Valores < 1 s retornam None
    assert _parse_retry_after("0") is None
    assert _parse_retry_after("-10") is None
    past_date = "Wed, 23 Sep 2026 17:25:00 GMT"
    assert _parse_retry_after(past_date, now_fn=lambda: now) is None


def test_request_spacing_sleep_called(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    sleep_calls = []

    def opener(request, timeout):
        if "ix" in request.full_url:
            return response([raw_ix()])
        return response([raw_fac()])

    result = fetch_peeringdb_data(
        opener=opener,
        request_interval=2.5,
        sleep=lambda interval: sleep_calls.append(interval),
    )
    assert len(result.exchanges) == 1
    assert len(result.facilities) == 1
    assert result.fetched_endpoints == ("ix", "fac")
    assert sleep_calls == [2.5]


@pytest.mark.parametrize(
    "opener",
    [
        lambda req, timeout: (_ for _ in ()).throw(
            HTTPError(req.full_url, 500, "Internal Error", {}, None)
        ),
        lambda req, timeout: (_ for _ in ()).throw(URLError("connection refused")),
        lambda req, timeout: (_ for _ in ()).throw(HTTPException("bad http")),
        lambda req, timeout: (_ for _ in ()).throw(TimeoutError()),
        lambda req, timeout: io.BytesIO(b"not json"),
        lambda req, timeout: io.BytesIO(b"[]"),
        lambda req, timeout: io.BytesIO(json.dumps({"data": "not a list"}).encode()),
    ],
)
def test_envelope_and_transport_failures(monkeypatch, opener) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    with pytest.raises(PeeringDbError):
        fetch_peeringdb_data(opener=opener)


def test_budget_exceeded_before_facilities(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    timeline = [0.0, 5.0, 25.0]

    def fake_clock():
        return timeline.pop(0) if timeline else 30.0

    def opener(request, timeout):
        return response([raw_ix()])

    with pytest.raises(PeeringDbError) as exc_info:
        fetch_peeringdb_data(
            opener=opener, total_budget=20.0, clock=fake_clock, sleep=lambda _: None
        )
    assert "Orçamento de tempo excedido" in str(exc_info.value)
    assert exc_info.value.requests_made == 1
    assert exc_info.value.fetched_endpoints == ("ix",)


def test_partial_failure_raises_typed_error(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))

    def opener(request, timeout):
        if "ix" in request.full_url:
            return response([raw_ix()])
        raise HTTPError(request.full_url, 503, "Service Unavailable", {}, None)

    with pytest.raises(PeeringDbError) as exc_info:
        fetch_peeringdb_data(opener=opener, sleep=lambda _: None)
    assert "data centers" in str(exc_info.value)
    assert exc_info.value.requests_made == 2
    assert exc_info.value.fetched_endpoints == ("ix",)


def test_429_on_second_get_propagates_to_unavailable_status(monkeypatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    from email.message import Message

    from src.services.real_data_service import RealDataState, get_peeringdb_status

    def opener(request, timeout):
        if "ix" in request.full_url:
            return response([raw_ix()])
        headers = Message()
        headers["Retry-After"] = "60"
        raise HTTPError(request.full_url, 429, "Too Many Requests", headers, None)

    status = get_peeringdb_status(
        fetcher=lambda: fetch_peeringdb_data(opener=opener, sleep=lambda _: None)
    )
    assert status.state == RealDataState.UNAVAILABLE
    assert status.retry_after_seconds == 60
    assert status.requests_made == 2
    assert status.fetched_endpoints == ("ix",)
    assert "IXPs carregados; data centers falharam:" in status.message
    assert "tente novamente em ~60 s" in status.message
